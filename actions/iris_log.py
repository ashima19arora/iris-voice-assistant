"""Shared iris logger — INFO for flow, WARNING for rejections, ERROR for failures."""
import logging
import sys

LOGGER_NAME = "iris"


def get_logger() -> logging.Logger:
    log = logging.getLogger(LOGGER_NAME)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log
