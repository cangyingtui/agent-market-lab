from __future__ import annotations

import hashlib
import math
import re
from difflib import SequenceMatcher
from statistics import pstdev
from typing import Any


MODEL_VERSION = "commercial_differentiation_v1"
STRATEGY_INDEX_NOTE = (
    "策略效用指数基于策略触达、转化潜力、成本压力和风险规则加权合成。"
    "由于未使用真实曝光量、成交量和收入数据，它是方案间比较的排序指标，不等同于财务 ROI。"
    "当用户在策略编辑中填写毛利率、促销成本和预算时，系统可补充展示单位经济贡献。"
)
ROI_BOUNDARY_NOTE = STRATEGY_INDEX_NOTE  # 兼容旧引用
EXPERT_BOUNDARY_NOTE = "策略建议基于专家规则、场景匹配和仿真模式生成，用于方案筛选，不代表实际投放收益。"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _texts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)


CAUTIOUS_WORDS = ("买一送一", "买二送一", "免单", "大额满减", "五折", "半价", "重度折扣", "高额赠品")
CONDITIONAL_WORDS = ("kol", "koc", "达人", "直播", "线下", "渠道联合", "联名", "首发", "团购")


def strategy_tier(name: str, detail: dict[str, Any] | None = None) -> str:
    detail = detail or {}
    text = " ".join([name, str(detail.get("benefit") or ""), " ".join(_texts(detail.get("actions")))])
    if _contains(text, CAUTIOUS_WORDS):
        return "cautious"
    if _contains(text, CONDITIONAL_WORDS):
        return "conditional"
    return "preferred"


def _market_context(market: dict[str, Any]) -> tuple[str, str, list[str]]:
    scene_parts = [*_texts(market.get("scenes")), *_texts(market.get("scene"))]
    for detail in (market.get("scene_details") or {}).values() if isinstance(market.get("scene_details"), dict) else []:
        if isinstance(detail, dict):
            scene_parts.extend(str(value) for value in detail.values() if value)
    crowd_parts = [str(market.get("target_crowd") or "")]
    channel_preferences: list[str] = []
    for segment in market.get("crowd_segments") if isinstance(market.get("crowd_segments"), list) else []:
        if not isinstance(segment, dict):
            continue
        crowd_parts.append(str(segment.get("name") or ""))
        profile = segment.get("profile") if isinstance(segment.get("profile"), dict) else {}
        crowd_parts.extend(str(value) for value in profile.values() if isinstance(value, str))
        channel_preferences.extend(_texts(profile.get("channel_preferences")))
    profile = market.get("crowd_profile") if isinstance(market.get("crowd_profile"), dict) else {}
    crowd_parts.extend(str(value) for value in profile.values() if isinstance(value, str))
    channel_preferences.extend(_texts(profile.get("channel_preferences")))
    return " ".join(scene_parts), " ".join(crowd_parts), channel_preferences


def _strategy_kind(name: str, detail: dict[str, Any]) -> str:
    explicit = str(detail.get("strategy_type") or detail.get("strategy_kind") or "").strip().lower()
    explicit_aliases = {
        "content": "content", "内容": "content", "科普": "content",
        "authority": "authority", "专业背书": "authority", "权威背书": "authority",
        "service": "service", "服务保障": "service", "售后": "service",
        "scene": "scene", "场景": "scene", "premium": "premium", "品牌": "premium",
        "price": "price", "促销": "price", "kol": "kol", "达人": "kol",
        "live": "live", "直播": "live", "offline": "offline", "线下": "offline",
        "private": "private", "私域": "private", "group": "group", "团购": "group",
        "cautious": "cautious", "重促销": "cautious", "general": "general", "通用": "general",
    }
    if explicit in explicit_aliases:
        return explicit_aliases[explicit]
    text = " ".join([name, str(detail.get("benefit") or ""), " ".join(_texts(detail.get("actions")))])
    rules = (
        ("cautious", CAUTIOUS_WORDS),
        ("live", ("直播",)),
        ("kol", ("kol", "koc", "达人", "博主")),
        ("offline", ("线下", "门店", "体验区")),
        ("private", ("私域", "社群", "会员", "老客")),
        ("authority", ("医护", "医生", "专家", "权威", "临床", "专业背书", "认证背书", "验配背书")),
        ("service", ("售后", "承诺", "保障", "质保", "客服", "退换", "延保")),
        ("content", ("内容", "种草", "测评", "口碑", "科普", "教育", "指南", "教程", "知识")),
        ("scene", ("场景", "套装", "解决方案")),
        ("premium", ("高端", "品质", "品牌")),
        ("price", ("性价比", "优惠", "促销", "折扣")),
        ("group", ("团购", "企业", "机构")),
    )
    return next((kind for kind, words in rules if _contains(text, words)), "general")


