import json
from socket import socket
from typing import List, Tuple

import bcrypt

from config.logging import server_logger as logger
from config.settings import WHITELIST


def hash_password(password: str) -> str:
    """
    Generates a salted bcrypt hash from the provided plaintext password.
    Intended for secure password storage.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against its previously hashed bcrypt counterpart.
    Returns True if the password is valid, False otherwise.
    """
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def is_authorized(client_address: str):
    """
    Checks whether a client IP address is present in the whitelist.
    Returns True if authorized; otherwise, False.
    """
    return client_address in WHITELIST


def reject_connection(client: socket, client_address: Tuple[str, int]):
    """
    Closes the client socket and logs an unauthorized access attempt.
    Intended for handling disallowed or blacklisted connections.
    """
    client.close()
    logger.warning(f"Unauthorized connection attempt from {client_address}")


def parse_credentials(credentials: str) -> Tuple[str, str]:
    """
    Attempts to deserialize a JSON-encoded credential string.
    Returns a tuple of (username, password), or (None, None) if parsing fails.
    """
    try:
        data = json.loads(credentials)

        return (data.get("username"), data.get("password"))
    except json.JSONDecodeError as e:
        return None, None


def load_json(file_path: str):
    """
    Loads and returns the contents of a JSON file.
    Returns the parsed data or None on failure, logging errors as needed.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except json.JSONDecodeError:
        print(f"Invalid JSON content in {file_path}")
    except Exception as e:
        print(f"Error loading JSON file: {e}")

    return None


def save_json(file_path: str, data: List[dict] | List[str]):
    """
    Saves a Python object to a specified file as formatted JSON.
    Logs an error message if the save operation fails.
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error("Failed to save JSON: {e}")
