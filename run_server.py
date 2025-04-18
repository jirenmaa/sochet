import signal
import sys

from config.logging import server_logger as logger
from config.settings import makefile
from server.server import Server

if __name__ == "__main__":
    # create the databases file
    makefile()

    server = Server()

    def signal_handler(sig, frame):
        server.stop_connection()
        logger.warning("Exiting application...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        """
        Sample user (username - password)
            admin   - admin
            jack    - admin
            actor-1 - actor1
            actor-2 - actor2

        server.create_user("username", "password", "role")
        """
        server.start_connection()
    except Exception as e:
        logger.error(f"Server encountered an error: {e}")
        server.stop_connection()
