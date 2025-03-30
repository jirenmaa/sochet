import socket
import threading
from config.settings import HOST, PORT, BUFFER_SIZE
from config.logging_config import client_logger


class Client:
    """
    A client class to handle communication with the server via sockets.
    Provides methods to connect, send messages, and receive messages asynchronously.
    """

    def __init__(self, gui, username, password):
        self.client_socket = None
        self.gui = gui
        self.username = username
        self.password = password
        self.lock = threading.Lock()  # ensure thread-safe message sending

    def connect(self):
        """Establishes connection to the server and authenticates the client."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((HOST, PORT))
            client_logger.info(f"Connected to server at {HOST}:{PORT}")

            credentials = f"{self.username}::{self.password}"
            self.client_socket.send(credentials.encode("utf-8"))

            response = self.client_socket.recv(BUFFER_SIZE).decode("utf-8")

            if response == "AUTH_SUCCESS":
                threading.Thread(target=self.receive_messages, daemon=True).start()
                client_logger.info(f"Authentication successful: {self.username}")

                return True
            else:
                self.gui.display_message(
                    "Login failed. Incorrect username or password."
                )
                client_logger.warning(f"Authentication failed: {self.username}")
                self.disconnect()

                return False
        except Exception as e:
            client_logger.error(f"Connection error: {e}")
            self.disconnect()

            return False

    def receive_messages(self):
        """
        Receives messages from the server asynchronously and displays them in the GUI.
        Terminates on disconnection or socket errors.
        """
        while True:
            try:
                message = self.client_socket.recv(BUFFER_SIZE).decode("utf-8")

                if message == "SERVER_SHUTDOWN" or not message:
                    client_logger.info("Disconnected from server.")
                    self.disconnect(is_server_down=True)
                    break

                self.gui.display_message(message)
            except Exception as e:
                client_logger.error(f"Error receiving message: {e}")
                self.disconnect()

                break

    def send_message(self, message):
        """Sends a message to the server."""
        if self.client_socket:
            with self.lock:  # Ensure only one thread can send messages at a time
                try:
                    self.client_socket.send(message.encode("utf-8"))
                    self.gui.display_message(f"You: {message}")
                    client_logger.info(f"Message sent: {message}")
                except Exception as e:
                    client_logger.error(f"Error sending message: {e}")
                    self.disconnect()

    def disconnect(self, is_server_down: bool = False):
        """Closes the client socket and performs cleanup operations."""
        if self.client_socket:
            try:
                if is_server_down:
                    self.gui.display_message(f"🛑 The server has been shut down")

                self.client_socket.close()
                client_logger.info("Client socket closed successfully.")
            except Exception as e:
                self.gui.display_message(f"Error closing connection: {e}")
                client_logger.error(f"Error closing connection: {e}")
            finally:
                self.client_socket = None
