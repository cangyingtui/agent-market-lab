from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time_utils import utc_now_naive


JsonColumn = MySQLJSON


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    plan_type: Mapped[str] = mapped_column(String(20), default="basic", nullable=False)
    basic_quota_remaining: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    pro_expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SimulationProject(Base, TimestampMixin):
    __tablename__ = "simulation_projects"
    __table_args__ = (
        Index("idx_sim_projects_user_status_created", "user_id", "status", "created_at"),
        Index("idx_sim_projects_user_updated", "user_id", "updated_at"),
        Index("idx_sim_projects_status_heartbeat", "status", "last_heartbeat_at"),
        Index("idx_sim_projects_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    plan_type_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_definition: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    market_config: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    result_data: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    quota_charged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    draft_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    simulation_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retry: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProductCategory(Base, TimestampMixin):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subcategory: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductFieldTemplate(Base, TimestampMixin):
    __tablename__ = "product_field_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("product_categories.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(40), default="string", nullable=False)
    field_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ui_control: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ui_schema: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True, deferred=True)
    default_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_category_quality", "category_id", "quality_status", "is_active"),
        Index("idx_products_category_price", "category_id", "price_cny"),
        Index("idx_products_name", "product_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    confirmed_sku: Mapped[str | None] = mapped_column(String(160), nullable=True)
    price_cny: Mapped[float | None] = mapped_column(Float, nullable=True)
    specifications: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collection_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(30), default="complete", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class CustomCompetitorBackfillJob(Base, TimestampMixin):
    __tablename__ = "custom_competitor_backfill_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_hash", name="uq_custom_competitor_backfill_project_snapshot"),
        Index("idx_custom_competitor_backfill_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    custom_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MarketCrowdTemplate(Base, TimestampMixin):
    __tablename__ = "market_crowd_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketStrategyTemplate(Base, TimestampMixin):
    __tablename__ = "market_strategy_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_params: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketSceneTemplate(Base, TimestampMixin):
    __tablename__ = "market_scene_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SimulationTaskLog(Base):
    __tablename__ = "simulation_task_logs"
    __table_args__ = (
        Index("idx_task_logs_project_task_created", "project_id", "task_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_projects.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    log_level: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class RagTraceLog(Base):
    __tablename__ = "rag_trace_logs"
    __table_args__ = (
        Index("idx_rag_trace_project_task_snapshot", "project_id", "task_id", "snapshot_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_projects.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    query_type: Mapped[str] = mapped_column(String(40), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    retrieved_items: Mapped[dict | list | None] = mapped_column(JsonColumn, nullable=True)
    final_used_items: Mapped[dict | list | None] = mapped_column(JsonColumn, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class DistillCheckLog(Base):
    __tablename__ = "distill_check_logs"
    __table_args__ = (
        Index("idx_distill_project_batch", "project_id", "validation_batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_projects.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_batch_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sample_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    distill_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_consistent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    judge_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class QuotaLog(Base):
    __tablename__ = "quota_logs"
    __table_args__ = (
        Index("idx_quota_user_project_created", "user_id", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_projects.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    change_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class ExportTask(Base):
    __tablename__ = "export_tasks"
    __table_args__ = (
        Index("idx_export_project_user_status", "project_id", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("simulation_projects.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    download_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ShareToken(Base):
    __tablename__ = "share_tokens"
    __table_args__ = (
        Index("idx_share_token_expires", "token_hash", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("simulation_projects.id"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class UpgradeLog(Base):
    __tablename__ = "upgrade_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    from_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_plan: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class SystemFeatureFlag(Base, TimestampMixin):
    __tablename__ = "system_feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flag_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
