from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from engine.evidence_utils import PRODUCT_EVIDENCE_KEYS, RAG_QUERY_KEYS, USER_EVIDENCE_KEYS, evidence_items
from engine.maut_model import average_dimension_scores, clamp, confidence_summary, decision_weight_profile, safe_float


PROMPT_VERSION = "aggregation_v0.1"

CONFIDENCE_FORMULA = (
    "0.40*logic_format_score + 0.25*competitor_price_coverage_score "
    "+ 0.20*rag_evidence_score + 0.15*crowd_profile_completeness_score"
)


def weighted_mean(values: list[tuple[float, float]]) -> float:
    weight_total = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / weight_total if weight_total else 0.0


def product_evidence_quality(evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    items = [
        item
        for item in evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS)
        if item.get("source_type") == "product_competitor"
    ]
    total = len(items)
    priced = 0
    named = 0
    with_specs = 0
    needs_enrichment = 0
    for item in items:
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        specs = raw.get("specifications") if isinstance(raw.get("specifications"), dict) else {}
        if raw.get("price_cny") is not None:
            priced += 1
        if raw.get("product_name") or raw.get("confirmed_sku"):
            named += 1
        if specs:
            with_specs += 1
        if raw.get("needs_enrichment") or raw.get("price_missing"):
            needs_enrichment += 1
    coverage = round(priced * 100 / total, 1) if total else 0.0
    return {
        "product_evidence_count": total,
        "priced_count": priced,
        "named_count": named,
        "with_specs_count": with_specs,
        "needs_enrichment_count": needs_enrichment,
        "price_coverage_pct": coverage,
    }


def confidence_level(score: float) -> dict[str, str]:
    if score >= 0.80:
        return {"level": "high", "label": "高", "color": "green"}
    if score >= 0.60:
        return {"level": "medium", "label": "中", "color": "yellow"}
    return {"level": "low", "label": "低", "color": "red"}


def normalized_evidence_score(value: Any) -> float:
    score = safe_float(value, 0.0)
    if score <= 1:
        return clamp(score)
    return clamp(score / 10)


