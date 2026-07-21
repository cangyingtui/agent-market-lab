from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import create_all_tables, engine  # noqa: E402


def main() -> int:
    create_all_tables()
    print(f"Database tables are ready: {engine.url.render_as_string(hide_password=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
