from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.openai_compat import create_openai_client
from app.crowd_profile import crowd_profile_text, normalize_crowd_profile, normalize_crowd_segments
from app.strategy_recommendations import normalize_strategy_recommendations
from app.time_utils import utc_now_iso
from engine.evidence_utils import (
    MARKET_EVIDENCE_KEYS,
    PRODUCT_EVIDENCE_KEYS,
    USER_EVIDENCE_KEYS,
    evidence_items,
)
from engine.commercial_model import MODEL_VERSION as COMMERCIAL_MODEL_VERSION, enrich_strategy_recommendations


PROMPT_VERSION = "report_builder_v0.2"

REPORT_KEYS = (
    "executive_summary",
    "target_segments",
    "competitor_insights",
    "pricing_analysis",
    "selected_strategies",
    "strategy_recommendations",
    "risk_warnings",
    "evidence_used",
    "scenes",
    "scene_details",
    "scene_detail",
    "strategy_details",
)

BANNED_UNSUPPORTED_TERMS = ("销量第一", "市场份额为", "真实销量", "官方销量")


def compact_json(value: Any, max_chars: int = 12000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:max_chars]


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "、".join(safe_text(item) for item in value if safe_text(item))
    return str(value).strip()


def base_host(url: str) -> str:
    parsed = urlparse(url or "")
    return parsed.netloc or parsed.path or ""


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def classify_user_profile_text(text: str) -> list[str]:
    tags: list[str] = []
    rules = {
        "price_sensitivity": ("价格敏感", "价格段", "促销", "性价比"),
        "feature_preference": ("关键词", "关注", "续航", "防水", "屏幕", "显示", "功能"),
        "category_preference": ("偏好品类", "最偏好", "第二偏好", "第三偏好"),
        "geo_demographic": ("位于", "省", "性别", "年龄", "人均GDP"),
    }
    for tag, keywords in rules.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tags or ["general_profile"]


