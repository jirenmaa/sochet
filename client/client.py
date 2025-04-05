import threading
from datetime import datetime
from socket import AF_INET, SOCK_STREAM, socket

from config.logging import client_logger
from config.settings import BUFFER_SIZE, HOST, PORT


class Client:
    """
    Handles the connection to the server, user authentication, message
    transmission, and reception in a multi-threaded environment. It interacts with the
    GUI for displaying messages and user feedback.
    """

    def __init__(self, gui: any, username: str, password: str):
        """
        Initialize a client instance with GUI reference and user credentials.
        """
        self.client = None
        self.gui = gui
        self.username = username
        self.password = password
        self.client_ip, self.client_port = (None, None)

        # threading lock for safe access to shared resources
        self.lock = threading.Lock()

    def connect_to_server(self):
        """
        Establishes a connection to the server and handles user authentication.

        Returns:
            bool: True if authenticated and connected, False otherwise.
        """
        try:
            self.client = socket(AF_INET, SOCK_STREAM)
            self.client.connect((HOST, PORT))
            client_logger.info(f"Connected to server at {HOST}:{PORT}")

            credentials = f"{self.username}::{self.password}"
            self.client.send(credentials.encode("utf-8"))

            response = self.client.recv(BUFFER_SIZE).decode("utf-8")

            if response == "AUTH_SUCCESS":
                threading.Thread(target=self.read_message, daemon=True).start()
                client_logger.info(f"Authentication successful: {self.username}")

                self.password = None
                self.client_ip, self.client_port = self.client.getpeername()

                return True
            else:
                self.gui.display_message(
                    "Login failed. Incorrect username or password."
                )
                client_logger.warning(f"Authentication failed: {self.username}")
                self.disconnect_from_server()

                return False
        except Exception as e:
            client_logger.error(f"Connection error: {e}")
            self.disconnect_from_server()

            return False

    def disconnect_from_server(self, server_stopped: bool = False):
        """
        Closes the client socket connection and performs cleanup.

        Args:
            server_stopped (bool): Flag indicating if server has shut down.
        """
        if not self.client:
            client_logger.error(f"No active client connection found.")
            raise ValueError(
                "Client instance is not initialized. Attempted to access or operate on a null client reference."
            )

        try:
            if server_stopped:
                self.gui.display_message(f"🛑 The server has been shut down")

            client_logger.info(
                "Client at %s:%s disconnected.", self.client_ip, self.client_port
            )
            self.client.close()
        except Exception as e:
            self.gui.display_message(f"Error closing connection: {e}")
            client_logger.error(f"Error closing connection: {e}")
        finally:
            self.client = None

    def write_message(self, message: str):
        """
        Sends a message to the server with thread-safe access.
        """
        if not self.client:
            client_logger.error("No active client connection found.")
            raise ValueError(
                "Client instance is not initialized. Attempted to access or operate on a null client reference."
            )

        with self.lock:  # ensure only one thread can send messages at a time
            try:
                timestamp = datetime.now().isoformat()
                payload = (
                    f"{self.username}::{timestamp}::{message}"  # simple format payload
                )

                self.client.send(payload.encode("utf-8"))
                client_logger.info(f"Message from [{self.username}]: {message}")
            except Exception as e:
                client_logger.error(f"Error sending message: {e}")
                self.disconnect_from_server()

    def read_message(self):
        """
        Continuously listens for incoming messages from the server and updates the GUI.

        Handles server shutdown signals and other disconnect scenarios gracefully.
        """
        while True:
            try:
                response = self.client.recv(BUFFER_SIZE).decode("utf-8")

                if response == "SERVER_SHUTDOWN":
                    client_logger.info("Disconnected from server.")
                    self.disconnect(is_server_down=True)
                    break

                # (e.g., user joined or left), which do not follow the 'username::timestamp::message' format
                if "::" not in response:
                    self.gui.display_message(f"\n\n{response}", tag="info")
                    continue

                user, timestmp, msg = response.split("::")

                message = f"\n\n{user} ({timestmp})\n↳ {msg}"

                self.gui.display_message(message)
            except Exception as e:
                client_logger.error(f"Error receiving message: {e}")
                self.disconnect_from_server()

                break
