from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    mitre: str | None
    description: str
    when: dict[str, Any]


def load_rules(rules_directory: Path) -> list[Rule]:
    rules: list[Rule] = []
    for rule_file in sorted(rules_directory.glob("*.yaml")):
        data = yaml.safe_load(rule_file.read_text(encoding="utf-8")) or []
        if not isinstance(data, list):
            raise ValueError(f"{rule_file.name} must contain a YAML list")
        for raw in data:
            rules.append(Rule(**raw))
    return rules


def event_matches(rule: Rule, event: dict[str, Any]) -> bool:
    for key, wanted in rule.when.items():
        if key.endswith("_contains"):
            field = key.removesuffix("_contains")
            actual = str(event.get(field, "")).casefold()
            if str(wanted).casefold() not in actual:
                return False
        elif str(event.get(key, "")).casefold() != str(wanted).casefold():
            return False
    return True


def evaluate(rules: list[Rule], event: dict[str, Any]) -> list[Rule]:
    return [rule for rule in rules if event_matches(rule, event)]

