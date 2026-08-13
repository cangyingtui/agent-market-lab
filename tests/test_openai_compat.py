from typing import Any

import httpx
import openai
import pytest

from app.openai_compat import create_openai_client


pytestmark = pytest.mark.no_db


def test_create_openai_client_supplies_explicit_http_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    transport = object()

    def fake_http_client(**kwargs: Any) -> object:
        captured["httpx"] = kwargs
        return transport

    def fake_openai(**kwargs: Any) -> dict[str, Any]:
        captured["openai"] = kwargs
        return kwargs

    monkeypatch.setattr(httpx, "Client", fake_http_client)
    monkeypatch.setattr(openai, "OpenAI", fake_openai)

    result = create_openai_client(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        timeout=45,
        max_retries=2,
    )

    assert captured["httpx"] == {"timeout": 45, "trust_env": False}
    assert captured["openai"]["http_client"] is transport
    assert "proxies" not in captured["openai"]
    assert result["max_retries"] == 2
