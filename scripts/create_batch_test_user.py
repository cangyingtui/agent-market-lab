from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import UpgradeLog, User  # noqa: E402
from app.security import hash_password  # noqa: E402


DEFAULT_USERNAME = "123@test"
ACCOUNT_MARKER = "AgentSim公开演示测试账号"
AUDIT_REASON = "batch_test_account_bootstrap"


def required_password() -> str:
    password = os.getenv("BATCH_TEST_PASSWORD", "")
    if len(password) < 6:
        raise RuntimeError("BATCH_TEST_PASSWORD 必须通过环境变量提供，且至少 6 个字符")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="幂等创建 AgentSim 专用 Pro 批量测试账号")
    parser.add_argument("--rotate-password", action="store_true", help="显式轮换已有测试账号密码")
    args = parser.parse_args()

    username = os.getenv("BATCH_TEST_USERNAME", DEFAULT_USERNAME).strip()
    if username != DEFAULT_USERNAME:
        raise RuntimeError(f"测试账号用户名必须固定为 {DEFAULT_USERNAME}")
    password = required_password()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        created = user is None
        old_plan: str | None = None

        if user is None:
            user = User(
                username=username,
                email=None,
                password_hash=hash_password(password),
                full_name=ACCOUNT_MARKER,
                plan_type="pro",
                basic_quota_remaining=0,
            )
            db.add(user)
            db.flush()
            db.add(
                UpgradeLog(
                    user_id=user.id,
                    from_plan=None,
                    to_plan="pro",
                    reason=AUDIT_REASON,
                )
            )
        else:
            if user.full_name not in {None, "", ACCOUNT_MARKER}:
                raise RuntimeError("同名账号已存在，但不是专用批量测试账号；拒绝接管")
            user.full_name = ACCOUNT_MARKER
            old_plan = user.plan_type
            if user.plan_type != "pro":
                user.plan_type = "pro"
                db.add(
                    UpgradeLog(
                        user_id=user.id,
                        from_plan=old_plan,
                        to_plan="pro",
                        reason=AUDIT_REASON,
                    )
                )
            if args.rotate_password:
                user.password_hash = hash_password(password)

        db.commit()
        db.refresh(user)
        payload = {
            "username": user.username,
            "user_id": user.id,
            "plan_type": user.plan_type,
            "status": "created" if created else "existing",
            "password_rotated": bool(args.rotate_password and not created),
        }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
