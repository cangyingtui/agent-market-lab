from __future__ import annotations

from typing import Any


DIMENSION_BLOCKERS = {
    "price_acceptance": "价格接受度不足",
    "function_fit": "核心功能匹配不足",
    "brand_loyalty": "品牌信任或偏好不足",
    "social_influence": "口碑与社会认同不足",
}


def _texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def derive_purchase_blockers(
    agent: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> list[str]:
    """Return deterministic, explainable blockers from data already held by a decision."""
    agent = agent or {}
    decision = decision or {}
    blockers = _texts(decision.get("blockers"))

    # Step2 explicitly configured concerns are the strongest non-LLM blocker signal.
    blockers.extend(_texts(agent.get("risk_concerns")))

    scores = decision.get("maut_scores") if isinstance(decision.get("maut_scores"), dict) else {}
    for key, label in DIMENSION_BLOCKERS.items():
        value = scores.get(key)
        if isinstance(value, (int, float)) and float(value) < 0.45:
            blockers.append(label)

    if agent.get("price_sensitivity") == "high" and not any("价格" in item for item in blockers):
        blockers.append("价格敏感，需要更强价格理由或促销支撑")

    if not blockers and decision.get("decision") == "not_buy":
        blockers.append("综合购买意愿不足")

    return list(dict.fromkeys(blockers))[:6]


def enrich_decision_blockers(
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    agent_map = {str(item.get("agent_id")): item for item in agents}
    changed = False
    enriched: list[dict[str, Any]] = []
    for decision in decisions:
        copied = dict(decision)
        blockers = derive_purchase_blockers(agent_map.get(str(copied.get("agent_id"))), copied)
        if blockers != _texts(copied.get("blockers")):
            copied["blockers"] = blockers
            copied["blocker_source"] = "derived_from_saved_inputs"
            changed = True
        enriched.append(copied)
    return enriched, changed

