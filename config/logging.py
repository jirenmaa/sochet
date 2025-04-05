import logging

from config.settings import CLIENT_LOG_FILE, LOGGING_FORMAT, SERVER_LOG_FILE

logging.basicConfig(
    filename=SERVER_LOG_FILE,
    level=logging.INFO,
    format=LOGGING_FORMAT
)

server_logger = logging.getLogger(f"[SERVER] - {__name__}")

# slient logger (Separate Logger)
client_logger = logging.getLogger(f"[CLIENT] - {__name__}")
client_logger.setLevel(logging.INFO)

# create a file handler for the client logger
client_file_handler = logging.FileHandler(CLIENT_LOG_FILE)
client_file_handler.setFormatter(logging.Formatter(LOGGING_FORMAT))

# prevent propagation to the root logger (server logger)
client_logger.propagate = False

# clear inherited handlers (optional but safe)
client_logger.handlers = []
client_logger.addHandler(client_file_handler)

