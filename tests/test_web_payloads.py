from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.export_service import sanitize_report, sanitize_web_report
from app.main import project_to_dict


@pytest.mark.no_db
def test_project_payload_defaults_to_configs_without_heavy_result() -> None:
    project = SimpleNamespace(
        id=7,
        user_id=3,
        project_name="pytest lightweight payload",
        status="completed",
        plan_type_used="pro",
        product_definition={"product_name": "测试产品"},
        market_config={"target_crowd": "测试人群"},
        config_snapshot={"snapshot_id": "snap_7"},
        snapshot_hash="hash_7",
        result_data={"agent_samples": [{"agent_id": "agent_001"}]},
        task_id="sim_7",
        draft_version=2,
        simulation_version="v1",
        error_code=None,
        error_reason=None,
        submitted_at=None,
        started_at=None,
        last_heartbeat_at=None,
        completed_at=None,
        created_at=None,
        updated_at=None,
    )

    detail = project_to_dict(project)
    assert detail["product_definition"]["product_name"] == "测试产品"
    assert detail["market_config"]["target_crowd"] == "测试人群"
    assert "config_snapshot" not in detail
    assert "result_data" not in detail

    summary = project_to_dict(project, include_configs=False)
    assert "product_definition" not in summary
    assert "market_config" not in summary

    submitted = project_to_dict(project, include_snapshot=True)
    assert submitted["config_snapshot"]["snapshot_id"] == "snap_7"


@pytest.mark.no_db
def test_web_report_is_compact_while_export_report_keeps_full_detail() -> None:
    report = {
        "agent_samples": [
            {
                "agent_id": f"agent_{index:03d}",
                "neighbors": ["agent_001"],
                "base_maut_scores": {"function_fit": 0.5},
            }
            for index in range(25)
        ],
        "purchase_decisions": [{"agent_id": f"agent_{index:03d}"} for index in range(30)],
        "formatted_evidence": {"prompt_version": "internal"},
        "final_rag_evidence": {"market_query": [{"snippet": "internal"}]},
        "rag_evidence": {"market_query": [{"snippet": f"证据 {index}"} for index in range(30)]},
        "data_enrichment_candidates": [{"product_id": index} for index in range(30)],
        "chart_data": {"overview_metrics": {"purchase_intent_index": 75}},
        "social_simulation": {"rounds_executed": 3, "node_count": 60},
    }

    export_report = sanitize_report(report, public=False)
    assert len(export_report["agent_samples"]) == 25
    assert len(export_report["purchase_decisions"]) == 30
    assert "formatted_evidence" in export_report

    web_report = sanitize_web_report(report, public=False)
    assert len(web_report["agent_samples"]) == 12
    assert "neighbors" not in web_report["agent_samples"][0]
    assert "base_maut_scores" not in web_report["agent_samples"][0]
    assert "purchase_decisions" not in web_report
    assert "formatted_evidence" not in web_report
    assert "final_rag_evidence" not in web_report
    assert len(web_report["rag_evidence"]["market_query"]) == 20
    assert len(web_report["data_enrichment_candidates"]) == 20
    assert web_report["chart_data"]["overview_metrics"]["purchase_intent_index"] == 75
    assert web_report["social_simulation"]["node_count"] == 60
