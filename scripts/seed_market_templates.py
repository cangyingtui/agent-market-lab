from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import MarketCrowdTemplate, MarketSceneTemplate, MarketStrategyTemplate  # noqa: E402


def load_json(name: str):
    return json.loads((PROJECT_ROOT / "data_seed" / name).read_text(encoding="utf-8"))


def main() -> int:
    created = {"crowd": 0, "strategy": 0, "scene": 0}
    with SessionLocal() as db:
        for index, item in enumerate(load_json("market_crowd_templates.json"), 1):
            exists = db.scalar(select(MarketCrowdTemplate).where(MarketCrowdTemplate.name == item["name"]))
            if exists:
                exists.description = item.get("description")
                exists.default_ratio = float(item.get("default_ratio") or 0)
                exists.tags = item.get("tags")
                exists.sort_order = index
                exists.is_active = True
                continue
            db.add(
                MarketCrowdTemplate(
                    name=item["name"],
                    description=item.get("description"),
                    default_ratio=float(item.get("default_ratio") or 0),
                    tags=item.get("tags"),
                    sort_order=index,
                    is_active=True,
                )
            )
            created["crowd"] += 1

        for index, item in enumerate(load_json("market_strategy_templates.json"), 1):
            exists = db.scalar(select(MarketStrategyTemplate).where(MarketStrategyTemplate.name == item["name"]))
            if exists:
                exists.description = item.get("description")
                exists.default_params = item.get("default_params")
                exists.sort_order = index
                exists.is_active = True
                continue
            db.add(
                MarketStrategyTemplate(
                    name=item["name"],
                    description=item.get("description"),
                    default_params=item.get("default_params"),
                    sort_order=index,
                    is_active=True,
                )
            )
            created["strategy"] += 1

        for index, item in enumerate(load_json("market_scene_templates.json"), 1):
            exists = db.scalar(select(MarketSceneTemplate).where(MarketSceneTemplate.name == item["name"]))
            if exists:
                exists.description = item.get("description")
                exists.default_weight = float(item.get("default_weight") or 1.0)
                exists.sort_order = index
                exists.is_active = True
                continue
            db.add(
                MarketSceneTemplate(
                    name=item["name"],
                    description=item.get("description"),
                    default_weight=float(item.get("default_weight") or 1.0),
                    sort_order=index,
                    is_active=True,
                )
            )
            created["scene"] += 1

        db.commit()

    print(f"Seeded market templates: {created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
