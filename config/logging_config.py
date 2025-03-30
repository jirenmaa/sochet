import logging
from config.settings import SERVER_LOG_FILE, CLIENT_LOG_FILE, LOGGING_FORMAT

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

client_logger.addHandler(client_file_handler)

