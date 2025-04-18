import json
from os import getenv, path
from typing import List, Union

from dotenv import load_dotenv

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
USER_DB = path.join(ROOT_PATH, "server", "data", getenv("USER_DB"))
MESSAGE_DB = path.join(ROOT_PATH, "server", "data", getenv("MESSAGE_DB"))
BANNED_USER_DB = path.join(ROOT_PATH, "server", "data", getenv("BANNED_USER_DB"))


def makefile(filepath: Union[str, List[str]] = []):
    """
    Ensures one or more files exist; creates them if their parent directory exists but the file does not.
    Skips creation if the directory is missing or the file already exists.
    """
    paths = [filepath] if isinstance(filepath, str) else filepath
    paths.extend([USER_DB, MESSAGE_DB, BANNED_USER_DB])

    for file in paths:
        if not isinstance(file, str):
            continue  # skip invalid types

        if path.isfile(file):
            continue

        dir_path = path.dirname(file)
        if not path.isdir(dir_path):
            print(f"Directory for '{file}' does not exist. Skipping file creation.")
            continue

        with open(file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)
        print(f"{path.basename(file)} created with empty list.")
