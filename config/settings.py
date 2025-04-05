from os import getenv, path

from dotenv import load_dotenv

from config.utils import makefile

load_dotenv()

HOST = getenv("HOST")
PORT = 65432
BUFFER_SIZE = 1024

WHITELIST = getenv("WHITELIST").split(",")

# logging settings
LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SERVER_LOG_FILE = "server/logs/server.log"
CLIENT_LOG_FILE = "client/logs/client.log"

ROOT_PATH = path.join(path.dirname(path.abspath(__name__)))
USER_DB = path.join(ROOT_PATH, "server", "database", getenv("USER_DB"))
MESSAGE_DB = path.join(ROOT_PATH, "server", "database", getenv("MESSAGE_DB"))

# create the databases file
makefile([USER_DB, MESSAGE_DB])
