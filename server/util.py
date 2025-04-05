import threading
import json
from socket import socket
from typing import Tuple

import bcrypt

from config.logging import server_logger

from config.settings import WHITELIST
from config.logging import server_logger


def hash_password(password: str) -> str:
    # generate a salt and hash the password using bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt)


def verify_password(password: str, hashed_password: str) -> bool:
    # verify the password against the stored hashed password
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def is_authorized(client_address: socket):
    return client_address[0] in WHITELIST


def reject_unauthorized(client_socket: socket, client_address: Tuple[str, int]):
    client_socket.close()
    server_logger.warning(f"Unauthorized connection attempt from {client_address}")


def parse_message(data: str, fallback_user: str = "anonim") -> Tuple[str, str]:
    """
    Parses a message string into (username, timestamp, message).
    Falls back to provided username if not embedded.
    """
    if "::" in data:
        return data.split("::", 2)

    return fallback_user, "January 1st, 1988 00:00:00", data


def load_json(file_path: str):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[INFO] Loaded JSON data from {file_path}")
            return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except json.JSONDecodeError:
        print(f"Invalid JSON content in {file_path}")
    except Exception as e:
        print(f"Error loading JSON file: {e}")

    return None


def save_json(file_path: str, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            print(f"Saved JSON data to {file_path}")
    except Exception as e:
        print(f"Failed to save JSON: {e}")


def log_threading_info(info_msg: str = "new connection") -> None:
    active_threads = [t.name for t in threading.enumerate() if t.is_alive()]
    server_logger.info(
        f"[{threading.active_count()}] Active threads after {info_msg}: {active_threads}"
    )