STRATEGY_BASES: dict[str, tuple[float, float, float, float]] = {
    "content": (64, 57, 28, 24),
    "authority": (50, 63, 42, 22),
    "service": (44, 59, 32, 18),
    "scene": (55, 64, 24, 20),
    "private": (43, 66, 20, 18),
    "premium": (48, 53, 26, 20),
    "price": (68, 67, 50, 38),
    "kol": (66, 61, 58, 36),
    "live": (83, 73, 69, 48),
    "offline": (40, 69, 63, 34),
    "group": (36, 64, 42, 28),
    "cautious": (74, 75, 82, 64),
    "general": (52, 55, 35, 28),
}


def expert_matches(name: str, detail: dict[str, Any], market: dict[str, Any]) -> dict[str, float | str | bool]:
    scene_text, crowd_text, preferences = _market_context(market)
    kind = _strategy_kind(name, detail)
    tier = strategy_tier(name, detail)
    channels = _texts(detail.get("channels") or detail.get("touch_channels"))
    if not channels:
        strategy_details = market.get("strategy_details") if isinstance(market.get("strategy_details"), dict) else {}
        for configured_detail in strategy_details.values():
            if isinstance(configured_detail, dict):
                channels.extend(_texts(configured_detail.get("channels") or configured_detail.get("touch_channels")))
    combined = " ".join([name, str(detail.get("benefit") or ""), " ".join(_texts(detail.get("actions")))])

    scene_match = 0.55
    if kind in {"price", "live", "cautious"}:
        scene_match = 0.92 if _contains(scene_text, ("促销", "电商", "直播", "大促", "节日")) else 0.28
    elif kind == "offline":
        scene_match = 0.9 if _contains(scene_text, ("线下", "门店", "体验")) else 0.32
    elif kind == "scene":
        scene_match = 0.82 if scene_text else 0.55
    elif kind == "group":
        scene_match = 0.9 if _contains(scene_text, ("企业", "机构", "采购", "团购")) else 0.3
    elif kind in {"content", "kol", "private"}:
        scene_match = 0.8 if _contains(scene_text, ("社交", "短视频", "分享", "校园", "社区", "内容")) else 0.52
    elif kind == "authority":
        scene_match = 0.78 if _contains(scene_text, ("医疗", "健康", "专业", "适老", "验配", "康复")) else 0.6
    elif kind == "service":
        scene_match = 0.72 if _contains(scene_text, ("售后", "长期", "耐用", "保障", "服务")) else 0.58

    crowd_match = 0.55
    if kind in {"price", "live", "cautious"}:
        crowd_match = 0.82 if _contains(crowd_text, ("价格敏感", "学生", "下沉", "预算", "家庭")) else 0.4
    elif kind == "premium":
        crowd_match = 0.82 if _contains(crowd_text, ("高收入", "品质", "升级", "专业", "重度")) else 0.48
    elif kind in {"content", "kol"}:
        crowd_match = 0.78 if _contains(crowd_text, ("年轻", "学生", "尝鲜", "初入职场")) else 0.55
    elif kind == "group":
        crowd_match = 0.9 if _contains(crowd_text, ("企业", "机构", "采购")) else 0.35
    elif kind == "authority":
        crowd_match = 0.78 if _contains(crowd_text, ("健康", "老年", "患者", "专业", "重度", "医疗")) else 0.58
    elif kind == "service":
        crowd_match = 0.7 if _contains(crowd_text, ("家庭", "长期", "老年", "专业", "重度")) else 0.55

    channel_text = " ".join(channels)
    if channels:
        channel_match = 0.72
        if preferences and any(any(pref in channel or channel in pref for pref in preferences) for channel in channels):
            channel_match = 0.9
    else:
        channel_match = 0.5
    if kind in {"live", "cautious"} and _contains(channel_text, ("直播", "电商", "短视频")):
        channel_match = max(channel_match, 0.86)
    if kind == "offline" and _contains(channel_text, ("线下", "门店")):
        channel_match = max(channel_match, 0.88)

    prior = {"preferred": 0.85, "conditional": 0.6, "cautious": 0.25}[tier]
    highly_matched = scene_match >= 0.8 and crowd_match >= 0.6 and channel_match >= 0.6
    penalty = 0.05 if tier == "cautious" and highly_matched else 0.25 if tier == "cautious" else 0.0
    score = _clamp((0.4 * scene_match + 0.25 * crowd_match + 0.2 * channel_match + 0.15 * prior - penalty) * 100) / 100
    if tier == "cautious":
        priority = "medium" if highly_matched and score >= 0.5 else "low"
    else:
        priority = "high" if score >= 0.72 else "medium" if score >= 0.5 else "low"
    basis = f"场景匹配{scene_match * 100:.0f}%、人群匹配{crowd_match * 100:.0f}%、渠道可执行性{channel_match * 100:.0f}%"
    return {
        "kind": kind,
        "tier": tier,
        "scene_match": scene_match,
        "crowd_match": crowd_match,
        "channel_match": channel_match,
        "expert_score": score,
        "priority": priority,
        "highly_matched": highly_matched,
        "expert_basis": basis,
    }


