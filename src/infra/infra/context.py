import uuid
from contextvars import ContextVar

CORRELATION_ID = ContextVar("correlation_id", default="-")


def init_context() -> None:
    CORRELATION_ID.set(str(uuid.uuid4()))
