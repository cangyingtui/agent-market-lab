from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from batch_product_simulations import ApiClient, clean_text


def list_projects(client: ApiClient) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for page in range(1, 101):
        payload = client.request(
            "GET",
            "/api/simulations",
            retry_safe=True,
            params={"page": page, "page_size": 100},
        )
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise RuntimeError("项目列表响应缺少items数组")
        projects.extend(item for item in items if isinstance(item, dict))
        if len(items) < 100:
            break
    return projects


def main() -> int:
    parser = argparse.ArgumentParser(description="仅清理当前登录专用测试账号的仿真项目")
    parser.add_argument("command", choices=("list", "delete-all", "delete-one"))
    parser.add_argument("--confirm-username", required=True)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--confirm-project-name")
    args = parser.parse_args()

    client = ApiClient()
    try:
        client.health()
        user = client.login()
        username = clean_text(user.get("username"))
        user_id = int(user.get("id") or 0)
        if username != clean_text(args.confirm_username):
            raise RuntimeError("当前登录账号与确认账号不一致，未执行任何删除")
        if clean_text(user.get("plan_type")).lower() != "pro":
            raise RuntimeError("当前测试账号不是Pro，未执行任何删除")

        projects = list_projects(client)
        foreign = [item for item in projects if int(item.get("user_id") or user_id) != user_id]
        if foreign:
            raise RuntimeError("项目列表出现其他用户项目，停止操作")
        snapshot = {
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "username": username,
            "user_id": user_id,
            "count": len(projects),
            "status_counts": dict(Counter(clean_text(item.get("status")) for item in projects)),
            "projects": projects,
        }
        if args.snapshot:
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            args.snapshot.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.command == "list":
            print(json.dumps({key: value for key, value in snapshot.items() if key != "projects"}, ensure_ascii=False))
            return 0

        if args.command == "delete-one":
            matches = [item for item in projects if int(item.get("id") or 0) == int(args.project_id or 0)]
            if len(matches) != 1:
                raise RuntimeError("待删除项目ID未唯一命中")
            project = matches[0]
            project_name = clean_text(project.get("project_name"))
            if project_name != clean_text(args.confirm_project_name):
                raise RuntimeError("项目名称与确认值不一致，未执行删除")
            if clean_text(project.get("status")) in {"running", "submitted", "queued", "report_generation_waiting"}:
                raise RuntimeError("项目仍在活动状态，未执行删除")
            client.request("DELETE", f"/api/simulations/{int(project['id'])}")
            remaining = list_projects(client)
            print(json.dumps({"username": username, "deleted_project_id": args.project_id, "deleted_project_name": project_name, "remaining": len(remaining)}, ensure_ascii=False))
            return 0

        if args.expected_count is None or args.expected_count != len(projects):
            raise RuntimeError(f"项目数量与确认值不一致：expected={args.expected_count}, actual={len(projects)}")
        active_statuses = {"running", "submitted", "queued", "report_generation_waiting"}
        active = [item for item in projects if clean_text(item.get("status")) in active_statuses]
        if active:
            raise RuntimeError(f"仍有{len(active)}个活动项目，停止删除")

        deleted = 0
        for item in projects:
            project_id = int(item.get("id") or 0)
            if not project_id:
                raise RuntimeError("项目缺少ID，停止删除")
            client.request("DELETE", f"/api/simulations/{project_id}")
            deleted += 1
        remaining = list_projects(client)
        if remaining:
            raise RuntimeError(f"删除后仍剩余{len(remaining)}个项目")
        print(json.dumps({"username": username, "user_id": user_id, "deleted": deleted, "remaining": 0}, ensure_ascii=False))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