def rag_evidence_quality(evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rag_items = evidence_items(evidence, *RAG_QUERY_KEYS)
    if not rag_items:
        rag_items = [
            item
            for values in evidence.values()
            if isinstance(values, list)
            for item in values
            if isinstance(item, dict)
        ]
    expected_count = max(len(RAG_QUERY_KEYS) * 5, 1)
    retrieved_count = len(rag_items)
    count_score = clamp(retrieved_count / expected_count)
    quality_values = [normalized_evidence_score(item.get("score")) for item in rag_items if item.get("score") is not None]
    quality_score = statistics.mean(quality_values) if quality_values else 0.0
    score = clamp(0.6 * count_score + 0.4 * quality_score)
    return {
        "score": round(score, 4),
        "retrieved_count": retrieved_count,
        "expected_count": expected_count,
        "count_score": round(count_score, 4),
        "quality_score": round(quality_score, 4),
    }


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return any(has_value(item) for item in value)
    if isinstance(value, dict):
        return any(has_value(item) for item in value.values())
    text = str(value).strip()
    return text not in {"", "unknown", "未知", "待确认", "目标用户", "None", "null"}


def first_value(*values: Any) -> Any:
    for value in values:
        if has_value(value):
            return value
    return None


def agent_values(agents: list[dict[str, Any]], key: str) -> list[Any]:
    return [agent.get(key) for agent in agents if has_value(agent.get(key))]


def crowd_profile_quality(
    agents: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    market = snapshot.get("market_config") if isinstance(snapshot, dict) and isinstance(snapshot.get("market_config"), dict) else {}
    profile = market.get("crowd_profile") if isinstance(market.get("crowd_profile"), dict) else {}
    field_values = {
        "target_crowd": first_value(
            market.get("target_crowd"),
            market.get("crowd"),
            profile.get("name"),
            *agent_values(agents, "segment"),
        ),
        "price_sensitivity": first_value(
            profile.get("price_sensitivity"),
            market.get("price_sensitivity"),
            *agent_values(agents, "price_sensitivity"),
        ),
        "feature_priorities": first_value(
            profile.get("feature_priorities"),
            profile.get("preferences"),
            *agent_values(agents, "preferred_features"),
        ),
        "age_range": first_value(profile.get("age_range"), profile.get("age"), *agent_values(agents, "age_range")),
        "city_tier": first_value(profile.get("city_tier"), profile.get("city"), *agent_values(agents, "city_tier")),
        "income_level": first_value(profile.get("income_level"), profile.get("income"), *agent_values(agents, "income_level")),
        "life_stage": first_value(
            profile.get("life_stage"),
            profile.get("occupation"),
            profile.get("usage"),
            *agent_values(agents, "life_stage"),
        ),
        "channel_preferences": first_value(profile.get("channel_preferences"), profile.get("channels"), *agent_values(agents, "channel_preferences")),
        "purchase_motivations": first_value(profile.get("purchase_motivations"), profile.get("motivations"), *agent_values(agents, "purchase_motivations")),
        "risk_concerns": first_value(profile.get("risk_concerns"), profile.get("concerns"), *agent_values(agents, "risk_concerns")),
        "custom_description": first_value(profile.get("custom_description"), profile.get("description")),
    }
    required_keys = ("target_crowd", "price_sensitivity", "feature_priorities")
    optional_keys = (
        "age_range",
        "city_tier",
        "income_level",
        "life_stage",
        "channel_preferences",
        "purchase_motivations",
        "risk_concerns",
        "custom_description",
    )
    present_required = [key for key in required_keys if has_value(field_values.get(key))]
    present_optional = [key for key in optional_keys if has_value(field_values.get(key))]
    required_score = len(present_required) / len(required_keys)
    optional_score = len(present_optional) / len(optional_keys)
    score = clamp(0.8 * required_score + 0.2 * optional_score)
    return {
        "score": round(score, 4),
        "required_score": round(required_score, 4),
        "optional_score": round(optional_score, 4),
        "present_fields": present_required + present_optional,
        "missing_required_fields": [key for key in required_keys if key not in present_required],
    }


def evidence_confidence_summary(
    decisions: list[dict[str, Any]],
    evidence_quality: dict[str, Any],
    rag_quality: dict[str, Any],
    profile_quality: dict[str, Any],
) -> dict[str, Any]:
    logic_summary = confidence_summary(decisions)
    logic_score = clamp(safe_float(logic_summary.get("score"), 0.0))
    price_score = clamp(safe_float(evidence_quality.get("price_coverage_pct"), 0.0) / 100)
    rag_score = clamp(safe_float(rag_quality.get("score"), 0.0))
    profile_score = clamp(safe_float(profile_quality.get("score"), 0.0))
    score = clamp(0.40 * logic_score + 0.25 * price_score + 0.20 * rag_score + 0.15 * profile_score)
    level = confidence_level(score)
    suggestions = list(logic_summary.get("manual_review_suggestions") or [])
    if price_score < 0.60:
        suggestions.append("竞品价格覆盖率偏低，价格带和敏感性结论需要谨慎使用。")
    if rag_score < 0.60:
        suggestions.append("RAG 证据数量或质量不足，建议补充更多竞品、用户评论或市场资料。")
    if profile_score < 0.70:
        suggestions.append("用户画像信息不够完整，建议补充价格敏感度、功能偏好、动机或顾虑。")
    if not suggestions:
        suggestions.append("当前证据可支撑演示分析，正式投放前仍建议结合真实销售和访谈数据复核。")
    return {
        "score": round(score, 4),
        **level,
        "display_name": "证据置信度",
        "components": {
            "logic_format_score": {
                "label": "逻辑/格式",
                "score": round(logic_score, 4),
                "weight": 0.40,
                "source": "Agent 决策格式、逻辑和不确定表述",
            },
            "competitor_price_coverage_score": {
                "label": "竞品价格覆盖率",
                "score": round(price_score, 4),
                "weight": 0.25,
                "source": "竞品证据中可用价格占比",
                "raw_pct": evidence_quality.get("price_coverage_pct"),
            },
            "rag_evidence_score": {
                "label": "RAG 证据数量/质量",
                "score": round(rag_score, 4),
                "weight": 0.20,
                "source": "检索证据数量和检索分数",
                "retrieved_count": rag_quality.get("retrieved_count"),
                "quality_score": rag_quality.get("quality_score"),
            },
            "crowd_profile_completeness_score": {
                "label": "用户画像完整度",
                "score": round(profile_score, 4),
                "weight": 0.15,
                "source": "目标人群、价格敏感度、功能偏好和画像细项",
                "present_fields": profile_quality.get("present_fields"),
            },
        },
        "logic_format_confidence": logic_summary,
        "level_counts": logic_summary.get("level_counts", {}),
        "manual_review_suggestions": suggestions,
        "formula": CONFIDENCE_FORMULA,
    }


def aggregate_results(
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    evidence: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, Any] | None = None,
    *,
    social_simulation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agent_map = {agent["agent_id"]: agent for agent in agents}
    weighted_scores: list[tuple[float, float]] = []
    decision_counts = Counter(item.get("decision") or "consider" for item in decisions)
    weighted_decision_counts: Counter[str] = Counter()
    segment_scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
    price_scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
    price_acceptance_scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
    drivers = Counter()
    blockers = Counter()
    driver_counts = Counter()
    blocker_counts = Counter()
    blocker_agent_weight = Counter()

    for decision in decisions:
        agent = agent_map.get(decision.get("agent_id"), {})
        score = float(decision.get("purchase_intent_score") or 0)
        sample_weight = max(safe_float(agent.get("sample_weight", decision.get("sample_weight")), 1.0), 0.0)
        weighted_scores.append((score, sample_weight))
        weighted_decision_counts[str(decision.get("decision") or "consider")] += sample_weight
        segment_scores[str(agent.get("segment") or decision.get("segment") or "unknown")].append((score, sample_weight))
        sensitivity = str(agent.get("price_sensitivity") or "unknown")
        price_scores[sensitivity].append((score, sample_weight))
        maut_scores = decision.get("maut_scores") if isinstance(decision.get("maut_scores"), dict) else {}
        if "price_acceptance" in maut_scores:
            price_acceptance_scores[sensitivity].append((float(maut_scores.get("price_acceptance") or 0), sample_weight))
        for item in decision.get("drivers") or []:
            drivers[str(item)] += sample_weight
            driver_counts[str(item)] += 1
        for item in decision.get("blockers") or []:
            blockers[str(item)] += sample_weight
            blocker_counts[str(item)] += 1
            blocker_agent_weight[str(item)] += sample_weight
    avg_score = weighted_mean(weighted_scores)
    sample_weight_total = sum(weight for _, weight in weighted_scores)

    competitor_advantages = [
        item.get("snippet")
        for item in evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS)
        if item.get("source_type") == "product_competitor"
    ][:5]
    user_risks = [
        item.get("snippet")
        for item in evidence_items(evidence, *USER_EVIDENCE_KEYS)
        if item.get("source_type") == "user_profile"
    ][:5]
    evidence_quality = product_evidence_quality(evidence)
    rag_quality = rag_evidence_quality(evidence)
    profile_quality = crowd_profile_quality(agents, snapshot)
    evidence_confidence = evidence_confidence_summary(decisions, evidence_quality, rag_quality, profile_quality)
    weight_profile = decision_weight_profile(snapshot)
    dimension_scores = average_dimension_scores(decisions, weight_profile["weights"])

    return {
        "prompt_version": PROMPT_VERSION,
        "purchase_intent_avg": round(avg_score, 4),
        "purchase_intent_distribution": dict(decision_counts),
        "purchase_intent_weighted_distribution": {
            key: round(value / sample_weight_total, 4) if sample_weight_total else 0.0
            for key, value in weighted_decision_counts.items()
        },
        "segment_summary": {
            segment: {
                "count": len(values),
                "ratio": round(sum(weight for _, weight in values) * 100 / sample_weight_total, 1)
                if sample_weight_total
                else 0.0,
                "avg_purchase_intent": round(weighted_mean(values), 4),
                "weighted_contribution": round(
                    weighted_mean(values) * sum(weight for _, weight in values) / sample_weight_total,
                    4,
                )
                if sample_weight_total
                else 0.0,
            }
            for segment, values in segment_scores.items()
        },
        "price_sensitivity_summary": {
            level: {
                "count": len(values),
                "avg_purchase_intent": round(weighted_mean(values), 4),
                "avg_price_acceptance": round(weighted_mean(price_acceptance_scores[level]), 4)
                if price_acceptance_scores.get(level)
                else None,
            }
            for level, values in price_scores.items()
        },
        "dimension_scores": dimension_scores,
        "decision_weight_profile": weight_profile,
        "confidence": evidence_confidence,
        "social_influence_avg": dimension_scores.get("social_influence", {}).get("avg_score", 0.0),
        "social_evolution": social_simulation.get("round_summaries", [])
        if isinstance(social_simulation, dict)
        else [],
        "social_network": {
            key: social_simulation.get(key)
            for key in ("rounds_executed", "converged", "node_count", "edge_count", "average_degree", "topology")
        }
        if isinstance(social_simulation, dict)
        else {},
        "top_purchase_drivers": [
            {"item": item, "count": driver_counts[item], "weight": round(weight, 4)}
            for item, weight in drivers.most_common(8)
        ],
        "top_purchase_blockers": [
            {
                "item": item,
                "count": blocker_counts[item],
                "weight": round(weight, 4),
                "affected_share_pct": round(blocker_agent_weight[item] * 100 / sample_weight_total, 1) if sample_weight_total else 0.0,
            }
            for item, weight in blockers.most_common(8)
        ],
        "competitor_advantages": competitor_advantages,
        "user_profile_risks": user_risks,
        "evidence_quality": evidence_quality,
        "rag_evidence_quality": rag_quality,
        "crowd_profile_quality": profile_quality,
    }
