from __future__ import annotations

from collections.abc import Iterable
from typing import Any


ANCHOR_PROFILES: dict[str, set[str]] = {
    "v0.1": {"text", "missing", "risk", "context"},
    "v0.1.1": {"text", "missing", "risk", "context"},
    "v0.2": {"text", "missing", "risk", "context", "semantic_candidate", "semantic", "escalation"},
    "v0.3": {"text", "missing", "risk", "context", "semantic_candidate", "semantic", "escalation", "obligation", "relation"},
    "v1.0": {"text", "missing", "risk", "context", "semantic_candidate", "semantic", "escalation", "obligation", "relation", "action"},
}

ANCHOR_ALIASES = {
    "text_anchor": "text",
    "missing_anchor": "missing",
    "risk_anchor": "risk",
    "context_anchor": "context",
    "semantic_anchor": "semantic",
    "semantic_candidate_anchor": "semantic_candidate",
    "escalation_anchor": "escalation",
    "obligation_anchor": "obligation",
    "relation_anchor": "relation",
    "action_anchor": "action",
}


def infer_anchor_profile(ruleset: str | None) -> str:
    ruleset_name = str(ruleset or "rules_v0.1").lower()
    if "v1" in ruleset_name:
        return "v1.0"
    if "v0.3" in ruleset_name:
        return "v0.3"
    if "v0.2" in ruleset_name:
        return "v0.2"
    if "v0.1.1" in ruleset_name:
        return "v0.1.1"
    return "v0.1"


def resolve_anchor_capabilities(
    *,
    ruleset: str | None = None,
    anchor_profile: str | None = None,
    enabled_anchors: str | Iterable[str] | None = None,
) -> dict[str, Any]:
    profile = _normalize_profile(anchor_profile) or infer_anchor_profile(ruleset)
    allowed = set(ANCHOR_PROFILES.get(profile) or ANCHOR_PROFILES["v0.1"])
    requested = _parse_enabled_anchors(enabled_anchors)
    enabled = set(allowed) if not requested else allowed & requested
    if "semantic" in enabled:
        enabled.add("semantic_candidate")
    ignored = sorted(requested - allowed)
    return {
        "profile": profile,
        "version": profile.removeprefix("v"),
        "allowed_anchors": sorted(allowed),
        "enabled_anchors": sorted(enabled),
        "disabled_anchors": sorted(allowed - enabled),
        "ignored_anchors": ignored,
    }


def anchor_enabled(capabilities: dict[str, Any], anchor_type: str) -> bool:
    return _normalize_anchor(anchor_type) in set(capabilities.get("enabled_anchors") or [])


def _normalize_profile(profile: str | None) -> str | None:
    if not profile:
        return None
    normalized = str(profile).strip().lower().replace("_", ".")
    if normalized in ANCHOR_PROFILES:
        return normalized
    if normalized in {"0.1", "0.1.1", "0.2", "0.3", "1", "1.0"}:
        return f"v{normalized}" if normalized != "1" else "v1.0"
    return None


def _parse_enabled_anchors(value: str | Iterable[str] | None) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace("|", ",").split(",")
    else:
        raw_items = list(value)
    anchors = {_normalize_anchor(item) for item in raw_items if str(item or "").strip()}
    anchors.discard("")
    return anchors


def _normalize_anchor(value: Any) -> str:
    anchor = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ANCHOR_ALIASES.get(anchor, anchor)
