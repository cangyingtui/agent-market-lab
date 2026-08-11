from __future__ import annotations

from typing import Any


def create_openai_client(
    *,
    api_key: str,
    base_url: str | None = None,
    timeout: float | int = 30,
    max_retries: int | None = None,
) -> Any:
    """Create an OpenAI-compatible client without inheriting proxy settings.

    Older OpenAI SDK releases pass ``proxies=`` to their internally-created
    httpx client, while httpx 0.28 removed that keyword. Supplying an explicit
    transport keeps the deployed dependency set compatible and prevents host
    proxy environment variables from leaking into simulation requests.
    """

    import httpx
    from openai import OpenAI

    transport = httpx.Client(timeout=timeout, trust_env=False)
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url or None,
        "timeout": timeout,
        "http_client": transport,
    }
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    return OpenAI(**kwargs)
