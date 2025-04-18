# fmt: off
import time
from json import dumps
from socket import AF_INET, SOCK_STREAM, socket, timeout
from threading import Event, RLock
from typing import Tuple

from config.logging import server_logger as logger
from config.settings import (BANNED_USER_DB, BUFFER_SIZE, HOST, MESSAGE_DB,
                             PORT, USER_DB)
from server.core.broadcaster import Broadcaster
from server.core.persistence import save_data
from server.handler.admin_commands import Commands
from server.manager import ClientManager
from shared.flags import *
from shared.protocol import build_response, parse_response
from utils.helpers import (hash_password, is_authorized, load_json,
                           parse_credentials, reject_connection,
                           verify_password)

# fmt: on


class Server:
    # Initialization & Server Lifecycle

    def __init__(self):
        """Initializes server resources, state flags, and in-memory databases."""
        self.is_running: bool = True
        self.server: socket | None = None
        self.clients: dict = {}
        # self.broadcast_message() inside remove_client(), and both use with self.lock.
        # But since remove_client() already holds the lock, and broadcast_message() -
        # also tries to acquire it — the thread blocks itself, which leads to a deadlock.
        # RLock allows the same thread to re-acquire the lock without blocking itself
        # https://docs.python.org/3/library/threading.html#rlock-objects
        self.lock: RLock = RLock()
        self.client_manager: ClientManager = ClientManager(max_workers=10)

        self.db_user = load_json(USER_DB)
        self.db_mesg = load_json(MESSAGE_DB)
        self.db_bans = set(load_json(BANNED_USER_DB))
        self.db_role = ["admin", "user"]

        self.admin_names = self.get_admin_usernames()

        self.muted_users: dict = {}

        self.commands: any = None
        self.broadcaster: any = None

    def start_connection(self):
        """Starts the server and accepts incoming connections."""
        with socket(AF_INET, SOCK_STREAM) as self.server:
            self.server.bind((HOST, PORT))
            self.server.listen()
            self.server.settimeout(1.0)

            # initialize socket-dependent classes
            self.broadcaster = Broadcaster(self)
            self.commands = Commands(self)

            print(f"\nServer started on ***.***.***.***:{PORT}")
            logger.info(f"Server started on {HOST}:{PORT}")

            try:
                while self.is_running:
                    self.accept_and_handle_connection()
            except KeyboardInterrupt:
                self.stop_connection()

    def stop_connection(self):
        """Gracefully shuts down the server and all client threads."""
        if not self.server:
            return

        self.is_running = False
        self.server.close()  # stop accepting new connections

        self.client_manager.shutdown_all()  # signal all client threads to exit

        print()
        save_data(MESSAGE_DB, self.db_mesg)  # save messages before shutdown

        # let threads do it via finally blocks
        # this avoids double-close, races, and duplicated state cleanup

        logger.info("Server shut down gracefully.")
        print("[INFO] Server shut down gracefully.")

    # Connection Management
    def accept_and_handle_connection(self):
        """Handles a new connection and starts a client thread."""
        try:
            client, address = self.server.accept()

            if not is_authorized(client_address=address[0]):
                return reject_connection(client, address)

            # get client remote address
            client_peer = client.getpeername()

            credentials = client.recv(BUFFER_SIZE).decode("utf-8")
            name, error = self.verify_user(client, credentials)

            if not name or error:
                logger.warning(f"[{error}] Unauthorized Attempt by {client_peer}")
                return

            self.clients[client] = name

            # submit the client handler to the thread pool via ClientManager,
            # which tracks lifecycle, manages cooperative shutdown signals,
            # and ensures proper cleanup when the client disconnects.
            self.client_manager.register(
                client, self.handle_client, client, address, name
            )
            logger.info(f"New connection: {name} - {client}")

            self.broadcaster.send_msg_to(client, AUTH_OK)
            self.broadcaster.broadcast_message(message=f"{name} has joined the chat!")
            self.broadcaster.broadcast_active_users()
            self.client_manager.log_client_threads()

        except timeout:
            pass
        except OSError:
            self.stop_connection()

    def handle_client(
        self, exit_event: Event, client: socket, address: Tuple[str, int], name: str
    ):
        """Handles incoming messages for a connected client."""
        try:
            client.settimeout(1.0)

            while self.is_running and not exit_event.is_set():
                if not self.handle_message(client, name):
                    break

        except Exception as e:
            logger.error(f"Handling client {address}: {e}")
        finally:
            self.remove_client(client)

    def handle_message(self, client: socket, sender: str):
        """Processes a message from a client."""
        try:
            now = time.time()

            # NOTE:
            # a bug caused by delayed recv() execution due to early return if we return the _check_mute first,
            # leading to buffer buildup and then message merging/overrun.
            # so, we need to read the buffer first, because it prevents socket buffer buildup and message merging.
            response = client.recv(BUFFER_SIZE).decode("utf-8").strip()

            if not response:
                return True

            _, message, flag, _ = parse_response(response)

            if flag == CLIENT_QUIT:
                return self.remove_client(client)

            elif not self.broadcaster.check_mute(client, sender, now):
                return True

            elif not self.broadcaster.check_rate_limit(client, now):
                return True

            elif sender in self.admin_names and message.startswith("/"):
                return self.commands.handle_admin_command(client, message, sender)

            elif not flag and flag not in FLAGS:
                self.broadcaster.broadcast_message(message=message, sender=sender)
                return True

        except timeout:
            return True
        except (ConnectionResetError, BrokenPipeError) as e:
            return self.remove_client(
                client, log_msg=f"Client disconnected: {client} ({e})"
            )
        except Exception:
            return True

    def remove_client(self, client, server_stop=False, with_broadcast=True, log_msg=""):
        """Disconnects a client, updates the active list, and broadcasts the update."""
        if client not in self.clients:
            return False

        with self.lock:
            if server_stop:
                self.broadcaster.broadcast_message(
                    flag=SYS_SERVER_CLOSED, message="Server has been shutdown."
                )

            username = self.clients.pop(client)

            # signal the thread to exit (cooperative shutdown)
            self.client_manager.shutdown(client)

            client.close()

            if not server_stop and with_broadcast:
                self.broadcaster.broadcast_message(
                    message=f"{username} has left the chat!"
                )
                self.broadcaster.broadcast_active_users()

            logger.info(log_msg or f"{username} disconnected.")
            self.client_manager.log_client_threads(info_msg="removing client")

            return False

    # User Management & Authentication
    def get_admin_usernames(self):
        """Returns list of admin usernames."""
        return [
            user["username"]
            for user in self.db_user.values()
            if user.get("role") == "admin"
        ]

    def verify_user(self, client, cred):
        """Verifies credentials sent from a client."""
        username, password = parse_credentials(cred)

        if not username or not password:
            payload = dumps(
                build_response(
                    sender="", message="Invalid Credential", flag=AUTH_INVALID
                )
            ).encode("utf-8")
            client.send(payload)
            client.close()
            return None, "AUTH_INVALID"

        if username in self.db_bans:
            payload = dumps(
                build_response(sender="", message="You Are Banned", flag=AUTH_BAN)
            ).encode("utf-8")
            client.send(payload)
            client.close()
            return None, "AUTH_BAN"

        user = self.db_user.get(username)
        if not user:
            payload = dumps(
                build_response(sender="", message="User Not Found.", flag=AUTH_DENIED)
            ).encode("utf-8")
            client.send(payload)
            client.close()
            return None, "AUTH_DENIED"

        if verify_password(password, user.get("password")):
            return username, None

        client.send("User Not Found.".encode())
        client.close()
        return None, "AUTH_DENIED"

    def create_user(self, username, password, role):
        """Creates and stores a new user."""
        if username in self.db_user:
            logger.info(f"{username} already exists.")
            return

        role = role if role in self.db_role else "user"
        self.db_user[username] = {
            "username": username,
            "password": hash_password(password).decode("utf-8"),
            "role": role,
        }
        save_data(USER_DB, self.db_user)

    # Messaging & Broadcast
    def send_msg_to(
        self, client: socket, flag: str = "", message: str = "", sender: str = ""
    ):
        self.broadcaster.send_msg_to(client, flag, message, sender)

    def broadcast_active_users(self):
        self.broadcaster.broadcast_active_users()

    def broadcast_message(
        self,
        skip_socket: socket | None = None,
        flag: str = "",
        message: str = "",
        sender: str = "",
    ):
        self.broadcaster.broadcast_message(skip_socket, flag, message, sender)
