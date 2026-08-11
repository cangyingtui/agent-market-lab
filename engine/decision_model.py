from __future__ import annotations

import json
import statistics
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.openai_compat import create_openai_client
from app.time_utils import utc_now_iso
from engine.evidence_utils import PRODUCT_EVIDENCE_KEYS, evidence_items
from engine.maut_model import build_decision_model_summary, enrich_decisions_with_maut
from engine.report_generator import extract_json_object


PROMPT_VERSION = "decision_model_v0.1"


def base_host(url: str) -> str:
    parsed = urlparse(url or "")
    return parsed.netloc or parsed.path or ""


def feature_match_score(agent: dict[str, Any], product: dict[str, Any]) -> float:
    specs = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    text = " ".join([str(key) for key in specs.keys()] + [str(value) for value in specs.values()])
    score = 0.0
    for feature in agent.get("preferred_features") or []:
        if str(feature) and str(feature) in text:
            score += 0.08
    return min(score, 0.24)


def price_score(agent: dict[str, Any], product: dict[str, Any], competitor_items: list[dict[str, Any]]) -> float:
    price = product.get("price_cny")
    if not isinstance(price, (int, float)):
        return 0.48
    priced_competitors = [
        item.get("raw", {}).get("price_cny")
        for item in competitor_items
        if isinstance(item.get("raw"), dict) and isinstance(item.get("raw", {}).get("price_cny"), (int, float))
    ]
    competitor_avg = statistics.mean(priced_competitors) if priced_competitors else None
    sensitivity = agent.get("price_sensitivity")
    score = 0.58
    if competitor_avg:
        if price <= competitor_avg:
            score += 0.1
        else:
            score -= min((price - competitor_avg) / max(price, 1) * 0.5, 0.2)
    if sensitivity == "high" and price > 4000:
        score -= 0.12
    elif sensitivity == "low":
        score += 0.06
    return max(0.05, min(score, 0.9))


def fallback_decisions(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    error: str | None = None,
) -> dict[str, Any]:
    product = snapshot.get("product_definition") or {}
    competitor_items = evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS)
    decisions: list[dict[str, Any]] = []
    for agent in agents:
        score = price_score(agent, product, competitor_items) + feature_match_score(agent, product)
        score = max(0.05, min(score, 0.95))
        blockers = []
        if agent.get("price_sensitivity") == "high":
            blockers.append("价格敏感，需要更强价格理由或促销支撑")
        if not product.get("price_cny"):
            blockers.append("产品价格未确认")
        drivers = [f"关注{feature}" for feature in (agent.get("preferred_features") or [])[:2]]
        decisions.append(
            {
                "agent_id": agent["agent_id"],
                "purchase_intent_score": round(score, 4),
                "decision": "buy" if score >= 0.68 else "consider" if score >= 0.45 else "not_buy",
                "drivers": drivers or ["产品规格具备基础吸引力"],
                "blockers": blockers,
                "reason": "规则 fallback：综合价格敏感度、规格匹配和竞品证据给出购买意愿。",
                "evidence_refs": agent.get("evidence_refs") or [],
            }
        )
    decisions = enrich_decisions_with_maut(snapshot, evidence, agents, decisions)
    return {
        "prompt_version": PROMPT_VERSION,
        "decisions": decisions,
        "decision_model": build_decision_model_summary(decisions, snapshot),
        "is_fallback": True,
        "fallback_reason": error or "规则化购买决策",
    }


def build_decision_prompt(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "task": "为虚拟消费者 Agent 生成购买决策",
        "schema": {
            "decisions": [
                {
                    "agent_id": "agent_001",
                    "purchase_intent_score": "0-1",
                    "decision": "buy/consider/not_buy",
                    "drivers": ["购买驱动"],
                    "blockers": ["购买阻碍"],
                    "reason": "必须引用 evidence 的简短理由",
                    "evidence_refs": ["source id"],
                }
            ]
        },
        "snapshot": snapshot,
        "agents": agents,
        "evidence_summary": {
            key: [
                {
                    "source": item.get("source"),
                    "source_type": item.get("source_type"),
                    "snippet": item.get("snippet"),
                    "score": item.get("score"),
                }
                for item in items[:6]
            ]
            for key, items in evidence.items()
        },
    }
    return [
        {
            "role": "system",
            "content": "你是消费者购买决策模拟器，只输出 JSON，不要编造 evidence 中没有的数据。",
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)[:14000]},
    ]