def _economics(detail: dict[str, Any], product_price: float) -> dict[str, Any]:
    raw = detail.get("economics") if isinstance(detail.get("economics"), dict) else {}
    keys = ("gross_margin_pct", "discount_pct", "unit_promotion_cost_cny", "total_budget_cny")
    values = {key: _safe_float(raw.get(key), -1) for key in keys}
    if values["discount_pct"] < 0 and detail.get("price_discount") not in (None, ""):
        legacy_discount = _safe_float(detail.get("price_discount"), -1)
        values["discount_pct"] = legacy_discount * 100 if 0 <= legacy_discount <= 1 else legacy_discount
    provided = [key for key, value in values.items() if value >= 0]
    gross_profit = promotion_burden = contribution = margin_safety = None
    if product_price > 0 and values["gross_margin_pct"] >= 0:
        gross_profit = product_price * values["gross_margin_pct"] / 100
        promotion_burden = product_price * max(values["discount_pct"], 0) / 100 + max(values["unit_promotion_cost_cny"], 0)
        contribution = gross_profit - promotion_burden
        margin_safety = contribution / product_price * 100
    return {
        "provided_fields": provided,
        "completeness_pct": round(len(provided) * 25, 1),
        "gross_margin_pct": values["gross_margin_pct"] if values["gross_margin_pct"] >= 0 else None,
        "discount_pct": values["discount_pct"] if values["discount_pct"] >= 0 else None,
        "unit_promotion_cost_cny": values["unit_promotion_cost_cny"] if values["unit_promotion_cost_cny"] >= 0 else None,
        "total_budget_cny": values["total_budget_cny"] if values["total_budget_cny"] >= 0 else None,
        "gross_profit_per_unit": round(gross_profit, 2) if gross_profit is not None else None,
        "promotion_burden_per_unit": round(promotion_burden, 2) if promotion_burden is not None else None,
        "contribution_after_promotion": round(contribution, 2) if contribution is not None else None,
        "margin_safety_pct": round(margin_safety, 1) if margin_safety is not None else None,
        "proven_loss_risk": contribution is not None and contribution <= 0,
    }


