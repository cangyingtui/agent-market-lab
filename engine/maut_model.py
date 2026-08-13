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

WEIGHT_PROFILE_VERSION = "channel_weights_v1"
WEIGHT_TEMPLATES: dict[str, dict[str, float]] = {
    "default": dict(MAUT_WEIGHTS),
    "douyin": {
        "function_fit": 0.25,
        "price_acceptance": 0.25,
        "promotion_bonus": 0.20,
        "brand_loyalty": 0.10,
        "social_influence": 0.20,
    },
    "tmall": {
        "function_fit": 0.25,
        "price_acceptance": 0.27,
        "promotion_bonus": 0.13,
        "brand_loyalty": 0.20,
        "social_influence": 0.15,
    },
    "offline_premium": {
        "function_fit": 0.25,
        "price_acceptance": 0.20,
        "promotion_bonus": 0.10,
        "brand_loyalty": 0.25,
        "social_influence": 0.20,
    },
}

DIMENSION_LABELS: dict[str, str] = {
    "function_fit": "功能匹配度",
    "price_acceptance": "价格接受度",
    "promotion_bonus": "促销加成",
    "brand_loyalty": "品牌敏感度",
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


def agent_heterogeneity(agent_id: str, *, scale: float = 0.10) -> float:
    """Deterministic preference noise based on agent identity hash.

    Simulates unobserved consumer heterogeneity — the fact that two consumers
    with identical observable attributes still make different choices due to
    personal taste, mood, past experiences, etc.

    Uses SHA-256 of agent_id for cross-process reproducibility (CLAUDE.md rule #5).
    Returns a perturbation in [-scale, +scale] that is stable for the same agent_id.
    """
    import hashlib
    digest = hashlib.sha256(str(agent_id).encode()).hexdigest()
    # Map first 8 hex chars to [-1, 1] range
    raw = int(digest[:8], 16) / 0x7FFFFFFF - 1.0
    return round(raw * scale, 6)


def adaptive_thresholds(scores: list[float]) -> tuple[float, float]:
    """Compute percentile-based decision thresholds from actual score distribution.

    Uses p33/p67 of the current round's scores to set not_buy/consider/buy
    boundaries, with anchor floors to prevent all-neutral collapse when scores
    are tightly clustered (the "score polarization" problem).

    Strategy:
    - Wide spread (>=0.10): use natural p33/p67, clamped to anchors
    - Moderate spread (0.06-0.10): expand from median with 0.12 minimum gap
    - Tight spread (<0.06): force a minimum 0.14 gap around the median,
      guaranteeing roughly 1/3 of agents fall into buy + not_buy combined

    Anchors ensure: low ∈ [0.28, 0.50], high ∈ [0.50, 0.75].
    """
    if not scores or len(scores) < 3:
        return (0.42, 0.62)

    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    median = sorted_scores[n // 2]
    p33_idx = max(0, int(n * 0.33))
    p67_idx = min(n - 1, int(n * 0.67))
    low_pct = sorted_scores[p33_idx]
    high_pct = sorted_scores[p67_idx]
    spread = high_pct - low_pct

    if spread >= 0.10:
        # Distribution has natural spread — use percentiles directly
        low = low_pct
        high = high_pct
    elif spread >= 0.06:
        # Moderate clustering — expand from median with guaranteed gap
        low = min(low_pct, median - 0.06)
        high = max(high_pct, median + 0.06)
    else:
        # Tight cluster — force a meaningful split
        # Expand outward from median by at least 0.07 each side (0.14 gap)
        low = median - 0.07
        high = median + 0.07

    # Apply anchor floors: low ∈ [0.28, 0.50], high ∈ [0.50, 0.75]
    low = max(0.28, min(0.50, low))
    high = max(0.50, min(0.75, high))

    # Hard minimum gap of 0.10 between low and high
    if high - low < 0.10:
        mid = (low + high) / 2
        low = max(0.28, mid - 0.05)
        high = min(0.75, mid + 0.05)

    return (round(low, 4), round(high, 4))


def normalize_weights(value: Any, *, fallback: dict[str, float] | None = None) -> dict[str, float]:
    base = fallback or MAUT_WEIGHTS
    raw = value if isinstance(value, dict) else {}
    weights = {
        key: max(0.0, safe_float(raw.get(key), base[key]))
        for key in MAUT_WEIGHTS
    }
    total = sum(weights.values())
    if total <= 0:
        return dict(base)
    return {key: round(weight / total, 6) for key, weight in weights.items()}


def decision_weight_profile(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    configured = snapshot.get("decision_weight_profile")
    if not isinstance(configured, dict):
        configured = {}
    template = str(configured.get("template") or "default").strip().lower()
    template_weights = WEIGHT_TEMPLATES.get(template, WEIGHT_TEMPLATES["default"])
    weights = normalize_weights(configured.get("weights"), fallback=template_weights)
    return {
        "template": template if template in WEIGHT_TEMPLATES or template == "custom" else "default",
        "version": str(configured.get("version") or WEIGHT_PROFILE_VERSION),
        "weights": weights,
    }


def product_price(product: dict[str, Any]) -> float | None:
    value = product.get("price_cny") or product.get("price")
    parsed = safe_float(value, -1)
    return parsed if parsed > 0 else None


def infer_annual_income(agent: dict[str, Any]) -> float:
    segment = str(agent.get("segment") or "")
    income_level = str(agent.get("income_level") or "")
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    if any(word in income_level for word in ("高", "20万", "30万", "富裕")):
        base = 220000.0
    elif any(word in income_level for word in ("低", "5万", "8万")):
        base = 80000.0
    elif "高端" in segment or "高价值" in segment or sensitivity == "low":
        base = 180000.0
    elif "学生" in segment or "低线" in segment or sensitivity == "high":
        base = 90000.0
    else:
        base = 120000.0
    return base


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
    """功能匹配度：基于消费者偏好特征与产品参数的连续匹配评分。

    使用 Jaccard 风格的模糊匹配替代精确字符串匹配，消除离散步长。
    匹配粒度：完全匹配 > 子串包含 > 字符集重叠。
    """
    specs = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    params = product.get("params") if isinstance(product.get("params"), list) else []
    text_parts = [str(key) for key in specs.keys()] + [str(value) for value in specs.values()]
    for item in params:
        if isinstance(item, dict) and item.get("enabled", True):
            text_parts.extend([str(item.get("name") or ""), str(item.get("value") or "")])
    product_text = " ".join(text_parts).lower()

    preferences = [str(item) for item in agent.get("preferred_features") or [] if str(item)]
    if not preferences:
        return 0.58 if product_text else 0.45

    # Continuous fuzzy match: exact=1.0, substring=0.7, char-overlap=0.35*Jaccard
    match_scores: list[float] = []
    for pref in preferences:
        pref_lower = pref.lower()
        if pref_lower in product_text:
            match_scores.append(1.0)
        else:
            # Substring partial match
            words = pref_lower.split()
            partial_hits = sum(1.0 for w in words if w and w in product_text)
            if partial_hits > 0:
                match_scores.append(min(0.70, partial_hits / max(len(words), 1) * 0.65))
            else:
                # Character-level overlap as last resort
                product_chars = set(product_text)
                pref_chars = set(pref_lower)
                overlap = len(pref_chars & product_chars)
                union = len(pref_chars | product_chars)
                match_scores.append(overlap / max(union, 1) * 0.35)

    avg_match = sum(match_scores) / len(match_scores)
    return clamp(0.42 + avg_match * 0.48 + min(len(text_parts), 8) * 0.012)


def price_acceptance_score(agent: dict[str, Any], product: dict[str, Any], market: dict[str, Any]) -> float:
    """Logistic price acceptance based on discrete choice (logit) model.

    P(buy) = 1 / (1 + exp(-(α - β × price_burden)))

    - α (alpha): baseline willingness at zero price
    - β (beta):  price sensitivity — steeper = more price-sensitive
    - price_burden = net_price / annual_income

    The asymmetric logistic curve on the chart (chart_data.py) is derived
    from the aggregate intent distribution; this agent-level formula ensures
    individual purchase decisions also follow a smooth S-curve rather than
    a linear cliff.
    """
    price = product_price(product)
    if price is None:
        return 0.48
    discount = extract_discount(market)
    income = infer_annual_income(agent)
    net_price = price * (1.0 - discount)
    price_burden = net_price / max(income, 1.0)

    sensitivity = str(agent.get("price_sensitivity") or "medium")
    if sensitivity == "low":
        alpha = 3.0   # 高基准意愿
        beta = 22     # 价格不敏感（降低陡峭度，避免高价产品过早触底）
    elif sensitivity == "high":
        alpha = 1.5   # 低基准意愿
        beta = 45     # 价格极敏感（同步降低，保持相对差异）
    else:  # medium
        alpha = 2.2
        beta = 32     # 从 40 降至 32：高价产品（>¥10k）在中等敏感人群中仍保留一定接受度

    # Standard logit: score → 1 when price_burden → 0, score → 0 when price_burden → ∞
    logit = alpha - beta * price_burden
    raw = 1.0 / (1.0 + math.exp(-logit))

    # Segment-level adjustment: 高端人群略宽容，价格敏感人群略严苛
    gamma = segment_price_coefficient(agent)
    # Floor raised from 0.05 to 0.15: even extremely expensive products
    # (medical devices, premium equipment) retain minimum price acceptance,
    # preventing the MAUT score from being entirely dominated by price.
    return clamp(raw * gamma, 0.15, 0.98)


def promotion_bonus_score(agent: dict[str, Any], market: dict[str, Any]) -> float:
    discount = extract_discount(market)
    strategy_text = f"{market.get('strategy', '')} {market.get('basic_selected_strategy', '')}"
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    sensitivity_bonus = 0.08 if sensitivity == "high" else 0.04 if sensitivity == "medium" else 0.02
    strategy_bonus = 0.06 if any(word in strategy_text for word in ("促销", "优惠", "补贴", "折扣")) else 0.02
    return clamp(discount * 1.4 + sensitivity_bonus + strategy_bonus, 0, 0.30)


def brand_loyalty_score(agent: dict[str, Any], product: dict[str, Any]) -> float:
    """品牌忠诚度：基于品牌匹配、品牌导向性和价格敏感度的连续评分。

    使用连续映射替代离散分支，消除三模态聚类。
    品牌匹配效应受消费者品牌敏感度和价格敏感度双向调制。
    """
    brand = str(product.get("brand") or "").strip()
    if not brand:
        return 0.46

    preferred_brands = agent.get("preferred_brands")
    style = str(agent.get("decision_style") or "")
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    brand_oriented = 1.0 if "品牌" in style else 0.0
    if isinstance(preferred_brands, list) and preferred_brands:
        # Continuous brand match strength: exact match vs substring overlap
        brand_lower = brand.lower()
        match_scores = []
        for pref in preferred_brands:
            pref_lower = str(pref).lower()
            if pref_lower == brand_lower:
                match_scores.append(1.0)
            elif pref_lower in brand_lower or brand_lower in pref_lower:
                match_scores.append(0.65)
            else:
                # Jaccard-like character overlap
                overlap = len(set(pref_lower) & set(brand_lower))
                union = len(set(pref_lower) | set(brand_lower))
                match_scores.append(overlap / max(union, 1) * 0.35)
        best_match = max(match_scores) if match_scores else 0.0
        # Continuous mapping: base 0.50, brand match pushes up, mismatch down
        base = 0.50 + best_match * 0.28 - (1.0 - best_match) * 0.08
    else:
        # No brand preference — moderate baseline
        base = 0.58

    # Modulate by brand orientation (continuous) and price sensitivity
    brand_boost = brand_oriented * 0.05
    price_penalty = -0.06 if sensitivity == "high" else 0.0 if sensitivity == "medium" else 0.04
    return clamp(base + brand_boost + price_penalty, 0.35, 0.88)


def social_influence_score(agent: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> float:
    snippets = " ".join(
        str(item.get("snippet") or "")
        for item in evidence_items(evidence, *USER_EVIDENCE_KEYS, *MARKET_EVIDENCE_KEYS)[:12]
    )
    score = 0.50  # 与社交传播中的 neighbor_avg 默认值 0.5 对齐
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


def compute_environment_volatility(snapshot: dict[str, Any]) -> dict[str, Any]:
    """计算营商环境波动指数（范围 0-1）。

    综合 5 个外生因素，评估当前市场环境的不确定性。
    波动越大 → 消费者行为越分散 → 预测置信区间越宽。

    五个因素：
    1. 竞争激烈度（竞品数量、价格离散度）
    2. 消费信心（市场情绪信号）
    3. 市场成熟度（品类是否新兴/成熟）
    4. 策略激进程度（折扣/补贴力度）
    5. 价格敏感人群占比
    """
    product = snapshot.get("product_definition") or {}
    market = snapshot.get("market_config") or {}

    # 1. 竞争激烈度 (0-1)
    competitors = market.get("competitors") if isinstance(market.get("competitors"), list) else []
    comp_count = len(competitors)
    comp_prices: list[float] = []
    for c in competitors:
        if isinstance(c, dict):
            p = safe_float(c.get("price_cny") or c.get("price"), 0)
            if p > 0:
                comp_prices.append(p)
    price_dispersion = statistics.stdev(comp_prices) / statistics.mean(comp_prices) if len(comp_prices) >= 2 and statistics.mean(comp_prices) > 0 else 0.0
    competition_score = clamp(comp_count / 15 + price_dispersion / 2, 0.0, 1.0)

    # 2. 消费信心 (0-1, 越高信心越低 → 波动越大)
    strategy_text = str(market.get("strategy") or "") + str(market.get("basic_selected_strategy") or "")
    target = str(market.get("target_crowd") or market.get("crowd") or "")
    category = str(product.get("subcategory") or product.get("category") or "")
    signals = strategy_text + target + category
    caution_words = sum(1 for w in ("观望", "谨慎", "降级", "收紧", "保守", "悲观") if w in signals)
    confidence_loss = clamp(caution_words * 0.2, 0.0, 0.6)

    # 3. 市场成熟度 (0-1, 越新兴波动越大)
    emerging_keywords = ("新兴", "蓝海", "风口", "新品类", "初创", "早期")
    mature_keywords = ("成熟", "红海", "稳定", "传统", "饱和")
    emerging = sum(1 for w in emerging_keywords if w in signals)
    mature = sum(1 for w in mature_keywords if w in signals)
    if emerging > mature:
        maturity_volatility = 0.7
    elif mature > emerging:
        maturity_volatility = 0.2
    else:
        maturity_volatility = 0.45  # 未明确 → 中等波动

    # 4. 策略激进程度 (0-1)
    discount = safe_float(market.get("discount") or market.get("promotion_discount"), 0.0)
    aggressive_words = sum(1 for w in ("促销", "补贴", "大促", "限时", "买一送一", "满减", "免单") if w in signals)
    strategy_aggressiveness = clamp(discount * 1.5 + aggressive_words * 0.08, 0.0, 0.8)

    # 5. 价格敏感人群占比 (0-1)
    segments = market.get("crowd_segments") if isinstance(market.get("crowd_segments"), list) else []
    total_ratio = 0.0
    high_sensitivity_ratio = 0.0
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        ratio = safe_float(seg.get("ratio"), 0.0)
        total_ratio += ratio
        profile = seg.get("profile") if isinstance(seg.get("profile"), dict) else {}
        sensitivity = str(profile.get("price_sensitivity") or "")
        if sensitivity in ("high", "高", "高敏感", "价格敏感"):
            high_sensitivity_ratio += ratio
    sensitivity_share = high_sensitivity_ratio / max(total_ratio, 1.0)

    # 加权合成 (等权)
    raw = (
        competition_score * 0.20
        + confidence_loss * 0.20
        + maturity_volatility * 0.20
        + strategy_aggressiveness * 0.20
        + sensitivity_share * 0.20
    )
    volatility = clamp(raw, 0.05, 0.95)

    return {
        "index": round(volatility, 4),
        "label": "高" if volatility >= 0.55 else "中" if volatility >= 0.30 else "低",
        "factors": {
            "competition_intensity": round(competition_score, 4),
            "consumer_confidence_loss": round(confidence_loss, 4),
            "market_maturity_volatility": round(maturity_volatility, 4),
            "strategy_aggressiveness": round(strategy_aggressiveness, 4),
            "price_sensitivity_share": round(sensitivity_share, 4),
        },
        "note": (
            "营商环境波动指数综合评估了当前市场的竞争激烈度、消费者信心、"
            "市场成熟度、促销策略力度和价格敏感人群占比。指数越高，"
            "消费者行为越分散，预测结果的不确定性越大。"
        ),
    }


def apply_environment_perturbation(base_score: float, agent: dict[str, Any] | str, volatility: float) -> float:
    """Apply an explainable environment adjustment without random noise.

    The public function name is retained for report compatibility. Adjustment
    direction comes only from explicit price sensitivity and risk concerns;
    an old caller passing an agent id receives no artificial offset.
    """
    if volatility <= 0 or not isinstance(agent, dict):
        return base_score
    sensitivity = str(agent.get("price_sensitivity") or "medium")
    sensitivity_shift = {"high": -0.06, "medium": 0.0, "low": 0.025}.get(sensitivity, 0.0)
    concerns = agent.get("risk_concerns") if isinstance(agent.get("risk_concerns"), list) else []
    risk_penalty = min(len([item for item in concerns if str(item).strip()]) * 0.008, 0.03)
    offset = (sensitivity_shift - risk_penalty) * volatility
    return clamp(base_score + offset)


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


def weighted_purchase_intent(
    maut_scores: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> float:
    active_weights = normalize_weights(weights)
    return round(
        clamp(sum(active_weights[key] * safe_float(maut_scores.get(key), 0.0) for key in MAUT_WEIGHTS)),
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
    profile = decision_weight_profile(snapshot)
    weights = profile["weights"]
    env_info = compute_environment_volatility(snapshot)
    env_volatility = env_info["index"]
    agent_map = {agent.get("agent_id"): agent for agent in agents}
    prepared: list[tuple[dict[str, Any], dict[str, Any], dict[str, float], float]] = []
    for decision in decisions:
        copied = dict(decision)
        agent = agent_map.get(copied.get("agent_id"), {})
        maut_scores = compute_maut_scores(snapshot, evidence, agent)
        # Dynamic weight redistribution: when price_acceptance hits the floor
        # (≤ 0.20, i.e. product is very expensive for this agent), reduce the
        # price dimension weight and redistribute to quality dimensions.
        # This prevents high-price products like medical devices from having
        # their PI entirely dominated by near-zero price scores.
        pa_score = maut_scores.get("price_acceptance", 0.5)
        if pa_score <= 0.20:
            active_weights = dict(weights)
            excess = active_weights.get("price_acceptance", 0.25) - 0.10
            if excess > 0:
                active_weights["price_acceptance"] = 0.10
                # Redistribute to quality-driven dimensions
                active_weights["function_fit"] = active_weights.get("function_fit", 0.30) + excess * 0.50
                active_weights["brand_loyalty"] = active_weights.get("brand_loyalty", 0.15) + excess * 0.30
                active_weights["social_influence"] = active_weights.get("social_influence", 0.20) + excess * 0.20
                # Re-normalize
                total = sum(active_weights.values())
                active_weights = {k: round(v / total, 6) for k, v in active_weights.items()}
                maut_score = weighted_purchase_intent(maut_scores, active_weights)
            else:
                maut_score = weighted_purchase_intent(maut_scores, weights)
        else:
            maut_score = weighted_purchase_intent(maut_scores, weights)
        maut_score = apply_environment_perturbation(maut_score, agent, env_volatility)
        # Deterministic agent-level preference noise
        agent_id = str(agent.get("agent_id", ""))
        maut_score = clamp(maut_score + agent_heterogeneity(agent_id))
        prepared.append((copied, agent, maut_scores, maut_score))

    final_scores = [item[3] for item in prepared]
    low_threshold, high_threshold = adaptive_thresholds(final_scores)
    enriched: list[dict[str, Any]] = []
    for copied, agent, maut_scores, maut_score in prepared:
        original_score = safe_float(copied.get("purchase_intent_score"), -1)
        if original_score >= 0:
            copied["llm_purchase_intent_score"] = round(clamp(original_score), 4)
        if override_score:
            copied["purchase_intent_score"] = maut_score
            copied["decision"] = "buy" if maut_score >= high_threshold else "consider" if maut_score >= low_threshold else "not_buy"
        copied["segment"] = agent.get("segment")
        copied["segment_ratio"] = agent.get("segment_ratio")
        copied["sample_weight"] = safe_float(agent.get("sample_weight"), 1.0)
        copied["maut_scores"] = maut_scores
        copied["maut_weighted_score"] = maut_score
        copied["maut_formula"] = weight_formula(weights)
        copied["decision_weight_profile"] = profile["template"]
        copied["confidence"] = confidence_for_decision(copied, product)
        if product_price(product) is None:
            blockers = list(copied.get("blockers") or [])
            if "产品价格未确认" not in blockers:
                blockers.append("产品价格未确认")
            copied["blockers"] = blockers
        copied["environment_volatility"] = env_info
        enriched.append(copied)
    return enriched


def average_dimension_scores(
    decisions: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    active_weights = normalize_weights(weights)
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
            "weight": active_weights[key],
            "avg_score": round(averages[key], 4),
            "weighted_contribution": round(averages[key] * active_weights[key], 4),
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


def weight_formula(weights: dict[str, float]) -> str:
    active = normalize_weights(weights)
    return (
        "100 * clip("
        f"{active['function_fit']:.2f}*S_f + {active['price_acceptance']:.2f}*S_p + "
        f"{active['promotion_bonus']:.2f}*B_pr + {active['brand_loyalty']:.2f}*B_b + "
        f"{active['social_influence']:.2f}*S_s)"
    )


def build_channel_scenarios(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template, weights in WEIGHT_TEMPLATES.items():
        weighted_rows = [
            (
                weighted_purchase_intent(
                    decision.get("maut_scores") if isinstance(decision.get("maut_scores"), dict) else {},
                    weights,
                ),
                max(safe_float(decision.get("sample_weight"), 1.0), 0.0),
            )
            for decision in decisions
        ]
        total_weight = sum(weight for _, weight in weighted_rows)
        score = sum(value * weight for value, weight in weighted_rows) / total_weight if total_weight else 0.0
        rows.append(
            {
                "template": template,
                "label": {"default": "默认", "douyin": "抖音", "tmall": "天猫", "offline_premium": "线下高端"}[template],
                "weights": dict(weights),
                "purchase_intent": round(score * 100, 1),
            }
        )
    return rows


def build_decision_model_summary(
    decisions: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = decision_weight_profile(snapshot)
    weights = profile["weights"]
    # 从首个决策中提取营商环境波动指数（所有决策共享同一值）
    first_decision = decisions[0] if decisions else {}
    env_volatility = first_decision.get("environment_volatility") if isinstance(first_decision, dict) else None
    summary: dict[str, Any] = {
        "prompt_version": PROMPT_VERSION,
        "formula": "PurchaseIntent = 100 * clip(w_f*S_f + w_p*S_p + w_pr*B_pr + w_b*B_b + w_s*S_s)",
        "formula_resolved": weight_formula(weights),
        "weight_profile": profile,
        "weights": [
            {"dimension": key, "label": DIMENSION_LABELS[key], "symbol": symbol, "weight": weight}
            for key, symbol, weight in (
                ("function_fit", "S_f", weights["function_fit"]),
                ("price_acceptance", "S_p", weights["price_acceptance"]),
                ("promotion_bonus", "B_pr", weights["promotion_bonus"]),
                ("brand_loyalty", "B_b", weights["brand_loyalty"]),
                ("social_influence", "S_s", weights["social_influence"]),
            )
        ],
        "dimension_scores": average_dimension_scores(decisions, weights),
        "confidence": confidence_summary(decisions),
        "channel_scenarios": build_channel_scenarios(decisions),
        "notes": [
            "当前五维分数为规则化 MAUT 计算，用于保证报告可解释和可复盘。",
            "正式投放前建议结合真实销售、访谈和渠道数据进行复核。",
        ],
    }
    if env_volatility:
        summary["environment_volatility"] = env_volatility
    return summary
