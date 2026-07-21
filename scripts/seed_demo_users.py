from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402


DEMO_USERS = [
    {
        "username": "pro@example",
        "email": "pro@example",
        "password": "123456",
        "full_name": "专业版测试账号",
        "plan_type": "pro",
        "basic_quota_remaining": 2,
    },
    {
        "username": "normal@example",
        "email": "normal@example",
        "password": "123456",
        "full_name": "普通版测试账号",
        "plan_type": "basic",
        "basic_quota_remaining": 999,
    },
]


def main() -> int:
    with SessionLocal() as db:
        for item in DEMO_USERS:
            user = db.scalar(select(User).where(User.username == item["username"]))
            if user is None:
                user = User(
                    username=item["username"],
                    email=item["email"],
                    password_hash=hash_password(item["password"]),
                )
                db.add(user)
            user.full_name = item["full_name"]
            user.plan_type = item["plan_type"]
            user.basic_quota_remaining = item["basic_quota_remaining"]
        db.commit()
    print("已创建/更新测试账号：pro@example / normal@example，密码均为 123456")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
