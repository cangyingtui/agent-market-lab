from __future__ import annotations

import subprocess
import sys


COMMANDS = (
    ("scripts/init_db.py",),
    ("scripts/seed_categories.py",),
    ("scripts/seed_products.py",),
    ("scripts/seed_market_templates.py",),
    ("scripts/seed_feature_flags.py",),
    ("scripts/seed_demo_users.py",),
    ("scripts/migrate_product_prices_20260728.py", "--apply-db", "--verify"),
    ("scripts/check_data_ready.py",),
)


def main() -> int:
    for args in COMMANDS:
        command = [sys.executable, *args]
        print(f"[data-init] running: {' '.join(command)}", flush=True)
        subprocess.run(command, check=True)
    print("[data-init] production data is ready", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
