import socket
import threading
from config.settings import HOST, PORT, BUFFER_SIZE


class Client:
    def __init__(self, gui, username, password):
        self.client_socket = None
        self.gui = gui
        self.username = username
        self.password = password
        self.is_running = False

    def connect(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((HOST, PORT))
            self.client_socket.send(f"{self.username}::{self.password}".encode("utf-8"))

            response = self.client_socket.recv(BUFFER_SIZE).decode("utf-8")

            if response == "AUTH_SUCCESS":
                self.is_running = True

                threading.Thread(target=self.receive_messages, daemon=True).start()
                return True
            else:
                self.gui.display_message(
                    "Login failed. Incorrect username or password."
                )
                return False
        except Exception as e:
            self.gui.display_message(f"Connection error: {e}")
            return False

    def receive_messages(self):
        while self.is_running:
            try:
                message = self.client_socket.recv(BUFFER_SIZE).decode("utf-8")
                if message:
                    self.gui.display_message(message)
            except Exception as e:
                self.gui.display_message(f"Error receiving message: {e}")
                break

    def send_message(self, message):
        if self.client_socket and self.is_running:
            try:
                self.client_socket.send(message.encode("utf-8"))
                self.gui.display_message(f"You: {message}")  # display sent message locally
            except Exception as e:
                self.gui.display_message(f"Error sending message: {e}")

    def disconnect(self):
        self.is_running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception as e:
                self.gui.display_message(f"Error closing connection: {e}")
