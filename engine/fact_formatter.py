from __future__ import annotations

from typing import Any


PROMPT_VERSION = "fact_formatter_v0.1"


def compact_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": item.get("source"),
        "source_type": item.get("source_type"),
        "score": item.get("score"),
        "snippet": str(item.get("snippet") or "")[:220],
        "matched_fields": item.get("matched_fields") or [],
    }


def format_evidence_for_engine(evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    structured: list[dict[str, Any]] = []
    user_profile: list[dict[str, Any]] = []
    market: list[dict[str, Any]] = []
    for group, items in evidence.items():
        for item in items:
            row = compact_item(item)
            row["evidence_group"] = group
            if item.get("source_type") == "product_competitor":
                structured.append(row)
            elif item.get("source_type") == "user_profile":
                user_profile.append(row)
            else:
                market.append(row)
    return {
        "prompt_version": PROMPT_VERSION,
        "structured_product_evidence": structured[:10],
        "user_profile_evidence": user_profile[:12],
        "market_strategy_evidence": market[:8],
        "counts": {
            "structured_product_evidence": len(structured),
            "user_profile_evidence": len(user_profile),
            "market_strategy_evidence": len(market),
        },
    }
