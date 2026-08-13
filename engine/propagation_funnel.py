from __future__ import annotations

from typing import Any

from engine.maut_model import clamp, safe_float


MODEL_VERSION = "marketing_compartment_v1"
FISSION_KEYWORDS = ("情侣", "送礼", "礼物", "分享", "闺蜜", "家庭", "纪念日")


def _scene_text(market: dict[str, Any]) -> tuple[list[str], str]:
    tags = [str(item).strip() for item in market.get("scene_tags") or [] if str(item).strip()]
    scenes = market.get("scenes") if isinstance(market.get("scenes"), list) else []
    parts = [str(market.get("scene") or ""), *tags]
    for item in scenes:
        if isinstance(item, dict):
            parts.append(str(item.get("name") or item.get("scene") or ""))
        else:
            parts.append(str(item))
    return tags, " ".join(parts)


def _sentiment_from_distribution(distribution: dict[str, int]) -> dict[str, float]:
    """Compute sentiment percentages from a decision label distribution (buy/consider/not_buy counts)."""
    total = sum(distribution.values())
    if total <= 0:
        return {"positive": 0.0, "neutral": 100.0, "negative": 0.0}
    positive = distribution.get("buy", 0)
    neutral = distribution.get("consider", 0)
    negative = distribution.get("not_buy", 0)
    return {
        "positive": round(positive * 100 / total, 1),
        "neutral": round(neutral * 100 / total, 1),
        "negative": round(negative * 100 / total, 1),
    }


def _sentiment(decisions: list[dict[str, Any]]) -> dict[str, float]:
    """Legacy sentiment from flat decision list (used when no per-round data available)."""
    totals = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
    total_weight = 0.0
    for decision in decisions:
        weight = max(0.0, safe_float(decision.get("sample_weight"), 1.0))
        score = clamp(safe_float(decision.get("purchase_intent_score"), 0.5))
        label = str(decision.get("decision") or "")
        bucket = "positive" if label == "buy" else "negative" if label == "not_buy" else "neutral"
        totals[bucket] += weight
        total_weight += weight
    if total_weight <= 0:
        return {"positive": 0.0, "neutral": 100.0, "negative": 0.0}
    return {key: round(value * 100 / total_weight, 1) for key, value in totals.items()}


