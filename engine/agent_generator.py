from __future__ import annotations

import re
from typing import Any

from app.crowd_profile import crowd_profile_text, normalize_crowd_profile, normalize_crowd_segments, normalize_profile
from engine.evidence_utils import MARKET_EVIDENCE_KEYS, USER_EVIDENCE_KEYS, evidence_items
from engine.maut_model import compute_base_maut_scores
from engine.social_network import attach_social_network, representative_agent_count, social_network_config


PROMPT_VERSION = "agent_generator_v0.1"


def normalize_price_sensitivity(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"high", "高", "高敏感", "价格敏感"}:
        return "high"
    if text in {"low", "低", "低敏感", "不敏感"}:
        return "low"
    return "medium"


def infer_price_sensitivity(snippets: list[str], index: int, profile_value: Any = None) -> str:
    if profile_value:
        return normalize_price_sensitivity(profile_value)
    text = " ".join(snippets)
    if "价格敏感度高" in text or "性价比" in text:
        return "high" if index % 3 != 0 else "medium"
    if "价格敏感度低" in text or "消费价格段为high" in text:
        return "low"
    if "消费价格段为medium" in text:
        return "medium"
    return ["medium", "high", "low"][index % 3]


def extract_feature_preferences(snippets: list[str], product_definition: dict[str, Any]) -> list[str]:
    features: list[str] = []
    for snippet in snippets:
        match = re.search(r"关键词[:：](.+)", snippet)
        if match:
            features.extend([item.strip() for item in re.split(r"[;；,，]", match.group(1)) if item.strip()])
    specs = product_definition.get("specifications")
    if isinstance(specs, dict):
        features.extend(str(key) for key in specs.keys())
    result: list[str] = []
    for item in features:
        if item and item not in result:
            result.append(item)
    return result[:6] or ["价格", "功能", "可靠性"]


def infer_category_preference(snippets: list[str], fallback: str) -> str:
    for snippet in snippets:
        match = re.search(r"偏好品类为([^，,。]+)", snippet)
        if match:
            return match.group(1)
    return fallback or "目标品类"


def _extract_product_brand(product: dict[str, Any]) -> str:
    """从产品定义中提取品牌名"""
    brand = str(product.get("brand") or "").strip()
    if brand:
        return brand
    # 从产品名推断品牌（如"iPhone 15" → "Apple" 无法自动推断，回退为空）
    return ""


def _extract_competitor_brands(market: dict[str, Any]) -> list[str]:
    """从市场配置的竞品列表中提取品牌名"""
    brands: list[str] = []
    competitors = market.get("competitors")
    if not isinstance(competitors, list):
        return brands
    for item in competitors:
        if not isinstance(item, dict):
            continue
        # 优先取 brand 字段
        brand = str(item.get("brand") or "").strip()
        if brand:
            brands.append(brand)
            continue
        # 没有 brand 字段时，用 product_name 作为品牌代理
        name = str(item.get("product_name") or item.get("name") or "").strip()
        if name:
            brands.append(name)
    return brands


def _infer_preferred_brands(
    product_brand: str,
    competitor_brands: list[str],
    decision_style: str,
    local_index: int,
    price_sensitivity: str,
) -> list[str]:
    """根据决策风格和价格敏感度推导 agent 的品牌偏好。

    数学逻辑：消费者离散选择模型中，品牌偏好是二元哑变量。
    - 品牌信任型消费者更可能偏好特定品牌
    - 价格敏感型消费者更少关注品牌，偏好列表更短
    - 不同 agent 偏好不同品牌组合，模拟真实市场品牌分布
    """
    all_brands = list(dict.fromkeys(
        ([product_brand] if product_brand else [])
        + competitor_brands
    ))
    if not all_brands:
        return []

    style = str(decision_style or "")
    sensitivity = str(price_sensitivity or "medium")

    # 品牌信任型：偏好 1-2 个品牌，其中大概率包含产品品牌
    if "品牌" in style:
        if product_brand and local_index % 3 != 0:
            return [product_brand]
        # 部分品牌信任型消费者偏好竞品品牌
        alt = [b for b in all_brands if b != product_brand]
        if alt:
            idx = local_index % len(alt)
            return [alt[idx]]
        return [product_brand] if product_brand else []

    # 价格敏感型：约 40% 有品牌偏好（从 ~25% 提升）
    if sensitivity == "high":
        if local_index % 5 < 2:
            return [product_brand] if product_brand else (competitor_brands[:1] if competitor_brands else [])
        return []

    # 理性比较型 / 参数敏感型：约 40% 有品牌偏好（从 ~20% 提升）
    if local_index % 5 < 2:
        return [product_brand] if product_brand else (competitor_brands[:1] if competitor_brands else [])
    if local_index % 7 == 1 and competitor_brands:
        idx = local_index % len(competitor_brands)
        return [competitor_brands[idx]]

    # 其余 fallback：仍有 ~30% 概率分配品牌
    if local_index % 3 == 0:
        return [product_brand] if product_brand else (competitor_brands[:1] if competitor_brands else [])
    return []


