from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class StubMetricsSink:
    def __init__(self) -> None:
        self.batches: list[dict[str, object]] = []

    def send(self, metrics: Mapping[str, object]) -> None:
        self.batches.append(dict(metrics))
