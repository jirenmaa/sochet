import time
from socket import socket

from config.logging import server_logger as logger
from config.settings import BANNED_USER_DB
from server.core.persistence import save_data
from shared.flags import ADMIN_MSG, ADMIN_MUTE


class Commands:
    """
    Handles all administrative command actions such as /kick, /ban, /unban, /mute, and /help.
    Requires access to the server's internal methods and state via dependency injection.
    """

    def __init__(self, server: any = None):
        """
        Initialize command handler with access to the parent server instance.

        Args:
            server -- the main server object containing shared state and methods
        """
        self.server = server
        self.admin_command = {
            "/kick": "Kick a user from the chat. Usage: /kick <username>",
            "/ban": "Ban a user from reconnecting. Usage: /ban <username>",
            "/unban": "Unban a user. Usage: /unban <username>",
            "/mute": "Temporarily mute a user. Usage: /mute <username> <duration> (e.g. 10s)",
            "/help": "Show available admin commands.",
        }

    def handle_admin_command(self, admin_socket: socket, command: str, sender: str):
        """
        Dispatches admin command based on the command string.
        """
        parts = command.strip().split()

        if not parts:
            return True  # abort command

        cmd = parts[0].lower()

        if cmd not in self.admin_command:
            self.server.send_msg_to(
                admin_socket, ADMIN_MSG, "Unknown command. Use /help."
            )
            return True  # abort command

        if cmd == "/help":
            return self.admin_action_help(admin_socket)

        if len(parts) < 2:
            self.server.send_msg_to(admin_socket, ADMIN_MSG, "Missing target username.")
            return True  # abort command

        # extract the target username from the command (e.g., /mute <target_name> ...)
        target_name = parts[1]

        # prevent the admin from targeting themselves or another admin
        if target_name == sender or target_name in self.server.admin_names:
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                f"You cannot {cmd[1:]} yourself or another admin.",
            )
            return True  # abort command

        # route to specific command handler
        action_map = {
            "/kick": self.admin_action_kick,
            "/ban": self.admin_action_ban,
            "/unban": self.admin_action_unban,
            "/mute": self.admin_action_mute,
        }
        return action_map[cmd](admin_socket, target_name, sender, command)

    def admin_action_help(self, admin_socket: socket):
        """Sends list of all admin commands to the admin."""
        msg = "Admin Commands:\n" + "\n".join(
            f"{cmd}: {desc}" for cmd, desc in self.admin_command.items()
        )

        self.server.send_msg_to(admin_socket, ADMIN_MSG, msg)
        return True

    def admin_action_kick(
        self, admin_socket: socket, target_name: str, kicked_by: str, _
    ):
        """Kicks a connected user from the chat."""
        client = self.find_client_by_username(target_name)

        # ensure the target is currently in the chat
        if not client:
            self.server.send_msg_to(
                admin_socket, ADMIN_MSG, f"User '{target_name}' is not online."
            )
            return True  # abort action

        self.server.broadcast_message(
            message=f"{target_name} was kicked by [ADMIN] {kicked_by}"
        )
        self.server.remove_client(client, with_broadcast=False)
        self.server.broadcast_active_users()

        logger.warning(f"[ADMIN] {kicked_by} kicked {target_name}")
        return True

    def admin_action_ban(
        self, admin_socket: socket, target_name: str, banned_by: str, _
    ):
        """Bans a user (online or offline) and disconnects if online."""
        if target_name not in self.server.db_user:
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                f"Cannot ban '{target_name}': user does not exist.",
            )
            return True  # abort action

        if self.server.db_user[target_name].get("role") == "admin":
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                f"You cannot ban another admin: '{target_name}'.",
            )
            return True  # abort action

        self.server.db_bans.add(target_name)
        self.save_banned_users()

        client = self.find_client_by_username(target_name)
        if client:
            self.server.remove_client(client, with_broadcast=False)

        self.server.broadcast_message(
            message=f"'{target_name}' was banned by [ADMIN] {banned_by}"
        )
        self.server.broadcast_active_users()

        logger.warning(f"[ADMIN] {banned_by} banned {target_name}")
        return True

    def admin_action_unban(
        self, admin_socket: socket, target_name: str, unbanned_by: str, _
    ):
        """Removes a user from the banned list."""
        if target_name not in self.server.db_user:
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                f"Cannot unban '{target_name}': user does not exist.",
            )
            return True  # abort action

        if target_name not in self.server.db_bans:
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                f"Cannot unban '{target_name}': user is not banned.",
            )
            return True  # abort action

        self.server.db_bans.remove(target_name)
        self.save_banned_users()

        self.server.broadcast_message(
            message=f"'{target_name}' has been unbanned by [ADMIN] {unbanned_by}."
        )
        logger.info(f"[ADMIN] {unbanned_by} unbanned {target_name}")
        return True

    def admin_action_mute(
        self, admin_socket: socket, target_name: str, muted_by: str, command: str
    ):
        """Temporarily mutes a user for a specified duration."""
        client = self.find_client_by_username(target_name)

        if not client:
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                f"Cannot mute '{target_name}': user not in the chat.",
            )
            return True  # abort action

        # split the command string into parts: ['/mute', '<username>', '<duration>']
        parts = command.strip().split()

        # ensure the command includes both target username and duration (at least 3 parts)
        if len(parts) < 3:
            self.server.send_msg_to(
                admin_socket,
                ADMIN_MSG,
                "Invalid syntax. Use: /mute <username> <duration> (e.g., 10s, 2m, 1h)",
            )
            return True

        # etract the duration string (e.g., "10s", "2m", "1h") and convert to lowercase
        duration_str = parts[2].lower()
        unit_multipliers = {"s": 1, "m": 60, "h": 3600}

        # separate the numeric part and the unit character (e.g., "10" and "s")
        unit = duration_str[-1]
        amount = duration_str[:-1]

        # validate that the unit is allowed and the amount is a valid digit
        if unit not in unit_multipliers or not amount.isdigit():
            self.server.send_msg_to(
                admin_socket, ADMIN_MSG, "Invalid duration. Use 10s, 2m, or 1h."
            )
            return True  # abort action

        # convert duration to total seconds (e.g., 10 * 60 for 10 minutes)
        seconds = int(amount) * unit_multipliers[unit]
        mute_expiration = time.time() + seconds

        self.server.muted_users[target_name] = {
            "until": mute_expiration,
            "warned": False,
        }

        self.server.send_msg_to(client, ADMIN_MUTE, amount)
        self.server.broadcast_message(
            message=f"'{target_name}' has been muted by [ADMIN] {muted_by} for {duration_str}."
        )
        logger.warning(f"[ADMIN] {muted_by} muted {target_name} for {seconds}s")
        return True

    def find_client_by_username(self, username: str):
        """Returns the socket object of the user by username, or None."""
        for client, name in self.server.clients.items():
            if name == username:
                return client

        return None

    def save_banned_users(self):
        """Saves banned users to disk."""
        save_data(BANNED_USER_DB, list(self.server.db_bans))
