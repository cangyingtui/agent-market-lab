from __future__ import annotations

import random
from typing import Any


PROMPT_VERSION = "social_network_v0.1"

DEFAULT_SOCIAL_NETWORK = {
    "enabled": True,
    "topology": "connected_watts_strogatz",
    "k": 4,
    "rewire_probability": 0.3,
    "max_rounds": 3,
    "convergence_threshold": 0.02,
    "trust_sensitivity_min": 0.5,
    "trust_sensitivity_max": 1.0,
    "representative_ratio": 0.03,
    "representative_min": 60,
    "representative_max": 300,
}

PERSONALITY_NOTES = (
    "做决定前会先比较几项关键参数。",
    "更愿意听取熟悉人群的实际使用反馈。",
    "倾向在价格与长期体验之间做平衡。",
    "对口碑变化较敏感，但不会只凭单一评价下单。",
)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def representative_agent_count(sample_size: Any, config: dict[str, Any] | None = None) -> int:
    social = {**DEFAULT_SOCIAL_NETWORK, **(config or {})}
    ratio = max(0.0, _as_float(social.get("representative_ratio"), 0.03))
    minimum = max(1, _as_int(social.get("representative_min"), 60))
    maximum = max(minimum, _as_int(social.get("representative_max"), 300))
    requested = max(1, _as_int(sample_size, 1000))
    return max(minimum, min(maximum, round(requested * ratio)))


def social_network_config(snapshot: dict[str, Any], *, node_count: int | None = None) -> dict[str, Any]:
    params = snapshot.get("simulation_params") if isinstance(snapshot.get("simulation_params"), dict) else {}
    configured = params.get("social_network") if isinstance(params.get("social_network"), dict) else {}
    social = {**DEFAULT_SOCIAL_NETWORK, **configured}
    sample_size = params.get("sample_size") or 1000
    social["enabled"] = bool(social.get("enabled", True))
    social["topology"] = "connected_watts_strogatz"
    social["k"] = max(2, _as_int(social.get("k"), 4))
    social["rewire_probability"] = _clamp(_as_float(social.get("rewire_probability"), 0.3), 0.0, 1.0)
    social["max_rounds"] = max(1, min(10, _as_int(social.get("max_rounds"), 3)))
    social["convergence_threshold"] = _clamp(_as_float(social.get("convergence_threshold"), 0.02), 0.0, 1.0)
    social["trust_sensitivity_min"] = _clamp(_as_float(social.get("trust_sensitivity_min"), 0.5), 0.0, 1.0)
    social["trust_sensitivity_max"] = _clamp(
        _as_float(social.get("trust_sensitivity_max"), 1.0),
        social["trust_sensitivity_min"],
        1.0,
    )
    social["representative_agent_count"] = node_count or representative_agent_count(sample_size, social)
    return social


def _stable_seed(snapshot: dict[str, Any]) -> int:
    params = snapshot.get("simulation_params") if isinstance(snapshot.get("simulation_params"), dict) else {}
    return _as_int(params.get("random_seed"), 42)


def _effective_k(node_count: int, requested_k: int) -> int:
    if node_count <= 2:
        return max(0, node_count - 1)
    maximum = node_count - 1
    if maximum % 2:
        maximum -= 1
    result = min(maximum, max(2, requested_k))
    if result % 2:
        result -= 1
    return max(2, result)


