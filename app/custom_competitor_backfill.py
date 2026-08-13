from __future__ import annotations

import re
import unicodedata
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    CustomCompetitorBackfillJob,
    Product,
    ProductCategory,
    SimulationProject,
    SimulationTaskLog,
)
from app.time_utils import utc_now_naive


MODEL_VERSION = "custom_competitor_reuse_v1"


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalized_identity(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).casefold()
    return "".join(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text))


def brand_similarity(left: Any, right: Any) -> float:
    left_value = normalized_identity(left)
    right_value = normalized_identity(right)
    if not left_value or not right_value:
        return 0.0
    if left_value == right_value:
        return 1.0
    shorter, longer = sorted((left_value, right_value), key=len)
    if len(shorter) >= 2 and shorter in longer:
        return 0.92
    left_tokens = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", unicodedata.normalize("NFKC", clean_text(left)).casefold()))
    right_tokens = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", unicodedata.normalize("NFKC", clean_text(right)).casefold()))
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0


def positive_price(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def is_custom_competitor(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    raw_id = item.get("id")
    return bool(
        item.get("is_custom")
        or clean_text(item.get("competitor_type")).lower() == "custom"
        or clean_text(item.get("source")).lower() == "custom"
        or (isinstance(raw_id, (int, float)) and raw_id < 0)
    )


def custom_competitors_from_snapshot(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    competitors = market.get("competitors") if isinstance(market.get("competitors"), list) else []
    return [dict(item) for item in competitors if is_custom_competitor(item)]


def required_fields_missing(item: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("brand", "category", "subcategory"):
        if not clean_text(item.get(field)):
            missing.append(field)
    if not clean_text(item.get("product_name") or item.get("name")):
        missing.append("product_name")
    if positive_price(item.get("price_cny") or item.get("price")) is None:
        missing.append("price_cny")
    return missing


def similarity_result(item: dict[str, Any], product: Product) -> dict[str, Any]:
    category_match = clean_text(item.get("category")) == clean_text(product.category)
    subcategory_match = clean_text(item.get("subcategory")) == clean_text(product.subcategory)
    custom_price = positive_price(item.get("price_cny") or item.get("price"))
    product_price = positive_price(product.price_cny)
    brand_score = brand_similarity(item.get("brand"), product.brand)
    absolute_delta = abs(custom_price - product_price) if custom_price and product_price else None
    relative_delta = absolute_delta / custom_price if absolute_delta is not None and custom_price else None
    price_match = bool(
        absolute_delta is not None
        and (
            absolute_delta <= settings.custom_competitor_price_abs_tolerance_cny
            or (relative_delta is not None and relative_delta <= settings.custom_competitor_price_rel_tolerance)
        )
    )
    brand_match = brand_score >= settings.custom_competitor_brand_similarity_threshold
    highly_similar = category_match and subcategory_match and brand_match and price_match
    price_score = 0.0
    if relative_delta is not None:
        price_score = max(0.0, 1.0 - relative_delta / max(settings.custom_competitor_price_rel_tolerance, 0.01))
    score = 0.4 * float(category_match and subcategory_match) + 0.3 * brand_score + 0.3 * price_score
    return {
        "highly_similar": highly_similar,
        "score": round(score, 4),
        "category_match": category_match,
        "subcategory_match": subcategory_match,
        "brand_similarity": round(brand_score, 4),
        "absolute_price_delta": round(absolute_delta, 2) if absolute_delta is not None else None,
        "relative_price_delta": round(relative_delta, 4) if relative_delta is not None else None,
    }


def candidate_products(db: Session, item: dict[str, Any]) -> list[Product]:
    price = positive_price(item.get("price_cny") or item.get("price"))
    if price is None:
        return []
    window = max(settings.custom_competitor_price_abs_tolerance_cny, price * settings.custom_competitor_price_rel_tolerance)
    stmt = select(Product).where(
        Product.is_active.is_(True),
        Product.category == clean_text(item.get("category")),
        Product.subcategory == clean_text(item.get("subcategory")),
        Product.price_cny.is_not(None),
        Product.price_cny >= max(0.01, price - window),
        Product.price_cny <= price + window,
    )
    return list(db.scalars(stmt.limit(300)))


def find_highly_similar_product(db: Session, item: dict[str, Any]) -> tuple[Product | None, dict[str, Any] | None]:
    matches: list[tuple[float, Product, dict[str, Any]]] = []
    for product in candidate_products(db, item):
        result = similarity_result(item, product)
        if result["highly_similar"]:
            matches.append((float(result["score"]), product, result))
    if not matches:
        return None, None
    _, product, result = max(matches, key=lambda row: (row[0], -row[1].id))
    return product, result


def compact_provenance(item: dict[str, Any]) -> dict[str, Any]:
    provenance = item.get("data_provenance") if isinstance(item.get("data_provenance"), dict) else {}
    return {
        "product_record_id": provenance.get("product_record_id"),
        "collection_date": provenance.get("collection_date"),
        "collector": provenance.get("collector"),
        "review_status": provenance.get("review_status"),
        "price_type": provenance.get("price_type"),
        "sales_channel": provenance.get("sales_channel"),
        "product_url": provenance.get("product_url"),
        "price_status": item.get("price_status"),
    }


def resolve_active_category(db: Session, item: dict[str, Any]) -> ProductCategory | None:
    return db.scalar(
        select(ProductCategory).where(
            ProductCategory.category == clean_text(item.get("category")),
            ProductCategory.subcategory == clean_text(item.get("subcategory")),
            ProductCategory.is_active.is_(True),
        )
    )


def insert_custom_competitor(
    db: Session,
    item: dict[str, Any],
    *,
    project: SimulationProject,
    job: CustomCompetitorBackfillJob,
    source_row: int,
    category: ProductCategory,
) -> Product:
    specifications = dict(item.get("specifications")) if isinstance(item.get("specifications"), dict) else {}
    specifications["_custom_competitor_ingestion"] = {
        "model_version": MODEL_VERSION,
        "source": "simulation_custom_competitor",
        "project_id": project.id,
        "user_id": project.user_id,
        "snapshot_hash": job.snapshot_hash,
        "ingested_at": utc_now_naive().replace(microsecond=0).isoformat() + "Z",
        "provenance": compact_provenance(item),
    }
    product = Product(
        category_id=category.id,
        category=clean_text(item.get("category")),
        subcategory=clean_text(item.get("subcategory")),
        product_name=clean_text(item.get("product_name") or item.get("name")),
        brand=clean_text(item.get("brand")),
        confirmed_sku=clean_text(item.get("confirmed_sku")) or None,
        price_cny=positive_price(item.get("price_cny") or item.get("price")),
        specifications=specifications,
        source_file="simulation_custom_competitor",
        source_row=source_row,
        collection_time=utc_now_naive(),
        quality_status="complete",
        is_active=True,
    )
    db.add(product)
    db.flush()
    return product


def enqueue_project_backfill(db: Session, project: SimulationProject) -> CustomCompetitorBackfillJob | None:
    snapshot = project.config_snapshot if isinstance(project.config_snapshot, dict) else {}
    competitors = custom_competitors_from_snapshot(snapshot)
    if not competitors or not project.snapshot_hash:
        return None
    existing = db.scalar(
        select(CustomCompetitorBackfillJob).where(
            CustomCompetitorBackfillJob.project_id == project.id,
            CustomCompetitorBackfillJob.snapshot_hash == project.snapshot_hash,
        )
    )
    if existing:
        return existing
    job = CustomCompetitorBackfillJob(
        project_id=project.id,
        user_id=project.user_id,
        snapshot_hash=project.snapshot_hash,
        status="pending",
        custom_count=len(competitors),
    )
    db.add(job)
    db.flush()
    return job


def reset_stale_jobs(db: Session) -> int:
    cutoff = utc_now_naive() - timedelta(seconds=settings.custom_competitor_backfill_stale_seconds)
    jobs = list(
        db.scalars(
            select(CustomCompetitorBackfillJob).where(
                CustomCompetitorBackfillJob.status == "processing",
                CustomCompetitorBackfillJob.started_at.is_not(None),
                CustomCompetitorBackfillJob.started_at < cutoff,
            )
        )
    )
    for job in jobs:
        if job.attempt_count < settings.custom_competitor_backfill_max_retries:
            job.status = "pending"
            job.error_reason = "处理进程中断，已自动重新排队"
        else:
            job.status = "failed"
            job.completed_at = utc_now_naive()
            job.error_reason = "处理进程中断且已达到最大重试次数"
    if jobs:
        db.commit()
    return len(jobs)


def claim_next_job(db: Session) -> CustomCompetitorBackfillJob | None:
    reset_stale_jobs(db)
    job = db.scalar(
        select(CustomCompetitorBackfillJob)
        .where(CustomCompetitorBackfillJob.status == "pending")
        .order_by(CustomCompetitorBackfillJob.created_at, CustomCompetitorBackfillJob.id)
        .limit(1)
        .with_for_update()
    )
    if job is None:
        return None
    job.status = "processing"
    job.attempt_count += 1
    job.started_at = utc_now_naive()
    job.error_reason = None
    db.commit()
    db.refresh(job)
    return job


def process_claimed_job(db: Session, job: CustomCompetitorBackfillJob) -> dict[str, Any]:
    project = db.get(SimulationProject, job.project_id)
    if project is None:
        result = {"status": "skipped", "reason": "project_not_found", "items": []}
    elif project.snapshot_hash != job.snapshot_hash:
        result = {"status": "skipped", "reason": "snapshot_changed", "items": []}
    elif project.status not in {"completed", "report_waiting"}:
        result = {"status": "skipped", "reason": "simulation_not_completed", "items": []}
    else:
        snapshot = project.config_snapshot if isinstance(project.config_snapshot, dict) else {}
        items: list[dict[str, Any]] = []
        for index, competitor in enumerate(custom_competitors_from_snapshot(snapshot), 1):
            missing = required_fields_missing(competitor)
            if missing:
                items.append(
                    {
                        "product_name": competitor.get("product_name"),
                        "action": "skipped",
                        "reason": "missing_required_fields",
                        "missing_fields": missing,
                    }
                )
                continue
            provenance = competitor.get("data_provenance") if isinstance(competitor.get("data_provenance"), dict) else {}
            if clean_text(provenance.get("review_status")).lower() == "rejected":
                items.append(
                    {
                        "product_name": competitor.get("product_name"),
                        "action": "skipped",
                        "reason": "manual_review_rejected",
                    }
                )
                continue
            category = resolve_active_category(db, competitor)
            if category is None:
                items.append(
                    {
                        "product_name": competitor.get("product_name"),
                        "action": "skipped",
                        "reason": "unknown_or_inactive_category",
                    }
                )
                continue
            matched, similarity = find_highly_similar_product(db, competitor)
            if matched is not None:
                items.append(
                    {
                        "product_name": competitor.get("product_name"),
                        "action": "matched_existing",
                        "existing_product_id": matched.id,
                        "similarity": similarity,
                    }
                )
                continue
            product = insert_custom_competitor(
                db,
                competitor,
                project=project,
                job=job,
                source_row=project.id * 1000 + index,
                category=category,
            )
            items.append(
                {
                    "product_name": competitor.get("product_name"),
                    "action": "inserted",
                    "product_id": product.id,
                }
            )
        result = {"status": "completed", "model_version": MODEL_VERSION, "items": items}

    job.inserted_count = sum(item.get("action") == "inserted" for item in result["items"])
    job.matched_count = sum(item.get("action") == "matched_existing" for item in result["items"])
    job.skipped_count = sum(item.get("action") == "skipped" for item in result["items"])
    job.result_json = result
    job.status = "completed"
    job.completed_at = utc_now_naive()
    if project is not None:
        db.add(
            SimulationTaskLog(
                project_id=project.id,
                task_id=project.task_id,
                snapshot_id=job.snapshot_hash,
                stage="custom_competitor_backfill",
                log_level="info",
                message="自定义竞品低优先级复用处理完成",
                detail_json={
                    "job_id": job.id,
                    "inserted": job.inserted_count,
                    "matched": job.matched_count,
                    "skipped": job.skipped_count,
                },
            )
        )
    db.commit()
    return result


def fail_claimed_job(db: Session, job_id: int, exc: Exception) -> None:
    db.rollback()
    job = db.get(CustomCompetitorBackfillJob, job_id)
    if job is None:
        return
    job.error_reason = str(exc)[:2000]
    if job.attempt_count < settings.custom_competitor_backfill_max_retries:
        job.status = "pending"
    else:
        job.status = "failed"
        job.completed_at = utc_now_naive()
    db.commit()


def process_next_job(db: Session) -> dict[str, Any] | None:
    if not settings.custom_competitor_backfill_enabled:
        return None
    job = claim_next_job(db)
    if job is None:
        return None
    try:
        return {"job_id": job.id, **process_claimed_job(db, job)}
    except Exception as exc:
        fail_claimed_job(db, job.id, exc)
        return {"job_id": job.id, "status": "retry_or_failed", "error": str(exc)}
