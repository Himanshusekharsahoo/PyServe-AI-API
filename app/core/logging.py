import logging
import sys
from app.core.config import LOG_LEVEL


def setup_logging() -> logging.Logger:
    """
    Configure and return a structured logger for the application.
    """
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    log_format = (
        "[%(asctime)s] [%(process)d] [%(levelname)s] "
        "[%(name)s:%(lineno)d] - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger("pyserve")
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger


logger = setup_logging()
