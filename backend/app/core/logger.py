"""Loguru setup.

Reads LOG_LEVEL / LOG_FORMAT from settings. JSON mode emits one record per
line with full structured fields (ready for Datadog/CloudWatch/Loki). Text
mode keeps a human-friendly format that includes request_id when one is
contextualized — see app/main.py's request_id_middleware.
"""

import os
import sys

from loguru import logger

from app.core.config import settings

LOG_PATH = "logs"
os.makedirs(LOG_PATH, exist_ok=True)

# Format string for text mode. {extra[request_id]} prints "-" when the
# request-id middleware hasn't bound one (e.g. for boot/startup logs).
_TEXT_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | "
    "{extra[request_id]} | {message}"
)


def _patch_request_id(record):
    """Default request_id to '-' when none is contextualized."""
    record["extra"].setdefault("request_id", "-")


logger.remove()
logger.configure(patcher=_patch_request_id)

_use_json = settings.LOG_FORMAT.lower() == "json"

# Console
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL.upper(),
    format="{message}" if _use_json else _TEXT_FORMAT,
    serialize=_use_json,
    backtrace=False,
    diagnose=False,  # don't expose locals in tracebacks (can leak secrets)
)

# File. JSON mode here too so log shippers can parse it.
logger.add(
    f"{LOG_PATH}/app.log",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    level=settings.LOG_LEVEL.upper(),
    format="{message}" if _use_json else _TEXT_FORMAT,
    serialize=_use_json,
    backtrace=False,
    diagnose=False,
)


def get_logger():
    return logger