def build_propagation_funnel(
    snapshot: dict[str, Any],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    social_simulation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = snapshot.get("simulation_params") if isinstance(snapshot.get("simulation_params"), dict) else {}
    configured = snapshot.get("social_propagation_config")
    if not isinstance(configured, dict):
        configured = {}
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    tags, scene_text = _scene_text(market)
    keyword_fission = any(keyword in scene_text for keyword in FISSION_KEYWORDS)
    fission_factor = clamp(safe_float(configured.get("scene_fission_factor"), 1.25 if keyword_fission else 1.0), 0.5, 2.0)
    sample_size = max(1, int(safe_float(params.get("sample_size"), len(agents) or 1000)))
    external_per_round = max(0, int(safe_float(configured.get("external_traffic_per_round"), max(20, sample_size * 0.05))))
    rounds = max(1, int((social_simulation or {}).get("rounds_executed") or configured.get("max_rounds") or 3))
    round_summaries = (social_simulation or {}).get("round_summaries") if isinstance((social_simulation or {}).get("round_summaries"), list) else []
    # Base sentiment from final decisions (used for compartment model rate calibration only)
    base_sentiment = _sentiment(decisions)
    avg_intent = sum(
        safe_float(item.get("purchase_intent_score"), 0.5) * max(safe_float(item.get("sample_weight"), 1.0), 0.0)
        for item in decisions
    ) / max(sum(max(safe_float(item.get("sample_weight"), 1.0), 0.0) for item in decisions), 1.0)
    exposure_to_interest = clamp(safe_float(configured.get("exposure_to_interest_rate"), 0.22 + 0.30 * avg_intent), 0.01, 0.95)
    interest_to_purchase = clamp(safe_float(configured.get("interest_to_purchase_rate"), 0.12 + 0.38 * avg_intent), 0.01, 0.95)
    purchase_to_recommend = clamp(
        safe_float(configured.get("purchase_to_recommend_rate"), 0.08 + base_sentiment["positive"] / 500) * fission_factor,
        0.01,
        0.90,
    )
    negative_attrition = clamp(safe_float(configured.get("negative_attrition_rate"), 0.04 + base_sentiment["negative"] / 500), 0.0, 0.50)

    states = {
        "未曝光": round(sample_size * 0.60, 1),
        "已曝光": round(sample_size * 0.40, 1),
        "感兴趣": 0.0,
        "已购买": 0.0,
        "主动推荐": 0.0,
        "放弃/负面": 0.0,
    }
    round_rows: list[dict[str, Any]] = []
    link_totals: dict[tuple[str, str], float] = {}

    def add_link(source: str, target: str, value: float) -> None:
        link_totals[(source, target)] = link_totals.get((source, target), 0.0) + max(0.0, value)

    for round_number in range(1, rounds + 1):
        organic = min(states["未曝光"], states["主动推荐"] * 0.20 * fission_factor)
        external = float(external_per_round)
        newly_exposed = external + organic
        states["未曝光"] = max(0.0, states["未曝光"] - organic)
        states["已曝光"] += newly_exposed
        interested = states["已曝光"] * exposure_to_interest
        negative = (states["已曝光"] - interested) * negative_attrition
        states["已曝光"] = max(0.0, states["已曝光"] - interested - negative)
        states["感兴趣"] += interested
        purchased = states["感兴趣"] * interest_to_purchase
        states["感兴趣"] -= purchased
        states["已购买"] += purchased
        recommended = purchased * purchase_to_recommend
        states["主动推荐"] += recommended
        states["放弃/负面"] += negative
        add_link("外部流量", "已曝光", external)
        add_link("主动推荐", "已曝光", organic)
        add_link("已曝光", "感兴趣", interested)
        add_link("已曝光", "放弃/负面", negative)
        add_link("感兴趣", "已购买", purchased)
        add_link("已购买", "主动推荐", recommended)
        # Per-round sentiment: use round_summaries if available, otherwise fallback to base
        round_index = round_number - 1
        if round_index < len(round_summaries):
            summary = round_summaries[round_index] if isinstance(round_summaries[round_index], dict) else {}
            dist = summary.get("decision_weighted_distribution") or summary.get("decision_distribution") or {}
            round_sentiment = _sentiment_from_distribution(dist)
        else:
            round_sentiment = dict(base_sentiment)
        round_rows.append(
            {
                "round": round_number,
                "external_traffic": round(external, 1),
                "organic_referral_traffic": round(organic, 1),
                "states": {key: round(value, 1) for key, value in states.items()},
                "sentiment": round_sentiment,
            }
        )

    nodes = [{"name": name} for name in ("外部流量", "已曝光", "感兴趣", "已购买", "主动推荐", "放弃/负面")]
    links = [
        {"source": source, "target": target, "value": round(value, 1)}
        for (source, target), value in link_totals.items()
        if value > 0
    ]
    return {
        "model": MODEL_VERSION,
        "parameter_source": "snapshot_config" if configured else "explainable_defaults",
        "external_traffic_per_round": external_per_round,
        "scene_tags": tags,
        "scene_fission_factor": round(fission_factor, 3),
        "scene_keyword_fallback_used": bool(keyword_fission and not tags),
        "rates": {
            "exposure_to_interest": round(exposure_to_interest, 4),
            "interest_to_purchase": round(interest_to_purchase, 4),
            "purchase_to_recommend": round(purchase_to_recommend, 4),
            "negative_attrition": round(negative_attrition, 4),
        },
        "rounds": round_rows,
        "nodes": nodes,
        "links": links,
        "sentiment_evolution": [
            {"round": row["round"], **row["sentiment"]}
            for row in round_rows
        ],
    }
