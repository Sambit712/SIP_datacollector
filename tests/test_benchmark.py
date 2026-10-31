"""Unit & Integration tests for Golden Benchmark & Evaluation Engine (Phase 4)."""

import json
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.evaluation.benchmark_runner import BenchmarkRunner
from src.evaluation.iaa_evaluator import IAAEvaluator
from src.evaluation.calibrator import CalibrationStore
from src.models.database import Base, GoldenRecord, RawRecord, IssueCategory, EvaluationRun
from src.nlp.fallback_engine import FallbackEngine
from src.nlp.llm_client import GroqLLMClient


@pytest.fixture
def eval_session():
    """Provides a fully seeded in-memory SQLite session for evaluation testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Pre-seed taxonomy
    for cat in FallbackEngine.get_taxonomy():
        session.add(IssueCategory(
            id=cat["id"],
            code=cat["code"],
            name=cat["name"],
            description=cat["description"],
        ))

    # Add 5 representative golden records
    sample_records = [
        ("r1", "AutoPay failed due to salary delay by 2 days, bank charged ₹295.", "cat_01", "cash_flow_mismatch", "highly_relevant"),
        ("r2", "NPCI e-mandate registration was rejected by NetBanking with MD01 error.", "cat_04", "autopay_mandate", "highly_relevant"),
        ("r3", "My portfolio return is down -3% after 7 months, very disappointed.", "cat_06", "expectation_mismatch", "highly_relevant"),
        ("r4", "Market crashed 600 points today and portfolio is in red, severe anxiety.", "cat_07", "volatility_anxiety", "highly_relevant"),
        ("r5", "Selling mutual funds to buy Bitcoin and Solana on Binance exchange.", "cat_13", "unclassified", "not_relevant"),
    ]

    for rid, text, cid, ccode, rel in sample_records:
        raw = RawRecord(
            id=rid,
            source_type="reddit",
            platform="Reddit",
            raw_text=text,
            sanitized_text=text,
            content_hash=f"hash_{rid}",
            relevance_status=rel,
        )
        session.add(raw)
        golden = GoldenRecord(
            id=f"g_{rid}",
            raw_record_id=rid,
            expected_relevance=rel,
            expected_category_id=cid,
            expected_journey_stage="instalment_failed" if "failed" in text else "active",
            expected_first_hand=True,
            expected_sip_status="discontinued" if "disappointed" in text or "selling" in text else "active",
            expected_stated_reason=text,
            reviewer_notes="Ground truth note",
        )
        session.add(golden)

    session.commit()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Inter-Annotator Agreement Tests
# ---------------------------------------------------------------------------

class TestIAAEvaluator:
    def test_perfect_agreement(self):
        labels_a = ["cat_01", "cat_02", "cat_03", "cat_04"]
        labels_b = ["cat_01", "cat_02", "cat_03", "cat_04"]
        kappa, interp = IAAEvaluator.compute_cohens_kappa(labels_a, labels_b)
        assert kappa == 1.0
        assert interp == "Almost perfect agreement"

    def test_moderate_agreement(self):
        labels_a = ["cat_01", "cat_02", "cat_03", "cat_01", "cat_02"]
        labels_b = ["cat_01", "cat_02", "cat_04", "cat_01", "cat_03"]
        kappa, interp = IAAEvaluator.compute_cohens_kappa(labels_a, labels_b)
        assert 0.0 <= kappa <= 1.0

    def test_disagreement_resolution(self):
        records = [
            {"id": "1", "label_rater1": "cat_01", "label_rater2": "cat_01"},
            {"id": "2", "label_rater1": "cat_01", "label_rater2": "cat_02"},
        ]
        resolved = IAAEvaluator.resolve_disagreements(records)
        assert resolved[0]["has_disagreement"] is False
        assert resolved[1]["has_disagreement"] is True
        assert resolved[1]["arbitrated_label"] == "cat_01"


# ---------------------------------------------------------------------------
# Benchmark Runner Tests
# ---------------------------------------------------------------------------

class TestBenchmarkRunner:
    def test_benchmark_execution_and_metrics_deterministic(self, eval_session):
        start_time = time.time()
        # Test deterministic evaluation engine (instant, offline)
        offline_client = GroqLLMClient(api_key="")
        runner = BenchmarkRunner(session=eval_session, llm_client=offline_client)
        results = runner.run_evaluation(save_to_db=True)
        elapsed = time.time() - start_time

        # Acceptance Criterion: Executes in < 15 seconds
        assert elapsed < 15.0, f"Benchmark execution took {elapsed:.2f}s, expected < 15s"

        assert results["total_evaluated"] == 5
        assert 0.0 <= results["overall_accuracy"] <= 1.0
        assert 0.0 <= results["macro_f1"] <= 1.0
        assert 0.0 <= results["macro_precision"] <= 1.0
        assert 0.0 <= results["macro_recall"] <= 1.0
        assert results["unsupported_claims_count"] == 0

        # Verify 13x13 confusion matrix exists
        cm = results["confusion_matrix"]
        assert len(cm) == 13
        for row in cm.values():
            assert len(row) == 13

        # Verify database persistence of EvaluationRun
        run_record = eval_session.query(EvaluationRun).first()
        assert run_record is not None
        assert run_record.total_records_evaluated == 5
        assert run_record.accuracy == results["overall_accuracy"]


# ---------------------------------------------------------------------------
# Calibration Store Tests
# ---------------------------------------------------------------------------

class TestCalibrationStore:
    def test_submit_correction(self, eval_session):
        golden_rec = eval_session.query(GoldenRecord).first()
        old_cat = golden_rec.expected_category_id
        target_cat = "cat_03" if old_cat != "cat_03" else "cat_04"

        updated = CalibrationStore.submit_correction(
            session=eval_session,
            golden_record_id=golden_rec.id,
            new_expected_category_id=target_cat,
            reviewer_notes="Re-classified after deeper PM review.",
            annotator_id="lead_pm_annotator",
        )
        assert updated.expected_category_id == target_cat
        assert "lead_pm_annotator" in updated.reviewer_notes

    def test_compute_before_after_delta(self):
        prev = {
            "overall_accuracy": 0.76,
            "macro_f1": 0.72,
            "relevance_accuracy": 0.85,
            "misclassifications": [{"raw_record_id": "r1"}, {"raw_record_id": "r2"}],
        }
        curr = {
            "overall_accuracy": 0.88,
            "macro_f1": 0.85,
            "relevance_accuracy": 0.95,
            "misclassifications": [{"raw_record_id": "r1"}],  # r2 resolved
        }

        delta = CalibrationStore.compute_before_after_delta(prev, curr)
        assert delta["delta_accuracy"] == 0.12
        assert delta["delta_macro_f1"] == 0.13
        assert delta["resolved_count"] == 1
        assert "r2" in delta["resolved_record_ids"]
        assert "76.0% -> 88.0%" in delta["summary"]