def normalize_llm_decisions(data: dict[str, Any], agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = data.get("decisions")
    if not isinstance(raw, list):
        raise ValueError("LLM 决策缺少 decisions 数组")
    agent_ids = {agent["agent_id"] for agent in agents}
    decisions: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        agent_id = item.get("agent_id")
        if agent_id not in agent_ids:
            continue
        score = item.get("purchase_intent_score")
        if not isinstance(score, (int, float)):
            score = 0.5
        decisions.append(
            {
                "agent_id": agent_id,
                "purchase_intent_score": round(max(0.0, min(float(score), 1.0)), 4),
                "decision": item.get("decision") if item.get("decision") in {"buy", "consider", "not_buy"} else "consider",
                "drivers": item.get("drivers") if isinstance(item.get("drivers"), list) else [],
                "blockers": item.get("blockers") if isinstance(item.get("blockers"), list) else [],
                "reason": str(item.get("reason") or "")[:400],
                "evidence_refs": item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else [],
            }
        )
    if len(decisions) != len(agents):
        raise ValueError("LLM 决策数量与 Agent 数量不一致")
    return decisions


def select_reasoning_agents(agents: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(agents) <= limit:
        return agents
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    segments: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        segments.setdefault(str(agent.get("segment") or "目标用户"), []).append(agent)
    while len(selected) < limit:
        progressed = False
        for rows in segments.values():
            if not rows:
                continue
            agent = rows.pop(0)
            agent_id = str(agent.get("agent_id"))
            if agent_id in seen_ids:
                continue
            selected.append(agent)
            seen_ids.add(agent_id)
            progressed = True
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


def generate_purchase_decisions(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
) -> dict[str, Any]:
    base_result = fallback_decisions(snapshot, evidence, agents, "规则化购买决策基线")
    if not settings.llm_api_key:
        base_result["fallback_reason"] = "LLM_API_KEY 未配置"
        base_result["prompt_trace"] = {
            "prompt_version": PROMPT_VERSION,
            "is_fallback": True,
            "error": "LLM_API_KEY 未配置",
            "input_agent_count": len(agents),
            "sampled_agent_count": 0,
        }
        return base_result
    sampled_agents = select_reasoning_agents(agents, max(1, settings.social_llm_sample_size))
    messages = build_decision_prompt(snapshot, evidence, sampled_agents)
    try:
        client = create_openai_client(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base or None,
            timeout=settings.llm_timeout_seconds,
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.15,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        data = extract_json_object(content)
        if data is None:
            raise ValueError("LLM 未返回可解析 JSON")
        sampled_decisions = normalize_llm_decisions(data, sampled_agents)
        sampled_map = {str(item.get("agent_id")): item for item in sampled_decisions}
        decisions: list[dict[str, Any]] = []
        for decision in base_result["decisions"]:
            copied = dict(decision)
            enriched_reason = sampled_map.get(str(copied.get("agent_id")))
            if enriched_reason:
                copied.update(
                    {
                        "purchase_intent_score": enriched_reason.get("purchase_intent_score"),
                        "drivers": enriched_reason.get("drivers") or copied.get("drivers") or [],
                        "blockers": enriched_reason.get("blockers") or copied.get("blockers") or [],
                        "reason": enriched_reason.get("reason") or copied.get("reason"),
                        "evidence_refs": enriched_reason.get("evidence_refs") or copied.get("evidence_refs") or [],
                        "llm_reasoning_sampled": True,
                    }
                )
            else:
                copied["llm_reasoning_sampled"] = False
            decisions.append(copied)
        decisions = enrich_decisions_with_maut(snapshot, evidence, agents, decisions)
        return {
            "prompt_version": PROMPT_VERSION,
            "decisions": decisions,
            "decision_model": build_decision_model_summary(decisions, snapshot),
            "is_fallback": False,
            "prompt_trace": {
                "prompt_version": PROMPT_VERSION,
                "model": settings.llm_model,
                "base_host": base_host(settings.llm_api_base),
                "request_chars": sum(len(message["content"]) for message in messages),
                "response_chars": len(content),
                "raw_response_truncated": content[:3000],
                "created_at": utc_now_iso(),
                "input_agent_count": len(agents),
                "sampled_agent_count": len(sampled_agents),
            },
        }
    except Exception as exc:
        base_result["fallback_reason"] = str(exc)
        base_result["prompt_trace"] = {
            "prompt_version": PROMPT_VERSION,
            "model": settings.llm_model,
            "base_host": base_host(settings.llm_api_base),
            "request_chars": sum(len(message["content"]) for message in messages),
            "is_fallback": True,
            "error": str(exc),
            "created_at": utc_now_iso(),
            "input_agent_count": len(agents),
            "sampled_agent_count": len(sampled_agents),
        }
        return base_result
