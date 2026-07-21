from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable

from engine.maut_model import clamp, compute_maut_scores, confidence_for_decision, safe_float, weighted_purchase_intent
from engine.social_network import social_network_config


PROMPT_VERSION = "social_simulation_v0.1"

CancelCallback = Callable[[], None]
RoundCallback = Callable[[int, int, dict[str, Any]], None]
ValidationCallback = Callable[[list[dict[str, Any]]], dict[str, Any]]


def _weight(agent: dict[str, Any], decision: dict[str, Any] | None = None) -> float:
    fallback = decision.get("sample_weight") if isinstance(decision, dict) else None
    return max(safe_float(agent.get("sample_weight"), safe_float(fallback, 1.0)), 0.0)


def _weighted_mean(rows: list[tuple[float, float]]) -> float:
    total = sum(weight for _, weight in rows)
    return sum(value * weight for value, weight in rows) / total if total else 0.0


def _decision_label(score: float) -> str:
    return "buy" if score >= 0.68 else "consider" if score >= 0.45 else "not_buy"


def _round_summary(
    round_number: int,
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    max_score_change: float,
) -> dict[str, Any]:
    agent_map = {str(agent.get("agent_id")): agent for agent in agents}
    overall_rows: list[tuple[float, float]] = []
    social_rows: list[tuple[float, float]] = []
    segment_rows: dict[str, list[tuple[float, float]]] = defaultdict(list)
    segment_counts: Counter[str] = Counter()
    distribution: Counter[str] = Counter()
    for decision in decisions:
        agent = agent_map.get(str(decision.get("agent_id")), {})
        weight = _weight(agent, decision)
        score = clamp(safe_float(decision.get("purchase_intent_score"), 0.0))
        social = clamp(safe_float((decision.get("maut_scores") or {}).get("social_influence"), 0.0))
        segment = str(agent.get("segment") or decision.get("segment") or "目标用户")
        overall_rows.append((score, weight))
        social_rows.append((social, weight))
        segment_rows[segment].append((score, weight))
        segment_counts[segment] += 1
        distribution[str(decision.get("decision") or _decision_label(score))] += 1
    total_weight = sum(weight for _, weight in overall_rows)
    return {
        "round": round_number,
        "overall_purchase_intent": round(_weighted_mean(overall_rows), 4),
        "social_influence_avg": round(_weighted_mean(social_rows), 4),
        "max_score_change": round(max_score_change, 4),
        "decision_distribution": dict(distribution),
        "segment_evolution": [
            {
                "name": segment,
                "value": round(_weighted_mean(rows) * 100, 1),
                "count": segment_counts[segment],
                "ratio": round(sum(weight for _, weight in rows) * 100 / total_weight, 1) if total_weight else 0.0,
            }
            for segment, rows in segment_rows.items()
        ],
    }


def _validation_summary(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(validation.get("enabled")),
        "status": validation.get("status"),
        "validation_batch_id": validation.get("validation_batch_id"),
        "checked_samples": validation.get("checked_samples", 0),
        "consistency_score": validation.get("consistency_score"),
        "warning_level": validation.get("warning_level"),
        "warning": validation.get("warning"),
    }


