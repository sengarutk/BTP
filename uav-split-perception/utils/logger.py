"""Logging with millisecond timestamps, a SUCCESS level, and colour on terminals."""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

SUCCESS_LEVEL_NUM = 25  # between INFO and WARNING
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")


def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)


logging.Logger.success = success


class HighPrecisionFormatter(logging.Formatter):
    """``[time.ms] [LEVEL] [name] message``, coloured when ``use_color``."""

    COLOR_RESET = "\033[0m"
    COLOR_DEBUG = "\033[35m"
    COLOR_INFO = "\033[36m"
    COLOR_SUCCESS = "\033[1;32m"
    COLOR_WARNING = "\033[1;33m"
    COLOR_ERROR = "\033[1;31m"
    COLOR_CRITICAL = "\033[1;41m"
    COLOR_TAG = "\033[1;34m"
    COLOR_TIME = "\033[90m"

    LEVEL_COLORS = {
        logging.DEBUG: COLOR_DEBUG,
        logging.INFO: COLOR_INFO,
        SUCCESS_LEVEL_NUM: COLOR_SUCCESS,
        logging.WARNING: COLOR_WARNING,
        logging.ERROR: COLOR_ERROR,
        logging.CRITICAL: COLOR_CRITICAL,
    }

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def formatTime(self, record, datefmt=None):
        ct = datetime.fromtimestamp(record.created)
        return ct.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def format(self, record):
        timestamp = self.formatTime(record)
        level_name = record.levelname
        module_name = record.name
        message = record.getMessage()

        if self.use_color:
            color = self.LEVEL_COLORS.get(record.levelno, self.COLOR_RESET)
            formatted = (
                f"{self.COLOR_TIME}[{timestamp}]{self.COLOR_RESET} "
                f"{color}[{level_name:<7}]{self.COLOR_RESET} "
                f"{self.COLOR_TAG}[{module_name}]{self.COLOR_RESET} "
                f"{message}"
            )
        else:
            formatted = f"[{timestamp}] [{level_name:<7}] [{module_name}] {message}"

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                formatted += "\n" + record.exc_text

        return formatted


def setup_logger(
    name: str = "UAV-SplitPerception",
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    propagate: bool = False,
) -> logging.Logger:
    """(Re)configures ``name`` to log to stdout and, if given, to ``log_file`` without colour."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = propagate

    # Replace only the handlers this module installed, so repeated calls neither
    # duplicate output nor discard handlers that the application configured.
    for h in list(logger.handlers):
        if getattr(h, "_aegis_handler", False):
            logger.removeHandler(h)

    use_color = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler._aegis_handler = True
    console_handler.setLevel(level)
    console_handler.setFormatter(HighPrecisionFormatter(use_color=use_color))
    logger.addHandler(console_handler)

    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler._aegis_handler = True
        file_handler.setLevel(level)
        file_handler.setFormatter(HighPrecisionFormatter(use_color=False))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "UAV-SplitPerception", log_file: Optional[str] = None) -> logging.Logger:
    """Returns a configured logger; configures it only on first use (or when log_file is given)."""
    existing = logging.getLogger(name)
    if log_file is None and any(getattr(h, "_aegis_handler", False) for h in existing.handlers):
        return existing
    level = logging.getLevelName(os.environ.get("AEGIS_LOG_LEVEL", "INFO").upper())
    return setup_logger(name=name, log_file=log_file, level=level if isinstance(level, int) else logging.INFO)
