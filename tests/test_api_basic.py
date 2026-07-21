from __future__ import annotations

from fastapi.testclient import TestClient

from app.redis_client import redis_json_get
from app.task_keys import project_progress_key


def test_health_and_readonly_endpoints(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["code"] == 0
    assert health.json()["ok"] is True
    assert health.json()["data"]["ok"] is True

    categories = client.get("/api/categories")
    assert categories.status_code == 200
    assert categories.json()["code"] == 0
    assert categories.json()["total"] >= 1
    category_id = categories.json()["items"][0]["id"]

    fields = client.get(f"/api/categories/{category_id}/fields")
    assert fields.status_code == 200
    assert "items" in fields.json()
    if fields.json()["items"]:
        assert "ui_schema" in fields.json()["items"][0]

    products = client.get("/api/products", params={"limit": 5})
    assert products.status_code == 200
    assert products.json()["total"] >= 1
    assert len(products.json()["items"]) <= 5

    market = client.get("/api/market/templates")
    assert market.status_code == 200
    assert market.json()["crowd"]["total"] >= 1
    assert market.json()["strategy"]["total"] >= 1
    assert market.json()["scene"]["total"] >= 1

    faiss = client.get("/api/debug/faiss/status")
    assert faiss.status_code == 200
    assert faiss.json()["index_dim"] == 1024
    assert faiss.json()["metadata_matches_index"] is True

    pdf = client.get("/api/debug/pdf/status")
    assert pdf.status_code == 200
    assert "checks" in pdf.json()
    assert "frontend_base_url" in pdf.json()


def test_auth_simulation_submit_and_queue(
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> None:
    headers = auth_headers
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"].startswith("pytest_")

    created = client.post("/api/simulations", headers=headers, json={"project_name": "pytest 仿真"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["plan_type_used"] == "basic"

    step1 = client.put(
        f"/api/simulations/{project_id}/step1",
        headers=headers,
        json={"product_definition": sample_product_definition},
    )
    assert step1.status_code == 200
    stale = client.put(
        f"/api/simulations/{project_id}/step1",
        headers=headers,
        json={"product_definition": sample_product_definition, "draft_version": 999},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "DRAFT_CONFLICT"
    assert "server_draft_version" in stale.json()["data"]

    step2 = client.put(
        f"/api/simulations/{project_id}/step2",
        headers=headers,
        json={"market_config": sample_market_config},
    )
    assert step2.status_code == 200

    submitted = client.post(f"/api/simulations/{project_id}/submit", headers=headers, json={})
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["plan_type_used"] == "basic"
    assert submitted.json()["snapshot_hash"]
    snapshot = submitted.json()["config_snapshot"]
    assert snapshot["snapshot_id"].startswith(f"snap_{project_id}_")
    assert snapshot["snapshot_hash"] == submitted.json()["snapshot_hash"]
    assert snapshot["user_id"]
    assert snapshot["submitted_at"]
    assert snapshot["simulation_params"]["rag_top_k"] >= 1
    assert snapshot["simulation_params"]["social_network"]["k"] == 4
    assert snapshot["simulation_params"]["social_network"]["representative_agent_count"] == 60
    assert set(snapshot["rag_search_queries"]) == {"product_query", "competitor_query", "market_query"}
    rag_text = snapshot["rag_search_text"]
    assert rag_text
    assert "一线/新一线" in rag_text
    assert "续航" in rag_text
    assert "品牌旗舰店" in rag_text

    queued = client.post(f"/api/simulations/{project_id}/run", headers=headers)
    assert queued.status_code == 200
    assert queued.json()["task"]["status"] == "queued"
    assert queued.json()["project"]["status"] == "submitted"
    task_id = queued.json()["task"]["task_id"]
    assert task_id.startswith("sim_")
    assert queued.json()["task"]["current_stage"] == "queued"
    assert queued.json()["task"]["stages"][0]["key"] == "queued"
    assert "queue_diagnostics" in queued.json()["task"]
    assert redis_json_get(project_progress_key(project_id))["task_id"] == task_id
    blocked_delete = client.delete(f"/api/simulations/{project_id}", headers=headers)
    assert blocked_delete.status_code == 409
    assert blocked_delete.json()["detail"] == "排队或运行中的项目请先取消任务"
    logs = client.get(f"/api/simulations/{project_id}/logs", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["project_id"] == project_id
    assert logs.json()["items"] == []
    me_after_run = client.get("/api/auth/me", headers=headers)
    assert me_after_run.status_code == 200
    assert me_after_run.json()["basic_quota_remaining"] == 1


def test_profile_upgrade_requires_contact_and_project_delete(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    headers = auth_headers
    profile = client.get("/api/user/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["plan_type"] == "basic"
    updated_profile = client.put(
        "/api/user/profile",
        headers=headers,
        json={"full_name": "Pytest 用户", "email": None, "avatar_url": "https://example.test/avatar.png"},
    )
    assert updated_profile.status_code == 200
    assert updated_profile.json()["full_name"] == "Pytest 用户"
    assert updated_profile.json()["avatar_url"] == "https://example.test/avatar.png"

    old_project = client.post("/api/simulations", headers=headers, json={"project_name": "pytest 普通版项目"})
    assert old_project.status_code == 201
    old_project_id = old_project.json()["id"]
    assert old_project.json()["plan_type_used"] == "basic"

    upgraded = client.post("/api/user/upgrade", headers=headers, json={"reason": "pytest"})
    assert upgraded.status_code == 403
    assert upgraded.json()["detail"]["code"] == "UPGRADE_CONTACT_REQUIRED"
    assert "18960333566" in upgraded.json()["detail"]["message"]

    old_after_upgrade = client.get(f"/api/simulations/{old_project_id}", headers=headers)
    assert old_after_upgrade.status_code == 200
    assert old_after_upgrade.json()["plan_type_used"] == "basic"

    page = client.get("/api/simulations", headers=headers, params={"page": 1, "page_size": 1, "status": "draft"})
    assert page.status_code == 200
    assert page.json()["page"] == 1
    assert page.json()["page_size"] == 1
    assert page.json()["total"] >= 1
    assert len(page.json()["items"]) == 1

    deleted = client.delete(f"/api/simulations/{old_project_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True
    assert client.get(f"/api/simulations/{old_project_id}", headers=headers).status_code == 404


def test_step2_multi_crowd_validation_and_legacy_fields(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    project = client.post("/api/simulations", headers=auth_headers, json={"project_name": "pytest 多客群"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    valid = client.put(
        f"/api/simulations/{project_id}/step2",
        headers=auth_headers,
        json={
            "market_config": {
                "crowd_segments": [
                    {"name": "年轻白领", "ratio": 60, "profile": {"price_sensitivity": "medium"}},
                    {"name": "育儿家庭", "ratio": 40, "profile": {"price_sensitivity": "high"}},
                ]
            }
        },
    )
    assert valid.status_code == 200
    assert valid.json()["market_config"]["target_crowd"] == "年轻白领"
    assert valid.json()["market_config"]["crowd_profile"]["price_sensitivity"] == "medium"

    invalid_total = client.put(
        f"/api/simulations/{project_id}/step2",
        headers=auth_headers,
        json={"market_config": {"crowd_segments": [{"name": "年轻白领", "ratio": 60}]}},
    )
    assert invalid_total.status_code == 422
    assert invalid_total.json()["code"] == "CROWD_RATIO_TOTAL_INVALID"

    over_basic_limit = client.put(
        f"/api/simulations/{project_id}/step2",
        headers=auth_headers,
        json={
            "market_config": {
                "crowd_segments": [
                    {"name": "客群 A", "ratio": 25},
                    {"name": "客群 B", "ratio": 25},
                    {"name": "客群 C", "ratio": 25},
                    {"name": "客群 D", "ratio": 25},
                ]
            }
        },
    )
    assert over_basic_limit.status_code == 403
    assert over_basic_limit.json()["code"] == "BASIC_CROWD_LIMIT"
