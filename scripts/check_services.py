from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402


def check_mysql() -> tuple[bool, str]:
    try:
        from sqlalchemy import text

        from app.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_redis() -> tuple[bool, str]:
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        pong = client.ping()
        return bool(pong), "ok" if pong else "ping failed"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    mysql_ok, mysql_msg = check_mysql()
    redis_ok, redis_msg = check_redis()
    result = {
        "mysql": {"ok": mysql_ok, "message": mysql_msg},
        "redis": {"ok": redis_ok, "message": redis_msg},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if mysql_ok and redis_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
