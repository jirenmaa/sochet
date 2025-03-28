import logging
from config.settings import LOG_FILE, LOGGING_FORMAT

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format=LOGGING_FORMAT
)

logger = logging.getLogger(__name__)
