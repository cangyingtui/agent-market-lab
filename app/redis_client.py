from __future__ import annotations

from functools import lru_cache
from typing import Any

import redis

from app.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def redis_json_get(key: str) -> dict[str, Any] | None:
    import json

    value = get_redis_client().get(key)
    if not value:
        return None
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def redis_json_set(key: str, value: dict[str, Any], ex: int | None = None) -> None:
    import json

    get_redis_client().set(key, json.dumps(value, ensure_ascii=False), ex=ex)
