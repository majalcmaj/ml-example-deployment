import os
from logging import Formatter, Logger, LoggerAdapter, StreamHandler, getLogger

from infra.context import CORRELATION_ID


def get_logger(name: str) -> LoggerAdapter[Logger]:
    extra = {"correlation_id": CORRELATION_ID.get()}
    logger = getLogger(name)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    if not logger.handlers:
        syslog = StreamHandler()
        formatter = Formatter(
            "%(asctime)s [%(levelname)s] %(correlation_id)s (%(name)s): %(message)s"
        )
        syslog.setFormatter(formatter)
        logger.addHandler(syslog)

    return LoggerAdapter(logger, extra)
