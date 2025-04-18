from __future__ import annotations

import time
from collections import deque
from socket import socket

from config.logging import server_logger
from shared.flags import ADMIN_MSG, USER_LIST_UPDATE
from shared.protocol import build_response, payload_wrapper


class Broadcaster:
    def __init__(self, server: any = None):
        """
        Initialize broadcaster handler with access to the parent server instance.

        Args:
            server -- the main server object containing shared state and methods
        """
        self.server = server

        self.message_rate_limit = {
            "interval": 10,  # minimum time (seconds) between messages
            "max_messages": 5,  # max allowed
            "user_timestamps": {},  # socket -> deque([t1, t2, t3])
        }

    def broadcast_message(
        self,
        skip_socket: socket | None = None,
        flag: str = "",
        message: str = "",
        sender: str = "",
    ):
        """Sends a message to all connected clients."""
        with self.server.lock:
            for client in list(self.server.clients.keys()):
                if client != skip_socket:
                    self.send_msg_to(client, flag, message, sender)
            
            if not flag and sender:
                # save only non-system messages (user send message only)
                payload = build_response(flag, message, sender)
                self.server.db_mesg.append(payload)

    def send_msg_to(
        self, client: socket, flag: str = "", message: str = "", sender: str = ""
    ):
        """Sends a message to a specific client safely with lock."""
        try:
            with self.server.lock:
                payload = build_response(flag, message, sender)
                client.sendall(payload_wrapper(payload))
        except Exception as e:
            server_logger.error(f"Sending message to client {client}: {e}")

    def broadcast_active_users(self):
        """Sends active user list to all clients."""
        with self.server.lock:
            users = ",".join(self.server.clients.values())

            for client in self.server.clients:
                self.send_msg_to(client, USER_LIST_UPDATE, users)

    def check_mute(self, client: socket, username: str, now: time) -> bool:
        """
        Checks if the user is muted. Sends mute warning only once.
        Returns True if allowed to speak, False if muted.
        """
        mute_info = self.server.muted_users.get(username)

        if not mute_info:
            return True  # not muted

        unmute_time = mute_info["until"]

        if now < unmute_time:
            # still muted — warn only once
            if not mute_info.get("warned", False):
                remaining = int(unmute_time - now)
                self.send_msg_to(
                    client,
                    flag=ADMIN_MSG,
                    message=f"You are muted for {remaining} more second(s).",
                )
                mute_info["warned"] = True  # Mark warning as sent
            return False

        # mute expired — cleanup
        del self.server.muted_users[username]
        return True

    def check_rate_limit(self, client: socket, now: time) -> bool:
        """Checks if the client is sending messages too quickly."""
        interval = self.message_rate_limit["interval"]
        max_msgs = self.message_rate_limit["max_messages"]
        user_history = self.message_rate_limit["user_timestamps"].setdefault(
            client, deque()
        )

        # drop old timestamps outside the interval window
        while user_history and now - user_history[0] > interval:
            user_history.popleft()

        if len(user_history) >= max_msgs:
            self.send_msg_to(
                client,
                ADMIN_MSG,
                f"Rate limit: max {max_msgs} messages every {interval}s. Please slow down.",
            )
            return False

        user_history.append(now)
        return True
