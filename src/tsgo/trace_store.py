"""Trace persistence utilities for Pipeline v0.2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .schema import Trace


class TraceSink(Protocol):
    """Persistence interface for pipeline traces."""

    def write(self, trace: Trace) -> Path:
        """Persist a trace and return the written path."""


@dataclass(slots=True)
class JsonlTraceSink:
    """Append traces to a local JSONL file."""

    path: Path

    def write(self, trace: Trace) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace.to_dict(), ensure_ascii=False, default=str))
            handle.write("\n")
        return self.path


@dataclass(slots=True)
class JsonTraceSink:
    """Write the latest trace as a pretty-printed JSON file."""

    path: Path

    def write(self, trace: Trace) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(trace.to_dict(), handle, ensure_ascii=False, indent=2, default=str)
        return self.path
