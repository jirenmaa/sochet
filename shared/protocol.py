import json
from datetime import datetime

from config.logging import server_logger as logger


def payload_wrapper(message: dict):
    return (json.dumps(message) + "\n").encode("utf-8")


def parse_response(raw_response: str, with_log: bool = True):
    """Parses a json string into (sender, message, flag, timestamp)."""

    try:
        response = json.loads(raw_response)

        return (
            response.get("sender"),
            response.get("message"),
            response.get("flag"),
            response.get("timestamp"),
        )
    except json.JSONDecodeError as e:
        if not with_log:
            return

        logger.error(f"Invalid JSON received: {e} — raw: {raw_response}")


def build_response(flag: str = "", message: str = "", sender: str = "") -> str:
    """
    Constructs a JSON-formatted response to be sent to the client.

    Args:
        flag (str, optional): An optional tag for special message types (e.g., ADMIN_KICK). Default is "".
        message (str): The main message content.
        sender (str, optional): The sender of the message. Default is "" (e.g., for server/system messages).

    Returns:
        str: A JSON string representing the structured message.
    """
    response = {
        "flag": flag,
        "sender": sender,
        "message": message,
        "timestamp": datetime.now().strftime("%d %b %Y, %H:%M"),
    }
    return response
