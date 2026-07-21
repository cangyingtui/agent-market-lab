from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    full_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateUserProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_k: int | None = Field(default=None, ge=1, le=200)
    source_include: list[str] | None = None
    source_exclude: list[str] | None = None
    include_products: bool = True
    product_definition: dict[str, Any] | None = None


class AssistantHistoryMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class AssistantChatRequest(BaseModel):
    project_id: int = Field(ge=1)
    page: str = Field(pattern="^(step1|step2|step3|step4)$")
    message: str = Field(min_length=1, max_length=1000)
    field_key: str | None = Field(default=None, max_length=120)
    field_label: str | None = Field(default=None, max_length=160)
    history: list[AssistantHistoryMessage] = Field(default_factory=list, max_length=8)
    client_context: dict[str, Any] = Field(default_factory=dict)


class CreateSimulationRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=160)


class UpdateSimulationDraftRequest(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=160)
    product_definition: dict[str, Any] | None = None
    market_config: dict[str, Any] | None = None
    draft_version: int | None = Field(default=None, ge=1)


class Step1Request(BaseModel):
    product_definition: dict[str, Any]
    draft_version: int | None = Field(default=None, ge=1)


class Step2Request(BaseModel):
    market_config: dict[str, Any]
    draft_version: int | None = Field(default=None, ge=1)


class SubmitSimulationRequest(BaseModel):
    product_definition: dict[str, Any] | None = None
    market_config: dict[str, Any] | None = None


class ExportRequest(BaseModel):
    format: str = Field(default="json", pattern="^(json|markdown|excel|pdf)$")


class ShareTokenRequest(BaseModel):
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class UpgradeUserRequest(BaseModel):
    reason: str | None = Field(default="local_development", max_length=120)


class DistillDebugRequest(BaseModel):
    snapshot: dict[str, Any] = Field(default_factory=dict)
    agents: list[dict[str, Any]] = Field(default_factory=list)
    purchase_decisions: list[dict[str, Any]] = Field(default_factory=list)
    threshold: float | None = Field(default=None, ge=0, le=1)
    sample_size: int | None = Field(default=None, ge=1, le=1000)
    validation_batch_id: str | None = Field(default=None, max_length=120)
