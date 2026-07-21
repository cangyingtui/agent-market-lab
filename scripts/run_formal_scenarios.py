from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app  # noqa: E402
from app.time_utils import utc_now_naive  # noqa: E402
from engine import worker  # noqa: E402


SCENARIOS = [
    {
        "name": "高端智能手机",
        "product_definition": {
            "product_name": "高端智能手机",
            "brand": "测试品牌",
            "category": "消费电子",
            "subcategory": "智能手机",
            "price_cny": 4999,
            "specifications": {"电池": "5000mAh", "屏幕": "OLED 120Hz", "防水": "IP68"},
        },
        "market_config": {"target_crowd": "高端用户", "strategy": "差异化定价", "scene": "线上首发"},
    },
    {
        "name": "电动牙刷",
        "product_definition": {
            "product_name": "电动牙刷",
            "brand": "测试品牌",
            "category": "家用电器",
            "subcategory": "电动牙刷",
            "price_cny": 399,
            "specifications": {"续航": "30天", "防水": "IPX7", "模式": "清洁/美白/敏感"},
        },
        "market_config": {"target_crowd": "注重口腔护理的年轻用户", "strategy": "功能差异化", "scene": "电商促销"},
    },
    {
        "name": "户外帐篷",
        "product_definition": {
            "product_name": "户外帐篷",
            "brand": "测试品牌",
            "category": "运动户外",
            "subcategory": "帐篷",
            "price_cny": 899,
            "specifications": {"防水": "3000mm", "重量": "2.8kg", "便携": "双人快速搭建"},
        },
        "market_config": {"target_crowd": "周末露营用户", "strategy": "场景化营销", "scene": "户外渠道"},
    },
    {
        "name": "护理床",
        "product_definition": {
            "product_name": "护理床",
            "brand": "测试品牌",
            "category": "医疗健康",
            "subcategory": "护理床",
            "price_cny": 2999,
            "specifications": {"电机": "静音双电机", "护栏": "可升降", "安全性": "防滑脚轮"},
        },
        "market_config": {"target_crowd": "居家康养家庭", "strategy": "安全信任优先", "scene": "康养渠道"},
    },
]


def create_user(client: TestClient) -> dict[str, str]:
    username = f"formal_{uuid4().hex[:10]}"
    response = client.post("/api/auth/register", json={"username": username, "password": "12345678"})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def run_scenario(client: TestClient, headers: dict[str, str], scenario: dict) -> dict:
    created = client.post("/api/simulations", headers=headers, json={"project_name": scenario["name"]})
    created.raise_for_status()
    project_id = created.json()["id"]
    client.put(
        f"/api/simulations/{project_id}/step1",
        headers=headers,
        json={"product_definition": scenario["product_definition"]},
    ).raise_for_status()
    client.put(
        f"/api/simulations/{project_id}/step2",
        headers=headers,
        json={"market_config": scenario["market_config"]},
    ).raise_for_status()
    client.post(f"/api/simulations/{project_id}/submit", headers=headers, json={}).raise_for_status()
    queued = client.post(f"/api/simulations/{project_id}/run", headers=headers)
    queued.raise_for_status()
    worker.run_loop(once=True, timeout=3)
    report = client.get(f"/api/simulations/{project_id}/report", headers=headers)
    report.raise_for_status()
    return {
        "project_id": project_id,
        "task_id": queued.json()["task"]["task_id"],
        "report": report.json()["report"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行正式功能场景并保存日志")
    parser.add_argument("--limit", type=int, default=len(SCENARIOS), help="最多运行多少个内置场景")
    parser.add_argument("--run-dir", default="", help="指定日志目录，默认 logs/formal_runs/YYYYMMDD_HHMMSS")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else PROJECT_ROOT / "logs" / "formal_runs" / utc_now_naive().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    os.environ["FORMAL_RUN_DIR"] = str(run_dir)

    client = TestClient(app)
    headers = create_user(client)
    results = []
    for scenario in SCENARIOS[: args.limit]:
        result = run_scenario(client, headers, scenario)
        results.append(
            {
                "scenario": scenario["name"],
                "project_id": result["project_id"],
                "task_id": result["task_id"],
                "is_fallback": result["report"].get("is_fallback"),
                "quality_warnings": result["report"].get("quality_warnings", []),
                "formal_test_log_path": result["report"].get("formal_test_log_path"),
                "purchase_intent_avg": result["report"].get("aggregation", {}).get("purchase_intent_avg"),
            }
        )

    summary_path = run_dir / "formal_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "summary_path": str(summary_path), "items": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