def _fallback_connected_watts_strogatz(node_count: int, k: int, probability: float, seed: int) -> list[tuple[int, int]]:
    if node_count <= 1:
        return []
    if node_count == 2:
        return [(0, 1)]
    rng = random.Random(seed)
    edges: set[tuple[int, int]] = set()
    half = max(1, k // 2)
    for source in range(node_count):
        for offset in range(1, half + 1):
            target = (source + offset) % node_count
            edge = tuple(sorted((source, target)))
            edges.add(edge)
    for source in range(node_count):
        for offset in range(1, half + 1):
            target = (source + offset) % node_count
            original = tuple(sorted((source, target)))
            if original not in edges or rng.random() >= probability:
                continue
            candidates = [
                candidate
                for candidate in range(node_count)
                if candidate != source and tuple(sorted((source, candidate))) not in edges
            ]
            if not candidates:
                continue
            edges.remove(original)
            edges.add(tuple(sorted((source, rng.choice(candidates)))))
    adjacency: dict[int, set[int]] = {index: set() for index in range(node_count)}
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    remaining = set(range(node_count))
    components: list[list[int]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: list[int] = []
        remaining.remove(start)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        components.append(component)
    for previous, current in zip(components, components[1:]):
        edges.add(tuple(sorted((previous[0], current[0]))))
    return sorted(edges)


def _network_edges(node_count: int, k: int, probability: float, seed: int) -> tuple[list[tuple[int, int]], str]:
    if node_count <= 2:
        return _fallback_connected_watts_strogatz(node_count, k, probability, seed), "builtin_compat"
    try:
        import networkx as nx

        graph = nx.connected_watts_strogatz_graph(node_count, k, probability, tries=100, seed=seed)
        return sorted(tuple(sorted((int(left), int(right)))) for left, right in graph.edges()), "networkx"
    except ImportError:
        return _fallback_connected_watts_strogatz(node_count, k, probability, seed), "builtin_compat"


def _persona(agent: dict[str, Any], trust_sensitivity: float, note: str) -> str:
    features = "、".join(str(item) for item in (agent.get("preferred_features") or [])[:3]) or "价格、功能和可靠性"
    influence = "较容易受到朋友评价影响" if trust_sensitivity >= 0.78 else "会参考朋友评价" if trust_sensitivity >= 0.62 else "更倾向独立判断"
    return (
        f"你属于{agent.get('segment') or '目标用户'}，生活阶段为{agent.get('life_stage') or '未特别说明'}，"
        f"所在城市层级为{agent.get('city_tier') or '未特别说明'}。你关注{features}，"
        f"对价格的敏感度为{agent.get('price_sensitivity') or 'medium'}。你{influence}。{note}"
    )


def attach_social_network(snapshot: dict[str, Any], agents: list[dict[str, Any]]) -> dict[str, Any]:
    social = social_network_config(snapshot, node_count=len(agents))
    node_count = len(agents)
    requested_k = _as_int(social.get("k"), 4)
    k = _effective_k(node_count, requested_k)
    seed = _stable_seed(snapshot)
    edges, implementation = _network_edges(node_count, k, float(social["rewire_probability"]), seed)
    neighbor_indexes: dict[int, list[int]] = {index: [] for index in range(node_count)}
    for left, right in edges:
        neighbor_indexes[left].append(right)
        neighbor_indexes[right].append(left)

    rng = random.Random(seed + 17)
    trust_min = float(social["trust_sensitivity_min"])
    trust_max = float(social["trust_sensitivity_max"])
    for index, agent in enumerate(agents):
        trust = round(rng.uniform(trust_min, trust_max), 4)
        note = PERSONALITY_NOTES[index % len(PERSONALITY_NOTES)]
        agent["neighbors"] = [agents[item]["agent_id"] for item in sorted(neighbor_indexes[index])]
        agent["trust_sensitivity"] = trust
        agent["persona"] = _persona(agent, trust, note)

    average_degree = round(sum(len(agent["neighbors"]) for agent in agents) / node_count, 4) if node_count else 0.0
    return {
        "prompt_version": PROMPT_VERSION,
        "enabled": bool(social["enabled"]),
        "topology": social["topology"],
        "implementation": implementation,
        "seed": seed,
        "requested_k": requested_k,
        "effective_k": k,
        "rewire_probability": social["rewire_probability"],
        "node_count": node_count,
        "edge_count": len(edges),
        "average_degree": average_degree,
    }