def _run_validation(
    callback: ValidationCallback | None,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    if callback is None:
        return {"enabled": False, "status": "not_configured", "checked_samples": 0}
    try:
        return callback(decisions)
    except Exception as exc:
        return {
            "enabled": True,
            "status": "failed",
            "checked_samples": 0,
            "warning_level": "warning",
            "warning": f"辅助模型复核暂不可用，主流程已继续：{exc}",
        }


def _round_one_decisions(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    initial_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    product = snapshot.get("product_definition") or {}
    agent_map = {str(agent.get("agent_id")): agent for agent in agents}
    decision_map = {str(decision.get("agent_id")): decision for decision in initial_decisions if isinstance(decision, dict)}
    rows: list[dict[str, Any]] = []
    for agent_id, agent in agent_map.items():
        copied = dict(decision_map.get(agent_id) or {"agent_id": agent_id})
        maut_scores = compute_maut_scores(snapshot, evidence, agent)
        score = weighted_purchase_intent(maut_scores)
        copied.update(
            {
                "agent_id": agent_id,
                "segment": agent.get("segment"),
                "segment_ratio": agent.get("segment_ratio"),
                "sample_weight": _weight(agent, copied),
                "maut_scores": maut_scores,
                "maut_weighted_score": score,
                "purchase_intent_score": score,
                "decision": _decision_label(score),
                "simulation_round": 1,
            }
        )
        copied["confidence"] = confidence_for_decision(copied, product)
        rows.append(copied)
    return rows


def _propagate_round(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    previous_decisions: list[dict[str, Any]],
    round_number: int,
) -> tuple[list[dict[str, Any]], float]:
    product = snapshot.get("product_definition") or {}
    previous_map = {str(item.get("agent_id")): item for item in previous_decisions if isinstance(item, dict)}
    rows: list[dict[str, Any]] = []
    max_change = 0.0
    for agent in agents:
        agent_id = str(agent.get("agent_id"))
        copied = dict(previous_map.get(agent_id) or {"agent_id": agent_id})
        neighbor_scores = [
            clamp(safe_float(previous_map.get(str(neighbor), {}).get("purchase_intent_score"), 0.5))
            for neighbor in agent.get("neighbors") or []
        ]
        neighbor_avg = sum(neighbor_scores) / len(neighbor_scores) if neighbor_scores else 0.5
        trust = clamp(safe_float(agent.get("trust_sensitivity"), 0.5))
        social_score = clamp(0.5 + trust * (neighbor_avg - 0.5))
        maut_scores = compute_maut_scores(snapshot, evidence, agent, social_influence=social_score)
        score = weighted_purchase_intent(maut_scores)
        previous_score = clamp(safe_float(copied.get("purchase_intent_score"), score))
        change = abs(score - previous_score)
        max_change = max(max_change, change)
        copied.update(
            {
                "agent_id": agent_id,
                "segment": agent.get("segment"),
                "segment_ratio": agent.get("segment_ratio"),
                "sample_weight": _weight(agent, copied),
                "maut_scores": maut_scores,
                "maut_weighted_score": score,
                "purchase_intent_score": score,
                "decision": _decision_label(score),
                "simulation_round": round_number,
                "neighbor_purchase_intent_avg": round(neighbor_avg, 4),
                "social_score_change": round(change, 4),
            }
        )
        copied["confidence"] = confidence_for_decision(copied, product)
        rows.append(copied)
    return rows, max_change


def run_social_simulation(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    initial_decisions: list[dict[str, Any]],
    *,
    network_metadata: dict[str, Any] | None = None,
    check_cancel: CancelCallback | None = None,
    on_round: RoundCallback | None = None,
    validate_round: ValidationCallback | None = None,
) -> dict[str, Any]:
    social = social_network_config(snapshot, node_count=len(agents))
    max_rounds = max(1, int(social["max_rounds"])) if social.get("enabled", True) else 1
    threshold = float(social["convergence_threshold"])
    summaries: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    decisions = _round_one_decisions(snapshot, evidence, agents, initial_decisions)
    converged = False
    final_validation: dict[str, Any] = {}

    for round_number in range(1, max_rounds + 1):
        if check_cancel:
            check_cancel()
        max_change = 0.0
        if round_number > 1:
            decisions, max_change = _propagate_round(snapshot, evidence, agents, decisions, round_number)
        summary = _round_summary(round_number, agents, decisions, max_change)
        final_validation = _run_validation(validate_round, decisions)
        summary["validation"] = _validation_summary(final_validation)
        summaries.append(summary)
        validations.append({"round": round_number, **_validation_summary(final_validation)})
        if on_round:
            on_round(round_number, max_rounds, summary)
        if round_number > 1 and max_change < threshold:
            converged = True
            break

    metadata = network_metadata or {}
    return {
        "prompt_version": PROMPT_VERSION,
        "config": {
            "topology": social["topology"],
            "k": social["k"],
            "rewire_probability": social["rewire_probability"],
            "max_rounds": max_rounds,
            "convergence_threshold": threshold,
            "representative_agent_count": len(agents),
        },
        "topology": metadata.get("topology") or social["topology"],
        "implementation": metadata.get("implementation"),
        "rounds_executed": len(summaries),
        "converged": converged,
        "node_count": metadata.get("node_count", len(agents)),
        "edge_count": metadata.get("edge_count", 0),
        "average_degree": metadata.get("average_degree", 0.0),
        "round_summaries": summaries,
        "round_validations": validations,
        "final_validation": final_validation,
        "final_decisions": decisions,
    }