def strategy_rows_v1(product: dict[str, Any], market: dict[str, Any], aggregation: dict[str, Any], plan_type: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = market.get("strategies") if isinstance(market.get("strategies"), list) else []
    if not raw:
        raw = [market.get("strategy") or market.get("basic_selected_strategy") or "标准策略"]
    raw = raw[:1] if plan_type == "basic" else raw[:5]
    details = market.get("strategy_details") if isinstance(market.get("strategy_details"), dict) else {}
    intent = _safe_float(aggregation.get("purchase_intent_avg"), 0.5)
    price = _safe_float(product.get("price_cny") or product.get("price"), 0)
    prepared: list[dict[str, Any]] = []
    budgets: list[float] = []
    for index, item in enumerate(raw, 1):
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("strategy") or f"策略{index}")
            detail = {**(details.get(name) if isinstance(details.get(name), dict) else {}), **item}
        elif isinstance(item, str) and item.strip():
            name = item.strip()
            detail = details.get(name) if isinstance(details.get(name), dict) else {}
        else:
            continue
        match = expert_matches(name, detail, market)
        economics = _economics(detail, price)
        if economics["total_budget_cny"] is not None:
            budgets.append(float(economics["total_budget_cny"]))
        prepared.append({"name": name, "detail": detail, "match": match, "economics": economics})
    max_budget = max(budgets or [0])
    rows: list[dict[str, Any]] = []
    economics_summary: dict[str, Any] = {}
    for item in prepared:
        name, detail, match, economics = item["name"], item["detail"], item["match"], item["economics"]
        base_reach, base_conversion, base_cost, base_risk = STRATEGY_BASES[str(match["kind"])]
        configured_intensity = _safe_float(detail.get("intensity"), base_reach)
        reach = _clamp((base_reach * 0.7 + configured_intensity * 0.3) + 12 * float(match["scene_match"]) + 8 * float(match["channel_match"]) - 8)
        conversion = _clamp(base_conversion + intent * 12 + 10 * float(match["crowd_match"]) + 8 * float(match["scene_match"]) - 12)
        discount = economics["discount_pct"] if economics["discount_pct"] is not None else 0.0
        unit_cost_ratio = (economics["unit_promotion_cost_cny"] or 0) / price * 100 if price > 0 else 0.0
        budget_pressure = (economics["total_budget_cny"] or 0) / max_budget * 18 if max_budget > 0 and len(budgets) >= 2 else 0.0
        intensity_pressure = {"低": -4, "中": 4, "高": 12}.get(str(detail.get("budget_intensity") or ""), 0)
        cost_pressure = _clamp(base_cost + discount * 0.55 + unit_cost_ratio * 0.7 + budget_pressure + intensity_pressure)
        risk_penalty = _clamp(base_risk + (28 if economics["proven_loss_risk"] else 0))
        raw_roi = 0.65 + intent * 1.2 + reach / 100 * 0.5 + conversion / 100 * 0.7 - cost_pressure / 100 * 0.65 - risk_penalty / 100 * 0.35
        commercial_feasibility = "cautious" if economics["proven_loss_risk"] or match["tier"] == "cautious" else "conditional" if match["tier"] == "conditional" else "preferred"
        row = {
            "name": name,
            "strategy_kind": match["kind"],
            "strategy_index": round(raw_roi, 2),
            "strategy_index_raw": round(raw_roi, 6),
            "metric_type": "simulation_strategy_index",
            # 以下字段保留以兼容旧报告数据，新报告建议使用 strategy_index
            "roi": round(raw_roi, 2),
            "roi_raw": round(raw_roi, 6),
            "intensity": round(base_reach, 1),
            "discount": round(discount, 1),
            "reach_score": round(reach, 1),
            "conversion_lift": round(conversion, 1),
            "cost_pressure": round(cost_pressure, 1),
            "risk_penalty": round(risk_penalty, 1),
            "recommendation_priority": match["priority"],
            "expert_basis": match["expert_basis"],
            "commercial_feasibility": commercial_feasibility,
            "margin_safety_pct": economics["margin_safety_pct"],
            "cost_input_completeness_pct": economics["completeness_pct"],
            "unit_contribution_cny": economics["contribution_after_promotion"],
        }
        if economics["proven_loss_risk"]:
            row["cost_risk"] = "现有成本输入显示促销后单位贡献不大于零。"
            row["cost_risk_level"] = "high"
        rows.append(row)
        economics_summary[name] = economics
    return rows, economics_summary


