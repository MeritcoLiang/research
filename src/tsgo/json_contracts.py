"""Structured JSON contracts for Pipeline v0.3 LLM-backed operators.

The functions in this module convert raw model JSON into the internal schema
objects used by the orchestration pipeline. They intentionally accept a small
amount of shape variation so v0.3 can tolerate common LLM output drift while
still keeping every operator schema-driven.
"""

from __future__ import annotations

from typing import Any

from .parsing import JsonParseError, parse_json_object
from .schema import Claim, ClaimType, Score


CLAIM_TYPES: set[str] = {
    "fact",
    "reasoning",
    "recommendation",
    "assumption",
    "calculation",
    "code",
    "risk",
    "unknown",
}


def parse_generate_packet(raw_text: str) -> list[str]:
    """Parse GenerateOperator output into candidate drafts."""

    obj = parse_json_object(raw_text)
    branches = obj.get("branches", [])
    if isinstance(branches, str):
        return [branches]
    if not isinstance(branches, list):
        raise JsonParseError("GenerateOperator 输出缺少 list 字段：branches。")

    drafts: list[str] = []
    for item in branches:
        if isinstance(item, str):
            draft = item.strip()
        elif isinstance(item, dict):
            draft = str(item.get("draft", "")).strip()
        else:
            draft = ""
        if draft:
            drafts.append(draft)
    if not drafts:
        raise JsonParseError("GenerateOperator 没有返回任何非空 draft。")
    return drafts


def parse_normalize_packet(raw_text: str) -> dict[str, Any]:
    """Parse NormalizeOperator output into summary/claims/assumptions/risks."""

    obj = parse_json_object(raw_text)
    return {
        "summary": str(obj.get("summary", "")).strip(),
        "claims": parse_claims(obj.get("claims", [])),
        "assumptions": _string_list(obj.get("assumptions", [])),
        "missing_info": _string_list(obj.get("missing_info", [])),
        "failure_modes": _string_list(obj.get("risks", obj.get("failure_modes", []))),
    }


def parse_score_packets(raw_text: str, *, weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Parse ScoreOperator output into score packets.

    Each packet contains an optional `state_id`, a `Score`, and critique arrays.
    """

    obj = parse_json_object(raw_text)
    raw_scores = obj.get("scores", [])
    if isinstance(raw_scores, dict):
        raw_scores = [raw_scores]
    if not isinstance(raw_scores, list):
        raise JsonParseError("ScoreOperator 输出缺少 list 字段：scores。")

    packets: list[dict[str, Any]] = []
    for raw in raw_scores:
        if not isinstance(raw, dict):
            continue
        score = Score(
            correctness=_float01(raw.get("correctness", raw.get("accuracy", 0.0))),
            completeness=_float01(raw.get("completeness", 0.0)),
            relevance=_float01(raw.get("relevance", 0.0)),
            clarity=_float01(raw.get("clarity", 0.0)),
            groundedness=_float01(raw.get("groundedness", 0.0)),
            safety=_float01(raw.get("safety", 1.0)),
            novelty=_float01(raw.get("novelty", 0.0)),
            actionability=_float01(raw.get("actionability", 0.0)),
            overall=_float01(raw.get("overall", 0.0)),
            notes=_string_list(raw.get("notes", [])),
        )
        if score.overall == 0.0 and weights:
            score.recompute_overall(weights)
        packets.append(
            {
                "state_id": str(raw.get("state_id", "")),
                "score": score,
                "strengths": _string_list(raw.get("strengths", [])),
                "weaknesses": _string_list(raw.get("weaknesses", [])),
                "critical_errors": _string_list(raw.get("critical_errors", [])),
                "improvement_instructions": _string_list(raw.get("improvement_instructions", [])),
            }
        )
    if not packets:
        raise JsonParseError("ScoreOperator 没有返回任何有效 score packet。")
    return packets


def parse_improve_packet(raw_text: str) -> dict[str, Any]:
    """Parse ImproveOperator output."""

    obj = parse_json_object(raw_text)
    draft = str(obj.get("draft", "")).strip()
    if not draft:
        raise JsonParseError("ImproveOperator 输出缺少非空 draft。")
    return {
        "draft": draft,
        "change_summary": _string_list(obj.get("change_summary", obj.get("changes", []))),
        "removed_claims": _string_list(obj.get("removed_claims", [])),
        "added_claims": _string_list(obj.get("added_claims", [])),
    }


def parse_aggregate_packet(raw_text: str) -> dict[str, Any]:
    """Parse AggregateOperator output."""

    obj = parse_json_object(raw_text)
    draft = str(obj.get("draft", "")).strip()
    if not draft:
        raise JsonParseError("AggregateOperator 输出缺少非空 draft。")
    return {
        "draft": draft,
        "selected_claims": parse_claims(obj.get("selected_claims", obj.get("claims", []))),
        "conflicts": _string_list(obj.get("conflicts", [])),
        "resolutions": _string_list(obj.get("resolutions", [])),
        "aggregation_policy": str(obj.get("aggregation_policy", "claim_level_weighted_merge")),
    }


def parse_validation_packet(raw_text: str) -> dict[str, Any]:
    """Parse ValidateOperator output."""

    obj = parse_json_object(raw_text)
    return {
        "pass": bool(obj.get("pass", obj.get("passed", False))),
        "blocking_issues": _string_list(obj.get("blocking_issues", [])),
        "non_blocking_issues": _string_list(obj.get("non_blocking_issues", [])),
        "required_edits": _string_list(obj.get("required_edits", [])),
        "confidence": _float01(obj.get("confidence", 0.0)),
    }


def parse_claims(raw_claims: Any) -> list[Claim]:
    """Coerce arbitrary JSON claim arrays into `Claim` objects."""

    if isinstance(raw_claims, str):
        raw_claims = [raw_claims]
    if not isinstance(raw_claims, list):
        return []

    claims: list[Claim] = []
    for raw in raw_claims:
        if isinstance(raw, str):
            text = raw.strip()
            claim_type: ClaimType = "unknown"
            confidence = None
            evidence_ids: list[str] = []
            verifier_notes: list[str] = []
        elif isinstance(raw, dict):
            text = str(raw.get("text", raw.get("claim", ""))).strip()
            claim_type = _claim_type(raw.get("claim_type", raw.get("type", "unknown")))
            confidence = _maybe_float01(raw.get("confidence"))
            evidence_ids = _string_list(raw.get("evidence_ids", []))
            verifier_notes = _string_list(raw.get("verifier_notes", []))
        else:
            continue
        if text:
            claims.append(
                Claim(
                    text=text,
                    claim_type=claim_type,
                    confidence=confidence,
                    evidence_ids=evidence_ids,
                    verifier_notes=verifier_notes,
                )
            )
    return claims


def _claim_type(value: Any) -> ClaimType:
    text = str(value).strip()
    if text in CLAIM_TYPES:
        return text  # type: ignore[return-value]
    return "unknown"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return [str(value)]
    return [str(item) for item in value if str(item)]


def _maybe_float01(value: Any) -> float | None:
    if value is None:
        return None
    return _float01(value)


def _float01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))
