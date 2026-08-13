from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    CustomCompetitorBackfillJob,
    DistillCheckLog,
    ExportTask,
    QuotaLog,
    RagTraceLog,
    ShareToken,
    SimulationProject,
    SimulationTaskLog,
    UpgradeLog,
    User,
)
from app.redis_client import get_redis_client
from app.task_keys import export_progress_key


TEST_PREFIXES = ("pytest_",)


def cleanup_redis_for_task(task_id: str | None, project_id: int | None = None) -> None:
    client = get_redis_client()
    if task_id:
        for queue_name in (settings.redis_basic_queue, settings.redis_pro_queue, settings.redis_task_queue, settings.redis_export_queue):
            for raw_item in client.lrange(queue_name, 0, -1):
                if task_id in raw_item:
                    client.lrem(queue_name, 0, raw_item)
        client.delete(f"simulation:progress:{task_id}")
        client.delete(f"simulation:cancel:{task_id}")
        client.delete(f"simulation:heartbeat:{task_id}")
    if project_id:
        client.delete(f"simulation:project:{project_id}:running")


def cleanup_test_users() -> None:
    with SessionLocal() as db:
        users = list(db.scalars(select(User).where(User.username.like("pytest\\_%", escape="\\"))))
        user_ids = [user.id for user in users]
        project_ids: list[int] = []
        task_ids: list[str] = []
        export_ids: list[int] = []
        if user_ids:
            projects = list(
                db.scalars(select(SimulationProject).where(SimulationProject.user_id.in_(user_ids)))
            )
            project_ids = [project.id for project in projects]
            task_ids = [project.task_id for project in projects if project.task_id]
        if project_ids:
            export_ids = list(
                db.scalars(select(ExportTask.id).where(ExportTask.project_id.in_(project_ids)))
            )

        for task_id in task_ids:
            cleanup_redis_for_task(task_id)
        for project_id in project_ids:
            cleanup_redis_for_task(None, project_id)
        client = get_redis_client()
        for export_id in export_ids:
            client.delete(export_progress_key(export_id))

        if project_ids:
            db.execute(delete(CustomCompetitorBackfillJob).where(CustomCompetitorBackfillJob.project_id.in_(project_ids)))
            for model in (ExportTask, ShareToken, QuotaLog, DistillCheckLog, RagTraceLog, SimulationTaskLog):
                db.execute(delete(model).where(model.project_id.in_(project_ids)))
            db.execute(delete(SimulationProject).where(SimulationProject.id.in_(project_ids)))
        if user_ids:
            db.execute(delete(UpgradeLog).where(UpgradeLog.user_id.in_(user_ids)))
            db.execute(delete(QuotaLog).where(QuotaLog.user_id.in_(user_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


@pytest.fixture(autouse=True)
def isolate_test_redis_queues(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if request.node.get_closest_marker("no_db"):
        yield
        return
    suffix = uuid4().hex
    monkeypatch.setattr(settings, "redis_task_queue", f"pytest:simulation:queue:{suffix}")
    monkeypatch.setattr(settings, "redis_pro_queue", f"pytest:simulation:queue:pro:{suffix}")
    monkeypatch.setattr(settings, "redis_basic_queue", f"pytest:simulation:queue:basic:{suffix}")
    monkeypatch.setattr(settings, "redis_export_queue", f"pytest:simulation:queue:exports:{suffix}")
    yield


@pytest.fixture(autouse=True)
def clean_test_data(request: pytest.FixtureRequest, isolate_test_redis_queues: None) -> Iterator[None]:
    if request.node.get_closest_marker("no_db"):
        yield
        return
    cleanup_test_users()
    yield
    cleanup_test_users()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    username = f"pytest_{uuid4().hex[:10]}"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "12345678"},
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def sample_product_definition() -> dict:
    return {
        "product_name": "测试智能手机",
        "brand": "测试品牌",
        "category": "消费电子",
        "subcategory": "智能手机",
        "price_cny": 3999,
        "specifications": {"电池": "5000mAh", "防水": "IP68", "屏幕": "OLED 120Hz"},
    }


@pytest.fixture()
def sample_market_config() -> dict:
    return {
        "target_crowd": "高端用户",
        "strategy": "差异化",
        "scene": "线上首发",
        "crowd_profile": {
            "age_range": "28-45",
            "city_tier": "一线/新一线",
            "income_level": "高收入",
            "life_stage": "高端商务与科技尝鲜",
            "price_sensitivity": "low",
            "feature_priorities": ["续航", "屏幕", "防水"],
            "channel_preferences": ["品牌旗舰店", "内容种草"],
            "purchase_motivations": ["提升效率", "体验升级"],
            "risk_concerns": ["售后体验", "价格波动"],
            "custom_description": "愿意为可靠体验和品牌服务支付溢价。",
        },
    }
