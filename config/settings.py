from dotenv import load_dotenv
from os import getenv

load_dotenv()

HOST = getenv("HOST")
PORT = 65432
BUFFER_SIZE = 1024

WHITELIST = getenv("WHITELIST").split(",")

# logging settings
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SERVER_LOG_FILE = "server/logs/server.log"
CLIENT_LOG_FILE = "client/logs/client.log"
