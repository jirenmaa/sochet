import concurrent.futures
import signal
import sys
import threading
from socket import AF_INET, SOCK_STREAM, socket, timeout
from typing import Tuple

from config.logging import server_logger
from config.settings import BUFFER_SIZE, HOST, MESSAGE_DB, PORT, USER_DB
from server.util import *

Threadpool = concurrent.futures.ThreadPoolExecutor


class Server:

    def __init__(self):
        """
        Initializes the server state, including connection flags, client tracking,
        threading lock, and in-memory user and message databases.
        """
        self.is_running = True
        self.server = None
        self.clients = {}

        # self.broadcast() inside remove_client(), and both use with self.lock.
        # But since remove_client() already holds the lock, and broadcast() -
        # also tries to acquire it — the thread blocks itself, which leads to a deadlock.
        # RLock allows the same thread to re-acquire the lock without blocking itself
        # https://docs.python.org/3/library/threading.html#rlock-objects
        self.lock = threading.RLock()

        self.user_db = load_json(USER_DB)
        self.msg_db = load_json(MESSAGE_DB)

    # server related logic
    def start_connection(self):
        """
        Starts the server socket, binds to host/port, and begins listening for client connections.
        Spawns a thread pool executor to manage concurrent client sessions.
        """
        with socket(AF_INET, SOCK_STREAM) as self.server:
            self.server.bind((HOST, PORT))
            self.server.listen()
            self.server.settimeout(1)

            print(f"\nServer started on ***.***.***.***:{PORT}")
            server_logger.info(f"Server started on {HOST}:{PORT}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                self.accept_connection(executor)

    def accept_connection(self, executor: Threadpool):
        """
        Accepts new client connections in a loop while the server is running.
        Uses the thread pool executor to handle each client in a separate thread.
        """
        try:
            while self.is_running:
                self.accept_and_handle_connection(executor)
        except KeyboardInterrupt:
            self.is_running = False
            self.stop_connection()

    def accept_and_handle_connection(self, executor: Threadpool):
        """
        Accepts a client socket, verifies IP and credentials, and starts client session if authorized.
        """
        try:
            client_socket, client_address = self.server.accept()

            if not is_authorized(client_address):
                reject_unauthorized(client_socket, client_address)
                return

            credentials = client_socket.recv(BUFFER_SIZE).decode("utf-8")
            username, error = self.verify_user(credentials)

            if error or not username:
                client_socket.close()
                return

            self.process_new_connection(
                executor, client_socket, username, client_address
            )

        except timeout:
            return
        except OSError:
            self.is_running = False
            self.stop_connection()

    def process_new_connection(
        self,
        executor: Threadpool,
        client_socket: socket,
        username: str,
        client_address: Tuple[str, int],
    ):
        """
        Sends an auth success message to the client, announces the user's presence,
        and submits the session to a thread pool.
        """
        self.handle_message(client_socket, "AUTH_SUCCESS")
        self.broadcast(f"{username} has joined the chat!")

        server_logger.info(f"New connection: {username} - {client_address}")
        executor.submit(self.handle_client, client_socket, client_address, username)

        log_threading_info()

    def stop_connection(self):
        """
        Gracefully shuts down the server, closes all sockets, and terminates active threads.
        Ensures that resources like locks and client handlers are properly released.

        - Allows client-handling threads to break out of their `while self.is_running:` loop.
        - Stops the `accept_connections()` loop from accepting new connections.
        - Prevents client threads from hanging indefinitely by breaking their `recv()` loops.
        - Ensures that the lock object is eligible for garbage collection.

        https://stackoverflow.com/questions/6359597/gracefully-terminating-python-threads
        https://stackoverflow.com/questions/5019436/python-how-to-terminate-a-blocking-thread
        """
        self.is_running = False

        server_logger.info("Saving messages...")
        self.save_message()
        server_logger.info("Messages Saved...")

        print("[WARNING] Server shutting down...")
        server_logger.warning("Server shutting down...")

        if self.server:
            self.server.close()

        # Get a lock to ensure thread-safe access to the `self.clients` dictionary.
        # gracefully disconnect all active clients by calling `self.remove_client(client_socket)`
        # for each socket, ensuring a clean shutdown process.
        for client_socket in list(self.clients.keys()):
            self.remove_client(client_socket, stopped=True)
            log_threading_info("closed connection")

        server_logger.warning("Server shut down gracefully.")

    def save_message(self):
        """
        Saves the current message database to disk in JSON format.
        """
        save_json(MESSAGE_DB, self.msg_db)

    # auth related logic
    def verify_user(self, credentials: str):
        """
        Verifies a user's credentials in the format 'username::password'.
        Returns the username on success, otherwise returns an error string.
        """
        if "::" not in credentials:
            return None, "AUTH_FAILED"

        username, password = credentials.split("::")

        user_data = self.user_db.get(username)
        if not user_data:
            return None, "AUTH_FAILED"

        hashed_password = user_data["password"]
        if verify_password(password, hashed_password):
            return username, None

        return None, "AUTH_FAILED"

    def save_user(self):
        """
        Saves the current user database to disk in JSON format.
        """
        save_json(USER_DB, self.user_db)

    def create_user(self, username: str, password: str):
        """
        Creates a new user account by hashing the password and storing it in the user database.
        """
        if username in self.user_db:
            return None, "AUTH_FAILED"

        # hash the password using the bcrypt wrapper
        password_hash = hash_password(password).decode("utf-8")

        self.user_db[username] = {"username": username, "password": password_hash}

        self.save_user()

    # client related logic
    def handle_client(
        self, client_socket: socket, client_address: Tuple[str, int], username: str
    ):
        """
        Handles communication with a connected client:
        - Adds client to the active list.
        - Listens for incoming messages in a loop.
        - Broadcasts messages to other clients.
        """
        try:
            with self.lock:
                # get the lock to ensure thread-safe access to the shared self.clients dictionary
                # prevents race conditions when multiple threads try to modify the dictionary simultaneously
                self.clients[client_socket] = username
                self.broadcast_active_users()

            client_socket.settimeout(1.0)

            # continuous listening — it keeps reading messages from a connected client until -
            # the connection is closed or an error occurs.
            while self.is_running:
                if not self.process_client_message(client_socket, username):
                    break
        except Exception as e:
            server_logger.error(f"Error handling client {client_address}: {e}")
            self.remove_client(client_socket)

    def remove_client(self, client_socket: socket, stopped: bool = False):
        """
        Removes a client from the session:
        - Optionally notifies the client about shutdown.
        - Closes the socket and removes from internal tracking.
        - Broadcasts user exit to others.
        """

        # ensure thread-safe access to self.clients
        with self.lock:
            if client_socket not in self.clients:
                return

            username = self.clients.pop(client_socket)

            if stopped:
                self.handle_message(client_socket, "SERVER_SHUTDOWN")

            client_socket.close()

            if not stopped:
                self.broadcast(f"{username} has left the chat!")
                server_logger.info(f"User '{username}' disconnected.")
                self.broadcast_active_users()

    def broadcast_active_users(self):
        """
        Sends the list of currently active usernames to the target client.
        """
        with self.lock:
            user_list = list(self.clients.values())
            message = f"ACTIVE_USERS::{','.join(user_list)}"

            for client_socket in self.clients.keys():
                self.handle_message(client_socket, message)

    def broadcast(self, message: str, exclude_socket=None):
        """
        Sends a message to all connected clients except the excluded one (e.g., sender).
        Ensures thread-safe access to the client list.
        """

        # ensure thread-safe access to self.clients
        with self.lock:
            for client_socket in list(self.clients.keys()):
                self.handle_message(client_socket, message)

    def handle_message(self, client_socket: socket, message: str):
        """
        Sends a message to a specific client. Handles exceptions gracefully.
        If sending fails, the client is disconnected.
        """
        try:
            client_socket.send(message.encode("utf-8"))
        except Exception as e:
            server_logger.error(f"Error sending message to client: {client_socket}: {e}")

    def process_client_message(self, client_socket: socket, username: str):
        """
        Processes a single message from a client.
        Returns False if the client should be disconnected.
        """
        try:
            data = client_socket.recv(BUFFER_SIZE).decode("utf-8").strip()

            if not data:
                return True  # empty messages are ignored

            user, timestamp, message = parse_message(data, username)

            if message.upper() == "CLIENT_QUIT":
                self.remove_client(client_socket)
                return False

            self.broadcast(f"{user}::{timestamp}::{message}")

            self.msg_db.append(
                {
                    "user": user,
                    "message": message,
                    "timestamp": timestamp,
                }
            )

            return True

        except timeout:
            return True  # just loop again
        except ConnectionResetError as e:
            # https://docs.python.org/3/library/exceptions.html#ConnectionResetError
            server_logger.warning(f"Client disconnected abruptly: {client_socket} ({e})")
            self.remove_client(client_socket)
            return False
        except BrokenPipeError as e:
            # https://docs.python.org/3/library/exceptions.html#BrokenPipeError
            server_logger.warning(f"Broken pipe — client probably closed: {client_socket} ({e})")
            self.remove_client(client_socket)
            return False
        except Exception as e:
            server_logger.error(f"Error receiving message from {username}: {e}")
            return False


if __name__ == "__main__":
    server = Server()

    def signal_handler(sig, frame):
        server.stop_connection()
        server_logger.warning("Exiting application...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        """
        Sample user (username - password)
            admin   - admin
            actor-1 - actor1
            actor-2 - actor2

        server.create_user("username", "password")
        """
        server.start_connection()
    except Exception as e:
        server_logger.error(f"Server encountered an error: {e}")
        server.stop_connection()
