from logging import Logger, LoggerAdapter, getLogger, StreamHandler, Formatter, INFO
from common.context import CORRELATION_ID


def get_logger(name: str) -> LoggerAdapter[Logger]:
    extra = {"correlation_id": CORRELATION_ID.get()}
    logger = getLogger(name)
    syslog = StreamHandler()
    formatter = Formatter(
        "%(asctime)s [%(levelname)s] %(correlation_id)s (%(name)s): %(message)s"
    )
    syslog.setFormatter(formatter)
    logger.setLevel(INFO)
    logger.addHandler(syslog)

    return LoggerAdapter(logger, extra)
