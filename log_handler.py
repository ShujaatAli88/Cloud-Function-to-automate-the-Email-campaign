# log_handler.py

from loguru import logger
import sys
import os

def setup_logger(log_file="run.log", overwrite=True):
    # Remove any existing handlers (including default one)
    logger.remove()

    # Optional: remove old file if overwriting
    if overwrite and os.path.exists(log_file):
        os.remove(log_file)

    # Format with colors
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Console output
    logger.add(sys.stdout, format=log_format, level="DEBUG", colorize=True)

    # File output
    logger.add(log_file, format=log_format, level="DEBUG", colorize=False)

    return logger
