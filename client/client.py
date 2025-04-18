import json
import threading
import time
from socket import AF_INET, SOCK_STREAM, socket
from typing import Tuple

from config.logging import client_logger as logger
from config.settings import BUFFER_SIZE, HOST, PORT
from shared.protocol import parse_response


class Client:
    """
    Handles connection, authentication, and communication with the server.
    Interacts with the GUI for displaying messages and feedback.
    """

    def __init__(self, gui: object, username: str, password: str):
        self.is_running = True
        self.client = None
        self.gui = gui

        self.username = username
        self.password = password
        self.client_ip, self.client_port = None, None

        self.lock = threading.Lock()

    def connect_to_server(self) -> Tuple[str, bool]:
        """
        Establish a connection to the server and perform authentication.
        Returns True on success, False otherwise.
        """
        try:
            self.client = socket(AF_INET, SOCK_STREAM)
            self.client.connect((HOST, PORT))
            self.client_ip, self.client_port = self.client.getpeername()

            credentials = {
                "username": self.username,
                "password": self.password,
            }

            self.client.send(json.dumps(credentials).encode("utf-8"))

            raw_response = self.client.recv(BUFFER_SIZE).decode("utf-8")
            responses = raw_response.strip().split("\n")

            authenticated = False

            for response in responses:
                if not response.strip():
                    continue

                _, message, flag, _ = parse_response(response)

                if flag == "AUTH_OK":
                    authenticated = True

                elif flag == "USER_LIST_UPDATE":
                    self.handle_active_users(message)

                else:
                    return message, True  # return msg and error

            if authenticated:
                self.password = None
                threading.Thread(target=self.read_message, daemon=True).start()
                return "", False

            logger.warning(f"Authentication failed for user: {self.username}")
            self.disconnect_from_server()
            return "", True
        except Exception as e:
            self.disconnect_from_server()
            return "", True

    def disconnect_from_server(self, server_stopped: bool = False):
        """
        Gracefully close the client socket and clean up.
        """
        try:
            if not self.client:
                raise ValueError("Client socket is not initialized.")

            if server_stopped:
                self.gui.display_message("🛑 Server has shut down.")

            logger.info(
                f"Disconnected client ({self.username}) from {self.client_ip}:{self.client_port}"
            )

            self.client.close()
            self.gui.message_entry.config(state="disabled")
        except Exception as e:
            self.gui.display_message(f"Error closing connection: {e}")
            logger.error(f"Error closing connection: {e}")

        finally:
            self.client = None

    def write_message(self, message: str = "", flag: str = ""):
        """
        Thread-safe message sender to the server.
        """
        with self.lock:
            if not self.client:
                raise ValueError("Cannot send message: client is not connected.")

            try:
                # fmt: off
                self.client.send(json.dumps({
                    "flag": flag,
                    "sender": self.username,
                    "message": message,
                }).encode("utf-8"))
                # fmt: on
            except Exception as e:
                logger.error("Sending message:", e)
                self.disconnect_from_server()

    def read_message(self):
        """
        Listens for messages from the server and routes them to handlers.
        """
        if not self.client:
            self.disconnect_from_server()
            return

        while self.is_running:
            raw_message = self.client.recv(BUFFER_SIZE).decode("utf-8")
            if not raw_message:
                break

            for message in raw_message.strip().split("\n"):
                if not message:
                    continue

                sender, content, flag, timestamp = parse_response(message)
                self._dispatch_server_message(flag, content, sender, timestamp)

                if not self.is_running:
                    break

        self.client.close()
        self.gui.message_entry.config(state="disabled")

    def _dispatch_server_message(
        self, flag: str, content: str, sender: str, timestamp: str
    ):
        """
        Routes server messages based on their flags.
        """
        dispatch = {
            "SYS_SERVER_CLOSED": self._handle_server_shutdown,
            "USER_LIST_UPDATE": lambda _f, _s, m, _t: self.handle_active_users(m),
            "ADMIN_KICK": self._handle_flag_response,
            "ADMIN_BAN": self._handle_flag_response,
            "ADMIN_MUTE": self._handle_flag_response,
            "ADMIN_MSG": self._handle_flag_response,
        }

        handler = dispatch.get(flag)
        if handler:
            handler(flag, sender, content, timestamp)

            if flag in {"SYS_SERVER_CLOSED", "ADMIN_KICK", "ADMIN_BAN"}:
                self.is_running = False
        else:
            if sender:
                display = f"\n\n{sender} ({timestamp})\n↳ {content}"
                self.gui.display_message(display)
            else:
                self.gui.display_message(f"\n\n({timestamp}) {content}", tag="info")

    def handle_active_users(self, msg: str):
        """Update the active user list in the GUI."""
        users = msg.split(",")
        self.gui.update_active_users(users)

    def _handle_flag_response(self, flag: str, _sender: str, msg: str, _timestamp: str):
        """Handles admin-related server messages."""
        if flag == "ADMIN_MUTE":
            try:
                self._start_mute_countdown(int(msg))
            except ValueError:
                logger.error("Muting client:", msg)
                self.disconnect_from_server()
            return

        self.gui.display_message(f"\n\n{msg}")

    def _handle_server_shutdown(
        self, _flag: str, _sender: str, _msg: str, _timestamp: str = ""
    ):
        """Handles server shutdown signal."""
        logger.info("Server shutdown message received.")
        self.disconnect_from_server(server_stopped=True)

    def _start_mute_countdown(self, duration: int):
        """
        Disables the message entry for a set duration, updating the entry field with a countdown.
        """

        def countdown():
            entry = self.gui.message_entry
            entry.config(state="normal")  # enable temporarily to insert text
            entry.delete(0, "end")

            for remaining in range(duration, 0, -1):
                entry.config(state="normal")
                entry.delete(0, "end")
                entry.insert(0, f"🔇 Muted ({remaining}s)...")
                entry.config(state="disabled")
                time.sleep(1)

            entry.config(state="normal")
            entry.delete(0, "end")

        threading.Thread(target=countdown, daemon=True).start()
