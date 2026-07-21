from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_model.faiss_rag import EmbeddingConfigError  # noqa: E402
from knowledge_model.rag_service import get_rag_service  # noqa: E402


QUERIES = [
    "高端智能手机 电池 价格",
    "电动牙刷 续航 防水",
    "户外帐篷 防水 重量",
    "护理床 电机 护栏",
]


def main() -> int:
    try:
        service = get_rag_service(force_reload=True)
    except ImportError as exc:
        print(f"Package check failed: {exc}")
        print("Install dependencies with: python -m pip install -r requirements.txt")
        return 1
    status = service.status()
    print(json.dumps(status, ensure_ascii=False, indent=2))

    if not status["metadata_matches_index"]:
        print("FAISS check failed: metadata length does not match index.ntotal")
        return 1

    if status["embedding_configured"] and status["index_dim"] != status["embedding_dim"]:
        print(
            "FAISS 维度与当前 embedding 配置不一致："
            f"index_dim={status['index_dim']}, embedding_dim={status['embedding_dim']}。"
            "请先运行 scripts/build_faiss_index.py 全量重建索引。"
        )
        return 1

    if not status["embedding_configured"]:
        print(
            "Embedding config is not complete, so ANN search was not called. "
            "Set EMBEDDING_API_KEY and EMBEDDING_MODEL in .env to run query retrieval."
        )
        return 0

    for query in QUERIES:
        print(f"\nQUERY: {query}")
        try:
            results = service.search(query, top_k=5)
        except EmbeddingConfigError as exc:
            print(f"Embedding config error: {exc}")
            return 1
        except Exception as exc:
            print(f"Embedding API call failed: {exc}")
            print(
                "请确认 EMBEDDING_API_BASE 指向的是支持 /embeddings 的服务，"
                "并且 EMBEDDING_MODEL 是该服务真实支持的向量模型。"
            )
            return 1
        for item in results:
            print(
                json.dumps(
                    {
                        "type": item["type"],
                        "score": item["score"],
                        "source": item["source"],
                        "matched_fields": item["matched_fields"],
                        "snippet": item["snippet"],
                    },
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
