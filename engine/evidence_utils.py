from __future__ import annotations

from typing import Any


PRODUCT_EVIDENCE_KEYS = ("product_query", "competitor_query", "product_competition")
USER_EVIDENCE_KEYS = ("market_query", "crowd_preference")
MARKET_EVIDENCE_KEYS = ("market_query", "market_strategy")
RAG_QUERY_KEYS = ("product_query", "competitor_query", "market_query")


def evidence_items(evidence: dict[str, list[dict[str, Any]]], *keys: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for key in keys:
        if key in seen_groups:
            continue
        seen_groups.add(key)
        items = evidence.get(key)
        if isinstance(items, list):
            rows.extend(item for item in items if isinstance(item, dict))
    return rows


def evidence_fingerprint(item: dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    return "|".join(
        str(part or "")
        for part in (
            item.get("source_type"),
            item.get("source"),
            raw.get("id"),
            raw.get("product_name"),
            item.get("snippet"),
        )
    )


def dedupe_and_rank(items: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ranked = sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: float(item.get("score") or 0),
        reverse=True,
    )
    result: list[dict[str, Any]] = []
    for item in ranked:
        key = evidence_fingerprint(item)
        if key in seen:
            continue
        seen.add(key)
        copied = dict(item)
        copied["final_rank"] = len(result) + 1
        result.append(copied)
        if len(result) >= limit:
            break
    return result


def rag_contract_fields(
    evidence: dict[str, list[dict[str, Any]]],
    final_evidence: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    final = final_evidence or {
        key: dedupe_and_rank(evidence.get(key, []), limit=10)
        for key in RAG_QUERY_KEYS
        if isinstance(evidence.get(key), list)
    }
    all_final = [item for items in final.values() for item in items]
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in all_final:
        source = str(item.get("source") or "")
        if not source or source in seen:
            continue
        seen.add(source)
        sources.append(
            {
                "source": source,
                "source_type": item.get("source_type"),
                "score": item.get("score"),
                "evidence_group": item.get("evidence_group"),
            }
        )
    return {
        "rag_summary": {
            "query_groups": {
                key: {
                    "retrieved_count": len(evidence.get(key, [])),
                    "final_used_count": len(final.get(key, [])),
                }
                for key in RAG_QUERY_KEYS
            },
            "total_retrieved": sum(len(items) for items in evidence.values()),
            "total_final_used": len(all_final),
        },
        "evidence_sources": sources,
        "insight_evidence_map": {
            "executive_summary": [item.get("source") for item in all_final[:5] if item.get("source")],
            "competitor_insights": [
                item.get("source")
                for item in evidence_items(final, "competitor_query", "product_query")[:8]
                if item.get("source")
            ],
            "pricing_analysis": [
                item.get("source")
                for item in evidence_items(final, "competitor_query")[:8]
                if item.get("source")
            ],
            "target_segments": [
                item.get("source")
                for item in evidence_items(final, "market_query")[:8]
                if item.get("source")
            ],
        },
    }