def allocate_segment_agent_counts(segments: list[dict[str, Any]], count: int) -> list[int]:
    if not segments:
        return []
    total = max(int(count), len(segments))
    counts = [1 for _ in segments]
    remaining = total - len(segments)
    if remaining <= 0:
        return counts
    weights = [max(float(segment.get("ratio") or 0), 0.0) or 1.0 for segment in segments]
    weight_total = sum(weights)
    raw_additions = [remaining * weight / weight_total for weight in weights]
    additions = [int(value) for value in raw_additions]
    for index, value in enumerate(additions):
        counts[index] += value
    leftover = remaining - sum(additions)
    order = sorted(range(len(segments)), key=lambda index: (raw_additions[index] - additions[index], -index), reverse=True)
    for index in order[:leftover]:
        counts[index] += 1
    return counts


def generate_agents(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    count: int | None = None,
) -> dict[str, Any]:
    product = snapshot.get("product_definition") or {}
    market = snapshot.get("market_config") or {}
    target_crowd = market.get("target_crowd") or market.get("crowd") or "目标用户"
    segments = normalize_crowd_segments(market)
    if not segments:
        segments = [
            {
                "name": target_crowd,
                "ratio": 100,
                "is_custom": False,
                "profile": normalize_crowd_profile(market),
            }
        ]
    category = product.get("subcategory") or product.get("category") or "目标品类"
    product_brand = _extract_product_brand(product)
    competitor_brands = _extract_competitor_brands(market)
    user_items = evidence_items(evidence, *USER_EVIDENCE_KEYS, *MARKET_EVIDENCE_KEYS)
    common_snippets = [str(item.get("snippet") or "") for item in user_items]
    profile_text = crowd_profile_text(market)
    if profile_text:
        common_snippets.append(profile_text)

    params = snapshot.get("simulation_params") if isinstance(snapshot.get("simulation_params"), dict) else {}
    requested_count = count if count is not None else representative_agent_count(params.get("sample_size") or 1000, social_network_config(snapshot))
    agents: list[dict[str, Any]] = []
    allocations = allocate_segment_agent_counts(segments, requested_count)
    agent_index = 0
    for segment, segment_count in zip(segments, allocations):
        segment_name = str(segment.get("name") or "目标用户")
        ratio = int(segment.get("ratio") or 0)
        profile = normalize_profile(segment.get("profile"), segment_name)
        snippets = [
            *common_snippets,
            crowd_profile_text({"crowd_segments": [segment]}),
        ]
        feature_preferences = extract_feature_preferences(snippets, product)
        profile_features = profile.get("feature_priorities") if isinstance(profile.get("feature_priorities"), list) else []
        if profile_features:
            feature_preferences = list(dict.fromkeys([*profile_features, *feature_preferences]))[:8]
        category_preference = infer_category_preference(snippets, category)
        sample_weight = round((ratio / 100) / segment_count, 8) if segment_count else 0.0
        for local_index in range(segment_count):
            agent_index += 1
            price_sensitivity = infer_price_sensitivity(snippets, local_index, profile.get("price_sensitivity"))
            offset = local_index % len(feature_preferences)
            preferred_features = feature_preferences[offset:] + feature_preferences[:offset]
            decision_style = ["理性比较型", "参数敏感型", "价格敏感型", "品牌信任型", "功能优先型", "综合权衡型"][local_index % 6]
            agents.append(
                {
                    "agent_id": f"agent_{agent_index:03d}",
                    "segment": segment_name,
                    "segment_ratio": ratio,
                    "sample_weight": sample_weight,
                    "age_range": profile.get("age_range"),
                    "city_tier": profile.get("city_tier"),
                    "income_level": profile.get("income_level"),
                    "life_stage": profile.get("life_stage"),
                    "category_preference": category_preference if local_index % 4 else category,
                    "price_sensitivity": price_sensitivity,
                    "preferred_features": preferred_features[:3],
                    "preferred_brands": _infer_preferred_brands(
                        product_brand, competitor_brands, decision_style, local_index, price_sensitivity
                    ),
                    "channel_preferences": profile.get("channel_preferences") or [],
                    "purchase_motivations": profile.get("purchase_motivations") or [],
                    "risk_concerns": profile.get("risk_concerns") or [],
                    "decision_style": decision_style,
                    "budget_band": product.get("price_cny") or "待确认",
                    "evidence_refs": [
                        item.get("source")
                        for item in user_items[agent_index - 1 : agent_index + 1]
                        if item.get("source")
                    ],
                }
            )
    network = attach_social_network(snapshot, agents)
    for agent in agents:
        agent["base_maut_scores"] = compute_base_maut_scores(snapshot, agent)
    return {
        "prompt_version": PROMPT_VERSION,
        "agents": agents,
        "social_network": network,
        "generation_basis": {
            "target_crowd": target_crowd,
            "crowd_profile": normalize_crowd_profile(market),
            "crowd_segments": segments,
            "category": category,
            "evidence_items": len(user_items),
            "representative_agent_count": len(agents),
        },
    }
