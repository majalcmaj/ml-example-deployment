from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from infra.context import CORRELATION_ID
from infra.metrics import MetricsCollector

if TYPE_CHECKING:
    from collections.abc import Mapping


class _StubSink:
    def __init__(self) -> None:
        self.batches: list[dict[str, object]] = []

    def send(self, metrics: Mapping[str, object]) -> None:
        self.batches.append(dict(metrics))


def test_record_and_exit_sends_batch_with_auto_fields() -> None:
    sink = _StubSink()
    with MetricsCollector(sink) as metrics:
        metrics.record("rows", 42)

    assert len(sink.batches) == 1
    batch = sink.batches[0]
    assert batch["rows"] == 42
    assert cast("float", batch["total_duration_seconds"]) >= 0
    assert batch["correlation_id"] == CORRELATION_ID.get()
    assert set(batch) == {"rows", "total_duration_seconds", "correlation_id"}


def test_timer_records_duration_and_runs_block() -> None:
    sink = _StubSink()
    calls: list[str] = []
    with MetricsCollector(sink) as metrics, metrics.timer("step_seconds"):
        calls.append("ran")

    assert calls == ["ran"]
    assert cast("float", sink.batches[0]["step_seconds"]) >= 0


def test_timer_records_and_reraises_on_exception() -> None:
    sink = _StubSink()
    with (
        pytest.raises(ValueError, match="boom"),
        MetricsCollector(sink) as metrics,
        metrics.timer("step_seconds"),
    ):
        raise ValueError("boom")

    assert "step_seconds" in sink.batches[0]


def test_correlation_id_read_live_at_exit() -> None:
    sink = _StubSink()
    token = CORRELATION_ID.set("initial")
    try:
        with MetricsCollector(sink) as metrics:
            metrics.record("rows", 1)
            CORRELATION_ID.set("updated-mid-run")
    finally:
        CORRELATION_ID.reset(token)

    assert sink.batches[0]["correlation_id"] == "updated-mid-run"


def test_exit_calls_send_exactly_once() -> None:
    sink = _StubSink()
    with MetricsCollector(sink) as metrics:
        metrics.record("a", 1)
        metrics.record("b", 2)

    assert len(sink.batches) == 1