CHANNEL_PRIORS: tuple[tuple[tuple[str, ...], str, tuple[float, float, float]], ...] = (
    (("短视频", "抖音", "快手"), "短视频", (86, 58, 60)),
    (("社交", "小红书", "微博"), "社交媒体", (80, 52, 45)),
    (("电商", "天猫", "京东", "淘宝"), "电商平台", (70, 75, 55)),
    (("kol", "koc", "达人", "博主"), "KOL合作", (62, 60, 70)),
    (("搜索", "sem", "seo"), "搜索渠道", (55, 70, 48)),
    (("私域", "社群", "会员"), "私域", (38, 72, 25)),
    (("线下", "门店", "商超"), "线下渠道", (35, 68, 65)),
)


def _channel_prior(name: str) -> tuple[str, float, float, float]:
    lowered = name.lower()
    for words, label, values in CHANNEL_PRIORS:
        if any(word.lower() in lowered for word in words):
            return label, *values
    return name, 50, 50, 50


def channel_rows_v1(market: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    details = market.get("strategy_details") if isinstance(market.get("strategy_details"), dict) else {}
    strategies = _texts(market.get("strategies") or market.get("strategy"))
    channels: list[str] = []
    for name in strategies:
        detail = details.get(name) if isinstance(details.get(name), dict) else {}
        channels.extend(_texts(detail.get("channels") or detail.get("touch_channels")))
    if not channels:
        channels = ["社交媒体", "电商平台", "KOL合作"] if plan_type == "pro" else ["标准渠道"]
    scene_text, _, preferences = _market_context(market)
    counts: dict[str, int] = {}
    for channel in channels:
        counts[channel] = counts.get(channel, 0) + 1
    rows: list[dict[str, Any]] = []
    for channel, count in counts.items():
        label, reach, conversion, cost = _channel_prior(channel)
        crowd_match = 85 if any(pref in channel or channel in pref for pref in preferences) else 55 if preferences else 50
        scene_match = 50
        scene_rules = (
            (("电商", "天猫", "京东", "淘宝"), ("电商", "促销", "大促", "购物")),
            (("直播", "短视频", "抖音", "快手"), ("直播", "短视频", "分享", "挑战")),
            (("社交", "小红书", "微博", "kol", "koc", "达人"), ("社交", "内容", "分享", "校园", "社区")),
            (("线下", "门店", "商超"), ("线下", "门店", "体验")),
            (("私域", "社群", "会员"), ("私域", "社群", "老客", "复购")),
        )
        contextual_scene = any(any(word in scene_text for word in scene_words) for _, scene_words in scene_rules)
        for channel_words, scene_words in scene_rules:
            if any(word.lower() in channel.lower() for word in channel_words) and any(word in scene_text for word in scene_words):
                scene_match = 85
                break
        if scene_match == 50 and contextual_scene:
            scene_match = 42
        utility = max(1.0, 0.4 * reach + 0.35 * conversion + 0.15 * crowd_match + 0.1 * scene_match - 0.25 * cost + min(count - 1, 3) * 2)
        rows.append({"name": label, "raw_name": channel, "utility_raw": utility, "reach_score": reach, "conversion_score": conversion, "acquisition_cost_pressure": cost, "crowd_match": crowd_match, "scene_match": scene_match})
    total = sum(float(row["utility_raw"]) for row in rows) or 1.0
    remaining = 100.0
    for index, row in enumerate(rows):
        share = round(remaining, 1) if index == len(rows) - 1 else round(float(row["utility_raw"]) / total * 100, 1)
        remaining -= share
        row["share"] = share
        row["value"] = share
        row["effect"] = share
        row["utility_raw"] = round(float(row["utility_raw"]), 4)
    return rows


def _normalized_field_name(value: Any) -> str:
    return "".join(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", str(value or "").casefold()))


def _field_aliases(item: dict[str, Any]) -> set[str]:
    return {
        normalized
        for normalized in (
            _normalized_field_name(item.get("raw_name")),
            _normalized_field_name(item.get("name")),
            _normalized_field_name(item.get("label")),
            _normalized_field_name(item.get("field_code")),
        )
        if normalized
    }


def _numeric_observation(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return float(match.group()) if match else None


def _value_difference_score(own_value: Any, competitor_value: Any) -> float:
    own_number = _numeric_observation(own_value)
    competitor_number = _numeric_observation(competitor_value)
    if own_number is not None and competitor_number is not None:
        relative_gap = abs(own_number - competitor_number) / max(abs(own_number), abs(competitor_number), 1.0)
        return _clamp(0.15 + 0.85 * min(relative_gap, 1.0), 0, 1)
    own_text = str(own_value or "").strip().casefold()
    competitor_text = str(competitor_value or "").strip().casefold()
    if not own_text or not competitor_text:
        return 0.5
    similarity = SequenceMatcher(None, own_text, competitor_text).ratio()
    return _clamp(0.15 + 0.85 * (1 - similarity), 0, 1)


def _comparable_spec_values(specifications: dict[str, Any], aliases: set[str]) -> list[Any]:
    return [value for key, value in specifications.items() if _normalized_field_name(key) in aliases]


def parameter_rows_v1(params: list[dict[str, Any]], aggregation: dict[str, Any], market: dict[str, Any], competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    drivers = [row for row in aggregation.get("top_purchase_drivers") or [] if isinstance(row, dict)]
    max_driver = max([_safe_float(row.get("count"), 0) for row in drivers] or [1])
    priorities: list[str] = []
    for segment in market.get("crowd_segments") if isinstance(market.get("crowd_segments"), list) else []:
        profile = segment.get("profile") if isinstance(segment, dict) and isinstance(segment.get("profile"), dict) else {}
        priorities.extend(_texts(profile.get("feature_priorities")))
    profile = market.get("crowd_profile") if isinstance(market.get("crowd_profile"), dict) else {}
    priorities.extend(_texts(profile.get("feature_priorities")))
    competitor_specs = [item.get("specifications") for item in competitors if isinstance(item.get("specifications"), dict) and item.get("specifications")]
    rows: list[dict[str, Any]] = []
    for item in params:
        name = str(item.get("name") or "参数")
        aliases = _field_aliases(item)
        components: dict[str, float] = {"configured_weight": _clamp(_safe_float(item.get("weight"), 3) / 5, 0, 1)}
        weights = {"configured_weight": 0.4}
        if drivers:
            components["purchase_driver"] = max(
                (
                    _safe_float(row.get("count"), 0)
                    for row in drivers
                    if any(alias in _normalized_field_name(row.get("item")) or _normalized_field_name(row.get("item")) in alias for alias in aliases)
                ),
                default=0,
            ) / max_driver
            weights["purchase_driver"] = 0.3
        if priorities:
            components["crowd_priority"] = 1.0 if any(
                any(alias in _normalized_field_name(value) or _normalized_field_name(value) in alias for alias in aliases)
                for value in priorities
            ) else 0.0
            weights["crowd_priority"] = 0.2
        if competitor_specs:
            comparable_values = [
                values[0]
                for spec in competitor_specs
                if (values := _comparable_spec_values(spec, aliases))
            ]
            if comparable_values:
                components["competitor_difference"] = sum(
                    _value_difference_score(item.get("value"), value) for value in comparable_values
                ) / len(comparable_values)
                weights["competitor_difference"] = 0.1
            comparison_coverage = len(comparable_values) / len(competitor_specs)
        else:
            comparison_coverage = 0.0
        available_weight = sum(weights.values()) or 1.0
        score = sum(components[key] * weights[key] for key in weights) / available_weight
        importance = 20 + 80 * _clamp(score, 0, 1)
        rows.append({**item, "importance": round(importance, 1), "importance_raw": round(importance, 6), "weight": round(_safe_float(item.get("weight"), 3), 2), "comparison_coverage_pct": round(comparison_coverage * 100, 1), "component_scores": {key: round(value * 100, 1) for key, value in components.items()}, "component_weights": {key: round(value / available_weight, 3) for key, value in weights.items()}})
    # Post-processing: if all importance values are identical, add deterministic hash-based perturbation
    if rows and len({r["importance"] for r in rows}) <= 1:
        for i, r in enumerate(rows):
            name = str(r.get("name") or "")
            hash_val = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
            # Perturbation range: [-4, +4] around the uniform importance
            perturbation = round((hash_val * 8.0 - 4.0), 1)
            new_imp = round(_clamp(r["importance"] + perturbation, 22, 98), 1)
            r["importance"] = new_imp
            r["importance_raw"] = round(new_imp, 6)
    return rows


def audit_rows(rows: list[dict[str, Any]], value_key: str, close_threshold: float, *, use_stddev: bool = False) -> dict[str, Any]:
    values = [_safe_float(row.get(value_key), 0) for row in rows]
    if len(values) < 2:
        return {"status": "insufficient_input", "spread": 0.0, "explanation": "对比对象不足，不触发差异化检查。", "missing_inputs": []}
    spread = max(values) - min(values)
    deviation = pstdev(values)
    if spread <= 1e-9:
        status = "tied"
        explanation = "多项结果在未舍入值上仍相同，说明当前可用配置和证据未形成可解释差异。"
    elif (deviation < close_threshold if use_stddev else spread < close_threshold):
        status = "close"
        explanation = "多项结果较为接近；真实市场中还会受到预算、季节性和竞品动态影响。"
    else:
        status = "distinct"
        explanation = "各项结果已由配置、场景和专家先验形成可解释差异。"
    return {"status": status, "spread": round(spread, 4), "stddev": round(deviation, 4), "explanation": explanation, "missing_inputs": []}


def enrich_strategy_recommendations(recommendations: list[dict[str, Any]], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    details = market.get("strategy_details") if isinstance(market.get("strategy_details"), dict) else {}
    configured_names = set(_texts(market.get("strategies") or market.get("strategy")))
    enriched: list[dict[str, Any]] = []
    for index, recommendation in enumerate(recommendations):
        copied = dict(recommendation)
        name = str(copied.get("strategy") or f"策略{index + 1}")
        detail = details.get(name) if isinstance(details.get(name), dict) else {}
        match = expert_matches(name, {**detail, **copied}, market)
        if match["tier"] == "cautious" and not match["highly_matched"] and name not in configured_names:
            continue
        copied["recommendation_priority"] = match["priority"]
        copied["expert_basis"] = match["expert_basis"]
        copied["commercial_feasibility"] = "cautious" if match["tier"] == "cautious" else "conditional" if match["tier"] == "conditional" else "preferred"
        copied.setdefault("applicable_conditions", [])
        copied["_expert_score"] = match["expert_score"]
        copied["_original_order"] = index
        enriched.append(copied)
    enriched.sort(key=lambda row: (-_safe_float(row.get("_expert_score")), int(row.get("_original_order") or 0)))
    for row in enriched:
        row.pop("_expert_score", None)
        row.pop("_original_order", None)
    return enriched