def split_evidence(evidence: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    structured: list[dict[str, Any]] = []
    user_profile: list[dict[str, Any]] = []
    market: list[dict[str, Any]] = []
    for group, items in evidence.items():
        for item in items:
            copied = dict(item)
            copied["evidence_group"] = group
            if item.get("source_type") == "product_competitor":
                structured.append(copied)
            elif item.get("source_type") == "user_profile":
                raw_text = str(item.get("snippet") or item.get("raw", {}).get("text") or "")
                copied["profile_tags"] = classify_user_profile_text(raw_text)
                user_profile.append(copied)
            else:
                market.append(copied)
    return {
        "structured_product_evidence": structured,
        "user_profile_evidence": user_profile,
        "market_strategy_evidence": market,
    }


def has_missing_product_prices(evidence: dict[str, list[dict[str, Any]]]) -> bool:
    for items in evidence.values():
        for item in items:
            raw = item.get("raw") if isinstance(item, dict) else None
            if isinstance(raw, dict) and raw.get("price_missing"):
                return True
    return False


def product_price_coverage(evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [
        item
        for item in evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS)
        if item.get("source_type") == "product_competitor"
    ]
    total = len(rows)
    priced = 0
    needs_enrichment = 0
    for item in rows:
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        if raw.get("price_cny") is not None:
            priced += 1
        if raw.get("needs_enrichment") or raw.get("price_missing"):
            needs_enrichment += 1
    return {
        "product_evidence_count": total,
        "priced_count": priced,
        "missing_price_count": max(total - priced, 0),
        "price_coverage_pct": round(priced * 100 / total, 1) if total else 0.0,
        "needs_enrichment_count": needs_enrichment,
    }


def validate_report(report: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> list[str]:
    warnings: list[str] = []
    if not report.get("evidence_used"):
        warnings.append("报告缺少 evidence_used，已使用 fallback 证据摘要补齐。")
    text = json.dumps(report, ensure_ascii=False, default=str)
    for term in BANNED_UNSUPPORTED_TERMS:
        if term in text:
            warnings.append(f"报告含有可能缺少证据支撑的表述：{term}")
    if has_missing_product_prices(evidence):
        risk_text = json.dumps(report.get("risk_warnings", []), ensure_ascii=False, default=str)
        pricing_text = json.dumps(report.get("pricing_analysis", {}), ensure_ascii=False, default=str)
        if "价格" not in risk_text + pricing_text or "缺失" not in risk_text + pricing_text:
            warnings.append("部分竞品价格缺失，报告需要提示价格分析不完整。")
    coverage = product_price_coverage(evidence)
    if coverage["product_evidence_count"] and coverage["price_coverage_pct"] < 60:
        warnings.append(f"本次竞品价格覆盖率为 {coverage['price_coverage_pct']}%，建议补充价格后再做定价结论。")
    return warnings


def normalize_report(data: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    report = {key: data.get(key, fallback[key]) for key in REPORT_KEYS}
    if not isinstance(report["target_segments"], list):
        report["target_segments"] = fallback["target_segments"]
    configured_segments = fallback.get("target_segments") if isinstance(fallback.get("target_segments"), list) else []
    llm_segments = report["target_segments"]
    llm_by_name = {
        str(item.get("name")): item
        for item in llm_segments
        if isinstance(item, dict) and item.get("name")
    }
    if configured_segments:
        report["target_segments"] = [
            {**segment, **llm_by_name.get(str(segment.get("name")), {}), "ratio": segment.get("ratio"), "crowd_profile": segment.get("crowd_profile")}
            for segment in configured_segments
        ]
    if not isinstance(report["competitor_insights"], list):
        report["competitor_insights"] = fallback["competitor_insights"]
    report["strategy_recommendations"] = (
        normalize_strategy_recommendations(report["strategy_recommendations"])
        or normalize_strategy_recommendations(fallback["strategy_recommendations"])
    )
    if not isinstance(report["selected_strategies"], list):
        report["selected_strategies"] = fallback.get("selected_strategies", [])
    if not isinstance(report["risk_warnings"], list):
        report["risk_warnings"] = fallback["risk_warnings"]
    if not isinstance(report["evidence_used"], list):
        report["evidence_used"] = fallback["evidence_used"]
    report["generated_at"] = utc_now_iso()
    report["llm_provider"] = settings.llm_provider
    report["llm_model"] = settings.llm_model
    report["is_fallback"] = False
    report["crowd_segments"] = fallback.get("crowd_segments") or []
    if not isinstance(report.get("scenes"), list):
        report["scenes"] = fallback.get("scenes") or []
    if not isinstance(report.get("scene_details"), dict):
        report["scene_details"] = fallback.get("scene_details") or {}
    if not isinstance(report.get("scene_detail"), dict):
        report["scene_detail"] = fallback.get("scene_detail") or {}
    if not isinstance(report.get("strategy_details"), dict):
        report["strategy_details"] = fallback.get("strategy_details") or {}
    report["prompt_trace"] = {
        "report_builder": {
            "prompt_version": PROMPT_VERSION,
            "is_fallback": False,
            "model": settings.llm_model,
            "base_host": base_host(settings.llm_api_base),
        }
    }
    return report


def evidence_summary(evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, items in evidence.items():
        for item in items[:5]:
            rows.append(
                {
                    "group": group,
                    "source": item.get("source"),
                    "source_type": item.get("source_type"),
                    "source_category": item.get("source_category") or (
                        "公开资料补充" if str(item.get("source") or "").startswith("public_evidence") else ""
                    ),
                    "score": item.get("score"),
                    "snippet": item.get("snippet"),
                    "profile_tags": classify_user_profile_text(str(item.get("snippet") or ""))
                    if item.get("source_type") == "user_profile"
                    else [],
                    "price_missing": item.get("raw", {}).get("price_missing")
                    if isinstance(item.get("raw"), dict)
                    else False,
                }
            )
    return rows[:18]


def build_fallback_report(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    error: str | None = None,
) -> dict[str, Any]:
    product = snapshot.get("product_definition") or {}
    market = snapshot.get("market_config") or {}
    crowd_profile = normalize_crowd_profile(market)
    crowd_segments = normalize_crowd_segments(market)
    profile_text = crowd_profile_text(market)
    product_name = product.get("product_name") or product.get("name") or snapshot.get("project_name") or "当前产品"
    category = product.get("subcategory") or product.get("category") or "目标品类"
    price = product.get("price_cny") or product.get("price") or "待确认"
    product_evidence = evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS)
    crowd_evidence = evidence_items(evidence, *USER_EVIDENCE_KEYS, *MARKET_EVIDENCE_KEYS)
    price_coverage = product_price_coverage(evidence)
    strategy_items = market.get("strategies") if isinstance(market.get("strategies"), list) else []
    strategy_details = market.get("strategy_details") if isinstance(market.get("strategy_details"), dict) else {}
    raw_scenes = market.get("scenes") if isinstance(market.get("scenes"), list) else []
    scenes = [str(item).strip() for item in raw_scenes if str(item or "").strip()]
    if not scenes and str(market.get("scene") or "").strip():
        scenes = [str(market.get("scene")).strip()]
    scene_details = market.get("scene_details") if isinstance(market.get("scene_details"), dict) else {}
    scene_detail = market.get("scene_detail") if isinstance(market.get("scene_detail"), dict) else {}
    if scene_detail and scenes and scenes[0] not in scene_details:
        scene_details = {**scene_details, scenes[0]: scene_detail}
    selected_strategies = []
    for item in strategy_items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("strategy") or "").strip()
            if name:
                detail = strategy_details.get(name) if isinstance(strategy_details.get(name), dict) else {}
                selected_strategies.append({**detail, **item, "name": name})
        elif str(item or "").strip():
            name = str(item).strip()
            detail = strategy_details.get(name) if isinstance(strategy_details.get(name), dict) else {}
            selected_strategies.append({**detail, "name": name})
    if not selected_strategies and str(market.get("strategy") or "").strip():
        name = str(market.get("strategy")).strip()
        detail = strategy_details.get(name) if isinstance(strategy_details.get(name), dict) else {}
        selected_strategies.append({**detail, "name": name})

    report = {
        "executive_summary": (
            f"{product_name} 已完成基于结构化竞品和用户画像的初步仿真。"
            f"当前品类为{category}，参考价格为{price}。"
            "报告优先使用可追溯 evidence，LLM 不可用时保留规则化结论。"
        ),
        "target_segments": [
            {
                "name": segment.get("name") or "核心目标用户",
                "ratio": segment.get("ratio") or 100,
                "insight": (
                    f"结构化画像：{crowd_profile_text({'crowd_segments': [segment]})}。"
                    if segment.get("profile")
                    else crowd_evidence[0]["snippet"] if crowd_evidence else "需要继续补充用户画像 evidence。"
                ),
                "crowd_profile": segment.get("profile") or {},
            }
            for segment in crowd_segments
        ]
        or [
            {
                "name": market.get("target_crowd") or "核心目标用户",
                "ratio": 100,
                "insight": (
                    f"结构化画像：{profile_text}。"
                    if profile_text
                    else crowd_evidence[0]["snippet"] if crowd_evidence else "需要继续补充用户画像 evidence。"
                ),
                "crowd_profile": crowd_profile,
            }
        ],
        "crowd_segments": crowd_segments,
        "crowd_profile": crowd_profile,
        "selected_strategies": selected_strategies,
        "strategy_details": strategy_details,
        "scenes": scenes,
        "scene_details": scene_details,
        "scene_detail": scene_detail,
        "competitor_insights": [
            {
                "source": item.get("source"),
                "insight": item.get("snippet"),
                "score": item.get("score"),
            }
            for item in product_evidence[:5]
        ],
        "pricing_analysis": {
            "reference_price": price,
            "competitor_price_coverage": price_coverage,
            "summary": "结构化产品证据已用于识别相近品类、品牌、规格和价格带；后续可加入销量或渠道数据增强判断。",
        },
        "strategy_recommendations": [
            {
                "strategy": item.get("name") or "基础转化策略",
                "actions": [
                    safe_text(safe_action)
                    for safe_action in [
                        item.get("execution_actions") or item.get("action") or f"围绕「{item.get('name') or '当前策略'}」组织核心卖点表达",
                        item.get("channels") or item.get("touch_channels") or "结合目标客群选择触达渠道",
                    ]
                    if safe_text(safe_action)
                ][:3],
                "expected_impact": item.get("expected_impact") or "基于已填写配置与仿真结果生成，公开资料覆盖有限时建议人工复核。",
            }
            for item in selected_strategies[:5]
        ]
        or [
            {
                "strategy": "基础卖点转化策略",
                "actions": ["围绕用户高频关注点组织卖点表达，避免只堆参数。", "对比同品类竞品的核心规格和价格带，形成清晰差异化。"],
                "expected_impact": "在策略配置较少时提供基础转化参考。",
            },
            {
                "strategy": "证据复核策略",
                "actions": ["报告生成后复核价格缺失或规格不完整的竞品。"],
                "expected_impact": "减少价格带和竞品结论偏差。",
            },
        ],
        "risk_warnings": [
            "当前 FAISS 语料主要是用户画像，竞品结论依赖 MySQL 产品表。",
            f"本次竞品价格覆盖率为 {price_coverage['price_coverage_pct']}%，价格带判断可能偏粗。",
        ],
        "evidence_used": evidence_summary(evidence),
        "generated_at": utc_now_iso(),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "is_fallback": True,
        "prompt_trace": {
            "report_builder": {
                "prompt_version": PROMPT_VERSION,
                "is_fallback": True,
                "model": settings.llm_model,
                "base_host": base_host(settings.llm_api_base),
            }
        },
    }
    if error:
        report["fallback_reason"] = error
        report["llm_error"] = error
        report["prompt_trace"]["report_builder"]["error"] = error
    report["strategy_recommendations"] = normalize_strategy_recommendations(report["strategy_recommendations"])
    if snapshot.get("commercial_model_version") == COMMERCIAL_MODEL_VERSION:
        report["strategy_recommendations"] = enrich_strategy_recommendations(report["strategy_recommendations"], snapshot)
    report["quality_warnings"] = validate_report(report, evidence)
    return report


def build_evidence_context(evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    split = split_evidence(evidence)
    return {
        "summary": evidence_summary(evidence),
        "counts": {key: len(value) for key, value in split.items()},
        "structured_product_evidence": split["structured_product_evidence"][:8],
        "user_profile_evidence": [
            {
                "source": item.get("source"),
                "score": item.get("score"),
                "snippet": item.get("snippet"),
                "profile_tags": item.get("profile_tags"),
            }
            for item in split["user_profile_evidence"][:8]
        ],
        "market_strategy_evidence": split["market_strategy_evidence"][:5],
    }


def build_report_prompt(snapshot: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    system = (
        "你是产品市场仿真平台的分析报告生成器。"
        "你必须只输出 JSON，不要输出 Markdown。"
        "所有结论必须能从输入的产品配置和 evidence 中得到支持；不要编造销量、份额或不存在的数据。"
    )
    user = {
        "task": "生成产品市场仿真报告",
        "required_schema": list(REPORT_KEYS),
        "snapshot": snapshot,
        "evidence_context": build_evidence_context(evidence),
        "instructions": [
            "executive_summary 用 2-4 句中文概括机会、竞品、价格和主要风险。",
            "target_segments、competitor_insights、strategy_recommendations、risk_warnings 必须是数组。",
            "strategy_recommendations 的每一项必须是对象，至少包含 strategy、actions、expected_impact；actions 必须是字符串数组。",
            "策略建议优先依据专家策略先验、目标人群和场景匹配，不得无依据均分策略、渠道或参数分数。",
            "不得为了制造差异编造梯度；如果多个结果高度接近，应解释其输入或证据成因。",
            "买一送一、买二送一、大额满减、免单等高让利策略默认低优先级，只有场景、人群和渠道高度吻合时才作为条件建议。",
            "每组策略整体兼顾预期效果和执行风险，但不要为每条建议重复成本免责声明。",
            "不得将仿真 ROI 描述为真实财务收益、财务 ROI 或收益承诺。",
            "策略建议可增加 applicable_conditions、recommendation_priority、expert_basis、commercial_feasibility 字段。",
            "pricing_analysis 必须是对象，包含 summary 和 reference_price。",
            "如果 snapshot.market_config.strategy_details、scenes、scene_details 或 scene_detail 存在，策略和场景解释必须优先使用这些字段。",
            "如果用户已填写营销策略，但公开资料证据有限，也必须输出基于配置与仿真结果的模拟分析；可标注“公开资料覆盖有限”，不要输出空策略或缺配置警告。",
            "如果 evidence_context 中包含 source_category=公开资料补充 的证据，优先用于竞品补价、场景痛点和策略解释，但需保留风险提示。",
            "evidence_used 必须列出被使用的 source、source_type、snippet。",
            "如果竞品价格缺失，pricing_analysis 或 risk_warnings 必须明确说明价格数据不完整。",
            "不要编造销量、市场份额、排名、真实用户数量等输入中不存在的数据。",
        ],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": compact_json(user)},
    ]


def call_llm_report(snapshot: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    client = create_openai_client(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base or None,
        timeout=settings.llm_timeout_seconds,
    )
    messages = build_report_prompt(snapshot, evidence)
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.2,
    }
    try:
        response = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    data = extract_json_object(content)
    if data is None:
        raise ValueError("LLM 未返回可解析的 JSON 报告")
    data["_prompt_trace"] = {
        "prompt_version": PROMPT_VERSION,
        "model": settings.llm_model,
        "base_host": base_host(settings.llm_api_base),
        "request_chars": sum(len(message["content"]) for message in messages),
        "response_chars": len(content),
        "raw_response_truncated": content[:3000],
        "created_at": utc_now_iso(),
    }
    return data


def generate_simulation_report(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    fallback = build_fallback_report(snapshot, evidence)
    if not settings.llm_api_key:
        return build_fallback_report(snapshot, evidence, error="LLM_API_KEY 未配置")
    try:
        data = call_llm_report(snapshot, evidence)
        prompt_trace = data.pop("_prompt_trace", {})
        report = normalize_report(data, fallback)
        if snapshot.get("commercial_model_version") == COMMERCIAL_MODEL_VERSION:
            report["strategy_recommendations"] = enrich_strategy_recommendations(report["strategy_recommendations"], snapshot)
        report["prompt_trace"]["report_builder"].update(prompt_trace)
        quality_warnings = validate_report(report, evidence)
        if quality_warnings:
            report["quality_warnings"] = quality_warnings
            if has_missing_product_prices(evidence):
                risk_warnings = report.setdefault("risk_warnings", [])
                if isinstance(risk_warnings, list):
                    risk_warnings.append("部分竞品价格缺失，价格分析需要结合后续价格数据复核。")
        else:
            report["quality_warnings"] = []
        return report
    except Exception as exc:
        return build_fallback_report(snapshot, evidence, error=str(exc))
