import threading
from concurrent.futures import ThreadPoolExecutor

from config.logging import server_logger


class ClientManager:
    def __init__(self, max_workers=10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}
        self.exit_flags = {}
        self.lock = threading.Lock()

    def register(self, client, handler, *args):
        """Submits a new client handler and tracks its lifecycle."""
        exit_event = threading.Event()

        def wrapped_handler():
            try:
                handler(exit_event, *args)
            finally:
                self.cleanup(client)

        with self.lock:
            self.exit_flags[client] = exit_event
            self.futures[client] = self.executor.submit(wrapped_handler)

    def shutdown(self, client):
        """Signals a single client to shut down."""
        with self.lock:
            if client in self.exit_flags:
                self.exit_flags[client].set()

    def shutdown_all(self):
        """Signals all clients to shut down and stops the thread pool."""
        with self.lock:
            for event in self.exit_flags.values():
                event.set()
            self.exit_flags.clear()
            self.futures.clear()

        self.executor.shutdown(wait=True)

    def cleanup(self, client):
        """Removes tracking info after a client handler exits."""
        with self.lock:
            self.exit_flags.pop(client, None)
            self.futures.pop(client, None)

        self.log_client_threads()

    def log_client_threads(self, info_msg="status check"):
        """Logs how many client handler threads are currently active."""
        active_clients = [
            client
            for client, future in self.futures.items()
            if not future.done() and not future.cancelled()
        ]
        count = len(active_clients)

        server_logger.info(f"[{count}] active client threads after {info_msg}")
