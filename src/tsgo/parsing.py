"""Small JSON parsing helpers for Pipeline v0.2.

The first concrete runner should tolerate common LLM output wrappers such as
Markdown code fences while keeping the orchestration layer schema-driven.
"""

from __future__ import annotations

import json
import re
from typing import Any


class JsonParseError(ValueError):
    """Raised when text cannot be parsed into the expected JSON object."""


def extract_json_candidate(text: str) -> str:
    """Extract the most likely JSON object or array from raw model text."""

    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    array_start = stripped.find("[")
    array_end = stripped.rfind("]")

    object_candidate = ""
    if object_start != -1 and object_end > object_start:
        object_candidate = stripped[object_start : object_end + 1]

    array_candidate = ""
    if array_start != -1 and array_end > array_start:
        array_candidate = stripped[array_start : array_end + 1]

    if object_candidate and array_candidate:
        return object_candidate if object_start < array_start else array_candidate
    if object_candidate:
        return object_candidate
    if array_candidate:
        return array_candidate
    return stripped


def parse_json(text: str) -> Any:
    """Parse raw text into JSON, with light extraction from Markdown wrappers."""

    candidate = extract_json_candidate(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JsonParseError(f"无法解析 JSON：{exc.msg}") from exc


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse raw text into a JSON object."""

    parsed = parse_json(text)
    if not isinstance(parsed, dict):
        raise JsonParseError("期望 JSON object，但解析结果不是 dict。")
    return parsed


def parse_json_list(text: str) -> list[Any]:
    """Parse raw text into a JSON array."""

    parsed = parse_json(text)
    if not isinstance(parsed, list):
        raise JsonParseError("期望 JSON array，但解析结果不是 list。")
    return parsed
