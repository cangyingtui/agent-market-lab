from __future__ import annotations

import argparse
import os
import pickle
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild the FAISS index from faiss_metadata.pkl using the configured embedding API."
    )
    parser.add_argument("--metadata-path", default=settings.faiss_metadata_path)
    parser.add_argument("--index-path", default=settings.faiss_index_path)
    parser.add_argument("--output-index-path", default="", help="Optional output path for a test index.")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--cache-dir", default="knowledge_model/knowledge_base/faiss_vector_cache")
    parser.add_argument("--reset-cache", action="store_true", help="Delete existing vector shard cache before running.")
    parser.add_argument("--limit", type=int, default=0, help="Optional smoke-test limit; 0 means all metadata.")
    parser.add_argument("--no-backup", action="store_true", help="Do not backup an existing index before replacing it.")
    parser.add_argument(
        "--write-limited-index",
        action="store_true",
        help="Allow writing/replacing an index when --limit is used. By default limited runs only validate.",
    )
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_metadata(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")
    with path.open("rb") as file:
        data = pickle.load(file)
    if not isinstance(data, list):
        raise ValueError("Metadata must be a list.")

    items = [
        item
        for item in data
        if isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and isinstance(item.get("source"), str)
    ]
    return items[:limit] if limit > 0 else items


def embedding_client() -> OpenAI:
    if not settings.embedding_api_key:
        raise RuntimeError("EMBEDDING_API_KEY is required before rebuilding FAISS.")
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL is required before rebuilding FAISS.")
    return OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_api_base or None,
        timeout=settings.embedding_timeout_seconds,
    )


def embed_batch(client: OpenAI, texts: list[str]) -> np.ndarray:
    if len(texts) > 10 and "dashscope.aliyuncs.com" in settings.embedding_api_base:
        raise RuntimeError("百炼 text-embedding-v3 单批最多 10 条，请把 --batch-size 设为 10 或更小。")

    kwargs: dict[str, Any] = {
        "model": settings.embedding_model,
        "input": texts,
    }
    if settings.embedding_use_dimensions_param:
        kwargs["dimensions"] = settings.embedding_dim

    try:
        response = client.embeddings.create(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            "Embedding API 调用失败。请确认 EMBEDDING_API_BASE 支持 /embeddings，"
            "EMBEDDING_MODEL 是真实可用的向量模型，并且 EMBEDDING_API_KEY 有权限调用。"
        ) from exc
    vectors = np.asarray([item.embedding for item in response.data], dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = np.divide(vectors, np.maximum(norms, 1e-12))
    return vectors.astype("float32")


def embed_batch_with_retry(texts: list[str], retries: int) -> np.ndarray:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return embed_batch(embedding_client(), texts)
        except Exception as exc:
            last_error = exc
            wait_seconds = min(2 ** attempt, 30)
            print(f"批次调用失败，准备重试：attempt={attempt}/{retries}, wait={wait_seconds}s, error={exc}", flush=True)
            time.sleep(wait_seconds)
    raise RuntimeError(f"Embedding 批次重试后仍失败：{last_error}")


def build_index(vectors: np.ndarray):
    import faiss

    if vectors.ndim != 2 or vectors.shape[0] == 0:
        raise ValueError("No vectors were generated.")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return index


def backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def shard_path(cache_dir: Path, start: int, end: int) -> Path:
    return cache_dir / f"vectors_{start:06d}_{end:06d}.npy"


def save_shard(path: Path, vectors: np.ndarray) -> None:
    temp_path = path.with_suffix(".npy.tmp")
    with temp_path.open("wb") as file:
        np.save(file, vectors)
    os.replace(temp_path, path)


def load_shards(cache_dir: Path, total: int, batch_size: int) -> np.ndarray:
    shards: list[np.ndarray] = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        path = shard_path(cache_dir, start, end)
        if not path.exists():
            raise FileNotFoundError(f"缺少向量缓存分片：{path}")
        vectors = np.load(path)
        if vectors.shape[0] != end - start:
            raise RuntimeError(f"向量缓存分片行数不匹配：{path}")
        shards.append(vectors.astype("float32"))
    return np.vstack(shards)


def build_vector_cache(
    items: list[dict[str, Any]],
    cache_dir: Path,
    batch_size: int,
    max_workers: int,
    retries: int,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    total = len(items)
    jobs: list[tuple[int, int, list[str], Path]] = []
    completed = 0
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        path = shard_path(cache_dir, start, end)
        if path.exists():
            completed += end - start
            continue
        texts = [item["text"] for item in items[start:end]]
        jobs.append((start, end, texts, path))

    print(f"向量缓存状态：已完成 {completed} / {total}，待处理批次 {len(jobs)}", flush=True)
    if not jobs:
        return

    workers = max(1, max_workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(embed_batch_with_retry, texts, retries): (start, end, path)
            for start, end, texts, path in jobs
        }
        for future in as_completed(future_map):
            start, end, path = future_map[future]
            vectors = future.result()
            if settings.embedding_dim and vectors.shape[1] != settings.embedding_dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch: got {vectors.shape[1]}, expected {settings.embedding_dim}."
                )
            save_shard(path, vectors)
            completed += end - start
            print(f"Embedded {completed} / {total}", flush=True)


def main() -> int:
    args = parse_args()
    metadata_path = resolve_path(args.metadata_path)
    index_path = resolve_path(args.index_path)
    output_index_path = resolve_path(args.output_index_path) if args.output_index_path else None
    cache_dir = resolve_path(args.cache_dir)

    items = load_metadata(metadata_path, limit=args.limit)
    if not items:
        raise RuntimeError("No valid metadata items found.")

    total = len(items)
    if args.limit > 0 and output_index_path is None and not args.write_limited_index:
        vectors = embed_batch_with_retry([item["text"] for item in items], args.retries)
        index = build_index(vectors)
        print(
            "Smoke test completed without writing an index: "
            f"items={len(items)}, ntotal={index.ntotal}, dim={index.d}. "
            "Run without --limit for full rebuild, or pass --output-index-path for a test file."
        )
        return 0

    if args.reset_cache and cache_dir.exists():
        shutil.rmtree(cache_dir)
    build_vector_cache(
        items=items,
        cache_dir=cache_dir,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        retries=args.retries,
    )
    matrix = load_shards(cache_dir, total=total, batch_size=args.batch_size)
    if settings.embedding_dim and matrix.shape[1] != settings.embedding_dim:
        raise RuntimeError(
            f"Embedding dimension mismatch: got {matrix.shape[1]}, expected {settings.embedding_dim}. "
            "Update EMBEDDING_DIM or use the embedding model selected for this FAISS corpus."
        )

    index = build_index(matrix)

    target_path = output_index_path or index_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f"{target_path.name}.building")

    import faiss

    faiss.write_index(index, str(temp_path))
    should_backup = target_path == index_path and not args.no_backup
    backup_path = backup_existing(index_path) if should_backup else None
    os.replace(temp_path, target_path)

    print(f"FAISS index rebuilt: path={target_path}, ntotal={index.ntotal}, dim={index.d}")
    if backup_path:
        print(f"Previous index backup: {backup_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAISS 重建失败：{exc}")
        raise SystemExit(1)
