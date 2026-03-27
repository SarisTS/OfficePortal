from loguru import logger
import sys
import os

LOG_PATH = "logs"

os.makedirs(LOG_PATH, exist_ok=True)

logger.remove()

# Console logging
logger.add(
    sys.stdout,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# File logging
logger.add(
    f"{LOG_PATH}/app.log",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    level="INFO"
)

def get_logger():
    return logger