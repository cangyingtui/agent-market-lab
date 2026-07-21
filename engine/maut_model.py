from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any

from engine.evidence_utils import MARKET_EVIDENCE_KEYS, USER_EVIDENCE_KEYS, evidence_items


PROMPT_VERSION = "maut_purchase_intent_v0.1"

MAUT_WEIGHTS: dict[str, float] = {
    "function_fit": 0.30,
    "price_acceptance": 0.25,
    "promotion_bonus": 0.10,
    "brand_loyalty": 0.15,
    "social_influence": 0.20,
}

DIMENSION_LABELS: dict[str, str] = {
    "function_fit": "功能匹配度",
    "price_acceptance": "价格接受度",
    "promotion_bonus": "促销加成",
    "brand_loyalty": "品牌忠诚度",
    "social_influence": "社会影响力",
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if not math.isfinite(value):
        return minimum
    return max(minimum, min(maximum, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return default
    return default


def product_price(product: dict[str, Any]) -> float | None:
    value = product.get("price_cny") or product.get("price")
    parsed = safe_float(value, -1)
    return parsed if parsed > 0 else None


def infer_annual_income(agent: dict[str, Any]) -> float:
    segment = str(agent.get("segment") or "")
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    if "高端" in segment or "高价值" in segment or sensitivity == "low":
        return 180000.0
    if "学生" in segment or "低线" in segment or sensitivity == "high":
        return 90000.0
    return 120000.0


def price_elasticity(agent: dict[str, Any]) -> float:
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    return {"high": 0.85, "medium": 0.45, "low": 0.20}.get(sensitivity, 0.45)


def segment_price_coefficient(agent: dict[str, Any]) -> float:
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    segment = str(agent.get("segment") or "")
    if "高端" in segment or sensitivity == "low":
        return 1.08
    if sensitivity == "high":
        return 0.88
    return 1.0


def extract_discount(market: dict[str, Any]) -> float:
    candidates: list[float] = []
    for key in ("discount", "price_discount", "discount_rate"):
        value = safe_float(market.get(key), -1)
        if value >= 0:
            candidates.append(value / 100 if value > 1 else value)
    strategies = market.get("strategies") if isinstance(market.get("strategies"), list) else []
    for item in strategies:
        if isinstance(item, dict):
            value = safe_float(item.get("price_discount"), -1)
            if value >= 0:
                candidates.append(value / 100 if value > 1 else value)
    if not candidates:
        text = f"{market.get('strategy', '')} {market.get('basic_selected_strategy', '')}"
        if any(word in text for word in ("促销", "折扣", "优惠", "补贴")):
            candidates.append(0.08)
    return clamp(max(candidates or [0.0]), 0.0, 0.8)


def function_fit_score(agent: dict[str, Any], product: dict[str, Any]) -> float:
    specs = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    params = product.get("params") if isinstance(product.get("params"), list) else []
    text_parts = [str(key) for key in specs.keys()] + [str(value) for value in specs.values()]
    for item in params:
        if isinstance(item, dict) and item.get("enabled", True):
            text_parts.extend([str(item.get("name") or ""), str(item.get("value") or "")])
    product_text = " ".join(text_parts)
    preferences = [str(item) for item in agent.get("preferred_features") or [] if str(item)]
    if not preferences:
        return 0.58 if product_text else 0.45
    matches = sum(1 for item in preferences if item and item in product_text)
    return clamp(0.42 + matches / max(len(preferences), 1) * 0.48 + min(len(text_parts), 8) * 0.012)


def price_acceptance_score(agent: dict[str, Any], product: dict[str, Any], market: dict[str, Any]) -> float:
    price = product_price(product)
    if price is None:
        return 0.48
    discount = extract_discount(market)
    income = infer_annual_income(agent)
    gamma = segment_price_coefficient(agent)
    epsilon = price_elasticity(agent)
    net_price = price * (1 - discount)
    raw = max(0.10, 1 - 10 * net_price / max(income, 1))
    return clamp(raw * gamma * (1 - 0.4 * epsilon))


def promotion_bonus_score(agent: dict[str, Any], market: dict[str, Any]) -> float:
    discount = extract_discount(market)
    strategy_text = f"{market.get('strategy', '')} {market.get('basic_selected_strategy', '')}"
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    sensitivity_bonus = 0.08 if sensitivity == "high" else 0.04 if sensitivity == "medium" else 0.02
    strategy_bonus = 0.06 if any(word in strategy_text for word in ("促销", "优惠", "补贴", "折扣")) else 0.02
    return clamp(discount * 1.4 + sensitivity_bonus + strategy_bonus, 0, 0.30)


def brand_loyalty_score(agent: dict[str, Any], product: dict[str, Any]) -> float:
    brand = str(product.get("brand") or "").strip()
    style = str(agent.get("decision_style") or "")
    if not brand:
        return 0.46
    if "品牌" in style or str(agent.get("price_sensitivity")) == "low":
        return 0.78
    return 0.64


def social_influence_score(agent: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> float:
    snippets = " ".join(
        str(item.get("snippet") or "")
        for item in evidence_items(evidence, *USER_EVIDENCE_KEYS, *MARKET_EVIDENCE_KEYS)[:12]
    )
    score = 0.52
    if any(word in snippets for word in ("评分", "推荐", "口碑", "社交", "KOL", "达人")):
        score += 0.16
    if any(word in snippets for word in ("价格敏感", "性价比", "谨慎")):
        score -= 0.04
    if agent.get("evidence_refs"):
        score += 0.05
    return clamp(score)


def compute_base_maut_scores(
    snapshot: dict[str, Any],
    agent: dict[str, Any],
) -> dict[str, float]:
    product = snapshot.get("product_definition") or {}
    market = snapshot.get("market_config") or {}
    return {
        "function_fit": round(function_fit_score(agent, product), 4),
        "price_acceptance": round(price_acceptance_score(agent, product, market), 4),
        "promotion_bonus": round(promotion_bonus_score(agent, market), 4),
        "brand_loyalty": round(brand_loyalty_score(agent, product), 4),
    }


def confidence_for_decision(decision: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        [
            str(decision.get("reason") or ""),
            " ".join(str(item) for item in decision.get("drivers") or []),
            " ".join(str(item) for item in decision.get("blockers") or []),
        ]
    )
    uncertain_terms = ("可能", "也许", "大概", "猜测", "待确认", "不确定", "需要复核")
    hallucination_score = clamp(sum(text.count(term) for term in uncertain_terms) / 8)
    logic_flag = 1 if product_price(product) is None and not any("价格" in str(item) for item in decision.get("blockers") or []) else 0
    format_flag = 0 if isinstance(decision.get("maut_scores"), dict) else 1
    confidence = clamp(1 - 0.6 * hallucination_score - 0.2 * logic_flag - 0.3 * format_flag)
    if confidence >= 0.80:
        level = "high"
        label = "高"
        color = "green"
    elif confidence >= 0.60:
        level = "medium"
        label = "中"
        color = "yellow"
    else:
        level = "low"
        label = "低"
        color = "red"
    return {
        "score": round(confidence, 4),
        "level": level,
        "label": label,
        "color": color,
        "hallucination_score": round(hallucination_score, 4),
        "logic_flag": logic_flag,
        "format_flag": format_flag,
        "formula": "max(0, 1 - 0.6*H - 0.2*1_logic - 0.3*1_format)",
    }


def compute_maut_scores(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agent: dict[str, Any],
    *,
    social_influence: float | None = None,
) -> dict[str, float]:
    base_scores = agent.get("base_maut_scores") if isinstance(agent.get("base_maut_scores"), dict) else {}
    if not base_scores:
        base_scores = compute_base_maut_scores(snapshot, agent)
    return {
        "function_fit": round(safe_float(base_scores.get("function_fit")), 4),
        "price_acceptance": round(safe_float(base_scores.get("price_acceptance")), 4),
        "promotion_bonus": round(safe_float(base_scores.get("promotion_bonus")), 4),
        "brand_loyalty": round(safe_float(base_scores.get("brand_loyalty")), 4),
        "social_influence": round(
            social_influence_score(agent, evidence) if social_influence is None else clamp(social_influence),
            4,
        ),
    }


def weighted_purchase_intent(maut_scores: dict[str, Any]) -> float:
    return round(
        clamp(sum(MAUT_WEIGHTS[key] * safe_float(maut_scores.get(key), 0.0) for key in MAUT_WEIGHTS)),
        4,
    )


def enrich_decisions_with_maut(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    override_score: bool = True,
) -> list[dict[str, Any]]:
    product = snapshot.get("product_definition") or {}
    agent_map = {agent.get("agent_id"): agent for agent in agents}
    enriched: list[dict[str, Any]] = []
    for decision in decisions:
        copied = dict(decision)
        agent = agent_map.get(copied.get("agent_id"), {})
        maut_scores = compute_maut_scores(snapshot, evidence, agent)
        maut_score = weighted_purchase_intent(maut_scores)
        original_score = safe_float(copied.get("purchase_intent_score"), -1)
        if original_score >= 0:
            copied["llm_purchase_intent_score"] = round(clamp(original_score), 4)
        if override_score:
            copied["purchase_intent_score"] = maut_score
            copied["decision"] = "buy" if maut_score >= 0.68 else "consider" if maut_score >= 0.45 else "not_buy"
        copied["segment"] = agent.get("segment")
        copied["segment_ratio"] = agent.get("segment_ratio")
        copied["sample_weight"] = safe_float(agent.get("sample_weight"), 1.0)
        copied["maut_scores"] = maut_scores
        copied["maut_weighted_score"] = maut_score
        copied["maut_formula"] = "100 * clip(0.30*S_f + 0.25*S_p + 0.10*B_pr + 0.15*B_b + 0.20*S_s)"
        copied["confidence"] = confidence_for_decision(copied, product)
        if product_price(product) is None:
            blockers = list(copied.get("blockers") or [])
            if "产品价格未确认" not in blockers:
                blockers.append("产品价格未确认")
            copied["blockers"] = blockers
        enriched.append(copied)
    return enriched


def average_dimension_scores(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, list[tuple[float, float]]] = {key: [] for key in MAUT_WEIGHTS}
    for decision in decisions:
        scores = decision.get("maut_scores") if isinstance(decision.get("maut_scores"), dict) else {}
        sample_weight = max(safe_float(decision.get("sample_weight"), 1.0), 0.0)
        for key in MAUT_WEIGHTS:
            if key in scores:
                rows[key].append((safe_float(scores.get(key), 0.0), sample_weight))
    averages = {
        key: (
            sum(score * sample_weight for score, sample_weight in values) / sum(sample_weight for _, sample_weight in values)
            if values and sum(sample_weight for _, sample_weight in values)
            else 0.0
        )
        for key, values in rows.items()
    }
    return {
        key: {
            "label": DIMENSION_LABELS[key],
            "weight": MAUT_WEIGHTS[key],
            "avg_score": round(averages[key], 4),
            "weighted_contribution": round(averages[key] * MAUT_WEIGHTS[key], 4),
        }
        for key in rows
    }


def confidence_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [
        (
            safe_float(decision.get("confidence", {}).get("score"), -1),
            max(safe_float(decision.get("sample_weight"), 1.0), 0.0),
        )
        for decision in decisions
        if isinstance(decision.get("confidence"), dict)
    ]
    scores = [(score, sample_weight) for score, sample_weight in scores if score >= 0]
    levels = Counter(
        str(decision.get("confidence", {}).get("level") or "unknown")
        for decision in decisions
        if isinstance(decision.get("confidence"), dict)
    )
    weight_total = sum(sample_weight for _, sample_weight in scores)
    avg = sum(score * sample_weight for score, sample_weight in scores) / weight_total if weight_total else 0.0
    if avg >= 0.80:
        level = "high"
        label = "高"
        color = "green"
    elif avg >= 0.60:
        level = "medium"
        label = "中"
        color = "yellow"
    else:
        level = "low"
        label = "低"
        color = "red"
    suggestions = []
    if levels.get("low", 0):
        suggestions.append("存在低置信 Agent 决策，建议人工复核其证据与价格输入。")
    if levels.get("medium", 0):
        suggestions.append("部分结论为中置信度，建议补充竞品价格或用户评论语料。")
    return {
        "score": round(avg, 4),
        "level": level,
        "label": label,
        "color": color,
        "level_counts": dict(levels),
        "manual_review_suggestions": suggestions,
        "formula": "max(0, 1 - 0.6*H - 0.2*1_logic - 0.3*1_format)",
    }


def build_decision_model_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "prompt_version": PROMPT_VERSION,
        "formula": "PurchaseIntent = 100 * clip(w_f*S_f + w_p*S_p + w_pr*B_pr + w_b*B_b + w_s*S_s)",
        "weights": [
            {"dimension": key, "label": DIMENSION_LABELS[key], "symbol": symbol, "weight": weight}
            for key, symbol, weight in (
                ("function_fit", "S_f", MAUT_WEIGHTS["function_fit"]),
                ("price_acceptance", "S_p", MAUT_WEIGHTS["price_acceptance"]),
                ("promotion_bonus", "B_pr", MAUT_WEIGHTS["promotion_bonus"]),
                ("brand_loyalty", "B_b", MAUT_WEIGHTS["brand_loyalty"]),
                ("social_influence", "S_s", MAUT_WEIGHTS["social_influence"]),
            )
        ],
        "dimension_scores": average_dimension_scores(decisions),
        "confidence": confidence_summary(decisions),
        "notes": [
            "当前五维分数为规则化 MAUT 计算，用于保证报告可解释和可复盘。",
            "正式投放前建议结合真实销售、访谈和渠道数据进行复核。",
        ],
    }
