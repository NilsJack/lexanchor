from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.services.anchor_capabilities import resolve_anchor_capabilities


class RuleLoader:
    def __init__(self, rules_dir: Path) -> None:
        self.rules_dir = rules_dir

    def list_rulesets(self) -> list[dict[str, Any]]:
        rulesets = []
        for path in sorted(self.rules_dir.glob("*.yaml")):
            data = self._load_yaml(path)
            try:
                rules = self.load_rules(path.stem)
            except Exception:
                rules = data.get("rules", []) if isinstance(data, dict) else []
            rulesets.append(
                {
                    "ruleset": path.stem,
                    "path": str(path),
                    "version": str(data.get("version") or "0.1") if isinstance(data, dict) else "0.1",
                    "extends": data.get("extends") if isinstance(data, dict) else None,
                    "rule_count": len(rules),
                }
            )
        return rulesets

    def load_rules(self, ruleset: str = "rules_v0.1", industry_id: str | None = None, org_id: str | None = None) -> list[dict[str, Any]]:
        rules = self._load_base_rules(ruleset, seen=set())

        if industry_id:
            industry_path = self.rules_dir / "industry_configs" / f"{industry_id}.yaml"
            if industry_path.exists():
                rules = self._merge_rules(rules, (self._load_yaml(industry_path) or {}).get("rules") or [])

        if org_id:
            org_path = self.rules_dir / "org_configs" / f"{org_id}.yaml"
            if org_path.exists():
                rules = self._merge_rules(rules, (self._load_yaml(org_path) or {}).get("rules") or [])

        return [rule for rule in rules if rule.get("enabled", True)]

    def _load_base_rules(self, ruleset: str, *, seen: set[str]) -> list[dict[str, Any]]:
        if ruleset in seen:
            raise ValueError(f"Circular ruleset inheritance: {ruleset}")
        seen.add(ruleset)
        base_path = self.rules_dir / f"{ruleset}.yaml"
        if not base_path.exists():
            raise FileNotFoundError(f"Ruleset not found: {ruleset}")

        data = self._load_yaml(base_path)
        parent = str((data or {}).get("extends") or "").strip()
        rules = self._load_base_rules(parent, seen=seen) if parent else []
        return self._merge_rules(rules, list((data or {}).get("rules") or []))

    def describe_ruleset(self, ruleset: str = "rules_v0.1", industry_id: str | None = None, org_id: str | None = None) -> dict[str, Any]:
        ruleset_path = self.rules_dir / f"{ruleset}.yaml"
        data = self._load_yaml(ruleset_path) if ruleset_path.exists() else {}
        rules = self.load_rules(ruleset=ruleset, industry_id=industry_id, org_id=org_id)
        capabilities = resolve_anchor_capabilities(ruleset=ruleset)
        rule_anchor_types = sorted({self._anchor_type_for_rule(rule) for rule in rules})
        return {
            "ruleset": ruleset,
            "version": str(data.get("version") or "0.1"),
            "extends": data.get("extends"),
            "rule_count": len(rules),
            "anchor_capabilities": capabilities,
            "enabled_anchor_types": capabilities["enabled_anchors"],
            "rule_anchor_types": rule_anchor_types,
            "rules": rules,
        }

    @staticmethod
    def _merge_rules(base_rules: list[dict[str, Any]], overlay_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = list(base_rules)
        positions = {str(rule.get("rule_id")): index for index, rule in enumerate(merged)}
        for overlay_rule in overlay_rules:
            rule_id = str(overlay_rule.get("rule_id") or "").strip()
            if not rule_id:
                continue
            if rule_id in positions:
                merged[positions[rule_id]] = overlay_rule
            else:
                positions[rule_id] = len(merged)
                merged.append(overlay_rule)
        return merged

    @staticmethod
    def _anchor_type_for_rule(rule: dict[str, Any]) -> str:
        rule_type = str(rule.get("type") or "keyword")
        if rule_type == "missing":
            return "missing"
        if rule_type == "obligation":
            return "obligation"
        if rule_type == "relation":
            return "relation"
        if rule.get("requires_llm") or rule_type == "semantic":
            return "semantic"
        return "text"

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle) or {}
        return data if isinstance(data, dict) else {}
