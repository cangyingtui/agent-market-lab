from __future__ import annotations

from typing import Any


PROFILE_LABELS = {
    "age_range": "年龄段",
    "city_tier": "城市层级",
    "income_level": "收入水平",
    "life_stage": "职业/家庭阶段",
    "price_sensitivity": "价格敏感度",
    "feature_priorities": "功能优先级",
    "channel_preferences": "渠道偏好",
    "purchase_motivations": "购买动机",
    "risk_concerns": "风险顾虑",
    "custom_description": "补充描述",
}


def as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [as_text(item) for item in value if as_text(item)]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return []


def normalize_profile(raw_profile: dict[str, Any] | None, name: str = "") -> dict[str, Any]:
    raw = raw_profile if isinstance(raw_profile, dict) else {}
    profile = {
        "name": name or as_text(raw.get("name")) or "目标用户",
        "age_range": as_text(raw.get("age_range") or raw.get("age")),
        "city_tier": as_text(raw.get("city_tier") or raw.get("city")),
        "income_level": as_text(raw.get("income_level") or raw.get("income")),
        "life_stage": as_text(raw.get("life_stage") or raw.get("occupation") or raw.get("usage")),
        "price_sensitivity": as_text(raw.get("price_sensitivity") or "medium"),
        "feature_priorities": as_list(raw.get("feature_priorities") or raw.get("preferences")),
        "channel_preferences": as_list(raw.get("channel_preferences") or raw.get("channels")),
        "purchase_motivations": as_list(raw.get("purchase_motivations") or raw.get("motivations")),
        "risk_concerns": as_list(raw.get("risk_concerns") or raw.get("concerns")),
        "custom_description": as_text(raw.get("custom_description") or raw.get("description")),
    }
    return {key: value for key, value in profile.items() if value not in ("", [])}


def _ratio_value(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and float(value).is_integer():
        return int(value)
    return default


def normalize_crowd_segments(market_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    market = market_config if isinstance(market_config, dict) else {}
    raw_segments = market.get("crowd_segments")
    segments: list[dict[str, Any]] = []
    if isinstance(raw_segments, list):
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            name = as_text(item.get("name") or item.get("segment"))
            if not name:
                continue
            segments.append(
                {
                    "name": name,
                    "ratio": _ratio_value(item.get("ratio")),
                    "is_custom": bool(item.get("is_custom", False)),
                    "profile": normalize_profile(item.get("profile"), name),
                }
            )
    if segments:
        return segments

    raw_profile = market.get("crowd_profile") if isinstance(market.get("crowd_profile"), dict) else {}
    target = as_text(market.get("target_crowd") or market.get("crowd") or raw_profile.get("name"))
    if not target and not raw_profile:
        return []
    return [
        {
            "name": target or "目标用户",
            "ratio": 100,
            "is_custom": False,
            "profile": normalize_profile(raw_profile, target or "目标用户"),
        }
    ]


def validate_crowd_segments(market_config: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str | None]:
    market = market_config if isinstance(market_config, dict) else {}
    if "crowd_segments" not in market:
        return normalize_crowd_segments(market), None
    raw_segments = market.get("crowd_segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        return [], "CROWD_RATIO_INVALID"

    segments: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in raw_segments:
        if not isinstance(item, dict):
            return [], "CROWD_RATIO_INVALID"
        name = as_text(item.get("name") or item.get("segment"))
        ratio = _ratio_value(item.get("ratio"), -1)
        if not name or name in names or ratio <= 0:
            return [], "CROWD_RATIO_INVALID"
        names.add(name)
        segments.append(
            {
                "name": name,
                "ratio": ratio,
                "is_custom": bool(item.get("is_custom", False)),
                "profile": normalize_profile(item.get("profile"), name),
            }
        )
    if sum(int(item["ratio"]) for item in segments) != 100:
        return segments, "CROWD_RATIO_TOTAL_INVALID"
    return segments, None


def primary_crowd_segment(market_config: dict[str, Any] | None) -> dict[str, Any] | None:
    segments = normalize_crowd_segments(market_config)
    if not segments:
        return None
    return max(enumerate(segments), key=lambda pair: (int(pair[1].get("ratio") or 0), -pair[0]))[1]


def canonicalize_market_crowds(market_config: dict[str, Any] | None) -> dict[str, Any]:
    market = dict(market_config) if isinstance(market_config, dict) else {}
    segments = normalize_crowd_segments(market)
    if not segments:
        return market
    market["crowd_segments"] = segments
    primary = primary_crowd_segment({"crowd_segments": segments}) or segments[0]
    market["target_crowd"] = primary["name"]
    market["crowd_profile"] = primary["profile"]
    return market


def normalize_crowd_profile(market_config: dict[str, Any] | None) -> dict[str, Any]:
    market = market_config if isinstance(market_config, dict) else {}
    primary = primary_crowd_segment(market)
    if primary:
        return normalize_profile(primary.get("profile"), as_text(primary.get("name")))
    raw = market.get("crowd_profile") if isinstance(market.get("crowd_profile"), dict) else {}
    target = as_text(market.get("target_crowd") or market.get("crowd") or raw.get("name"))
    return normalize_profile(raw, target)


def _profile_text(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, label in PROFILE_LABELS.items():
        value = profile.get(key)
        if isinstance(value, list) and value:
            parts.append(f"{label}:{'、'.join(value)}")
        elif value:
            parts.append(f"{label}:{value}")
    return " ".join(parts)


def crowd_profile_text(market_config: dict[str, Any] | None) -> str:
    segments = normalize_crowd_segments(market_config)
    if segments:
        return "；".join(
            " ".join(
                item
                for item in (
                    f"目标人群:{segment['name']}",
                    f"占比:{segment['ratio']}%",
                    _profile_text(segment["profile"]),
                )
                if item
            )
            for segment in segments
        )
    profile = normalize_crowd_profile(market_config)
    text = _profile_text(profile)
    return f"目标人群:{profile['name']} {text}".strip() if profile.get("name") else text
