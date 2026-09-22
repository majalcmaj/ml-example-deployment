from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Protocol

from infra.context import CORRELATION_ID
from infra.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping
    from logging import Logger, LoggerAdapter
    from types import TracebackType
    from typing import Self

MetricValue = float | int | str


class MetricsSink(Protocol):
    def send(self, metrics: Mapping[str, MetricValue]) -> None: ...


class LoggingMetricsSink:
    def __init__(self, log: LoggerAdapter[Logger] | None = None) -> None:
        self._log = log or get_logger(__name__)

    def send(self, metrics: Mapping[str, MetricValue]) -> None:
        self._log.info("Metrics batch: %s", dict(metrics))


class MetricsCollector:
    def __init__(self, sink: MetricsSink) -> None:
        self._sink = sink
        self._metrics: dict[str, MetricValue] = {}
        self._start: float | None = None

    def record(self, name: str, value: MetricValue) -> None:
        self._metrics[name] = value

    @contextmanager
    def timer(self, name: str) -> Generator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - start)

    def __enter__(self) -> Self:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._start is not None:
            self._metrics["total_duration_seconds"] = time.perf_counter() - self._start
        self._metrics["correlation_id"] = CORRELATION_ID.get()
        self._sink.send(self._metrics)
