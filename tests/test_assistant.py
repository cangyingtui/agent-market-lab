from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import assistant_service
from app.config import settings


@pytest.mark.no_db
def test_assistant_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/chat",
        json={"project_id": 1, "page": "step1", "message": "价格怎么填？"},
    )
    assert response.status_code == 401


def test_assistant_fallback_without_llm_key(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "embedding_api_key", "")
    created = client.post("/api/simulations", headers=auth_headers, json={"project_name": "pytest 助手项目"})
    assert created.status_code == 201

    response = client.post(
        "/api/assistant/chat",
        headers=auth_headers,
        json={
            "project_id": created.json()["id"],
            "page": "step1",
            "message": "价格应该怎么填？",
            "field_key": "price_cny",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert "价格" in body["reply"]
    assert body["quick_replies"]
    assert body["field_cards"][0]["key"] == "price_cny"


def test_assistant_uses_bailian_embedding_key_with_qwen_plus(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    calls: list[dict] = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content="这是价格字段。\n填写数字。\n例子：3999。")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "embedding_api_key", "pytest-bailian-key")
    monkeypatch.setattr(settings, "embedding_api_base", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(assistant_service, "create_assistant_client", lambda: fake_client)
    created = client.post("/api/simulations", headers=auth_headers, json={"project_name": "pytest 百炼助手项目"})
    assert created.status_code == 201

    response = client.post(
        "/api/assistant/chat",
        headers=auth_headers,
        json={
            "project_id": created.json()["id"],
            "page": "step1",
            "message": "价格应该怎么填？",
            "field_key": "price_cny",
        },
    )

    assert response.status_code == 200
    assert response.json()["source"] == "llm"
    assert calls[0]["model"] == "qwen-plus"


def test_assistant_rejects_other_users_project(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "embedding_api_key", "")
    created = client.post("/api/simulations", headers=auth_headers, json={"project_name": "pytest 私有助手项目"})
    assert created.status_code == 201

    second_user = client.post(
        "/api/auth/register",
        json={"username": "pytest_assistant_other", "password": "12345678"},
    )
    assert second_user.status_code == 201
    second_headers = {"Authorization": f"Bearer {second_user.json()['access_token']}"}

    response = client.post(
        "/api/assistant/chat",
        headers=second_headers,
        json={
            "project_id": created.json()["id"],
            "page": "step2",
            "message": "目标人群怎么选？",
        },
    )
    assert response.status_code == 404
