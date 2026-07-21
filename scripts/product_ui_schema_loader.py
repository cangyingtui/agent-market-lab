from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_SCHEMA_PATH = PROJECT_ROOT / "data_seed" / "product_field_ui_schemas.json"


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "")


@lru_cache(maxsize=1)
def load_ui_schema_payload() -> dict[str, Any]:
    if not UI_SCHEMA_PATH.exists():
        return {"default_hint": "", "rules": []}
    return json.loads(UI_SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_ui_schema_rules() -> dict[tuple[str, str, str], dict[str, Any]]:
    payload = load_ui_schema_payload()
    default_hint = payload.get("default_hint") or ""
    rules: dict[tuple[str, str, str], dict[str, Any]] = {}
    for category_rule in payload.get("rules", []):
        category = _normalize(category_rule.get("category"))
        subcategory = _normalize(category_rule.get("subcategory"))
        fields = category_rule.get("fields") if isinstance(category_rule.get("fields"), dict) else {}
        for field_name, schema in fields.items():
            if not isinstance(schema, dict):
                continue
            normalized = copy.deepcopy(schema)
            normalized.setdefault("hint", default_hint)
            rules[(category, subcategory, _normalize(field_name))] = normalized
    return rules


def schema_for_field(category: str, subcategory: str, field_name: str) -> dict[str, Any] | None:
    schema = load_ui_schema_rules().get((_normalize(category), _normalize(subcategory), _normalize(field_name)))
    return copy.deepcopy(schema) if schema else None

