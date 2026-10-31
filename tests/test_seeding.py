"""Unit & Integration tests for database seeding and Golden Dataset (Phase 1)."""

import json
from pathlib import Path
import pytest

from config.settings import get_settings
from data.seed_data import seed_all
from src.models.database import (
    GoldenRecord,
    IssueCategory,
    RawRecord,
    get_session,
    init_db,
)


@pytest.fixture(scope="module")
def seeded_db():
    """Initializes and seeds the database once for this test module."""
    init_db()
    seed_all()
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def test_seed_categories_count(seeded_db):
    """Verifies that exactly 13 canonical categories are seeded."""
    categories = seeded_db.query(IssueCategory).all()
    assert len(categories) == 13
    codes = {c.code for c in categories}
    assert "cash_flow_mismatch" in codes
    assert "autopay_mandate" in codes
    assert "payment_failures" in codes
    assert "volatility_anxiety" in codes
    assert "unclassified" in codes


def test_seed_records_sources_distribution(seeded_db):
    """Verifies that 53 demonstration records exist across all 5 research channels."""
    records = seeded_db.query(RawRecord).all()
    assert len(records) >= 50, f"Expected at least 50 demo records, found {len(records)}"

    sources = {r.source_type for r in records}
    expected_sources = {"reddit", "app_store", "official_doc", "news", "interview"}
    assert sources == expected_sources, f"Missing source types. Expected {expected_sources}, found {sources}"

    # Verify counts per channel
    reddit_count = seeded_db.query(RawRecord).filter_by(source_type="reddit").count()
    app_store_count = seeded_db.query(RawRecord).filter_by(source_type="app_store").count()
    doc_count = seeded_db.query(RawRecord).filter_by(source_type="official_doc").count()
    news_count = seeded_db.query(RawRecord).filter_by(source_type="news").count()
    interview_count = seeded_db.query(RawRecord).filter_by(source_type="interview").count()

    assert reddit_count == 15
    assert app_store_count == 15
    assert doc_count == 8
    assert news_count == 5
    assert interview_count == 10


def test_app_store_review_sentiment_balance(seeded_db):
    """Verifies that App Store reviews contain both negative (1-2 star) and positive (4-5 star) reviews to prevent bias."""
    low_ratings = seeded_db.query(RawRecord).filter(
        RawRecord.source_type == "app_store",
        RawRecord.rating <= 2
    ).count()

    high_ratings = seeded_db.query(RawRecord).filter(
        RawRecord.source_type == "app_store",
        RawRecord.rating >= 4
    ).count()

    assert low_ratings > 0, "Must have negative reviews representing friction"
    assert high_ratings > 0, "Must have positive reviews to prevent negativity bias"


def test_synthetic_vs_real_evidence_markers(seeded_db):
    """Verifies that regulatory and official reports are flagged as is_synthetic_demo = False, while simulated posts are True."""
    official_records = seeded_db.query(RawRecord).filter_by(source_type="official_doc").all()
    for rec in official_records:
        assert rec.is_synthetic_demo is False, f"Official doc {rec.id} must be marked is_synthetic_demo=False"

    reddit_records = seeded_db.query(RawRecord).filter_by(source_type="reddit").all()
    for rec in reddit_records:
        assert rec.is_synthetic_demo is True, f"Simulated reddit post {rec.id} must be marked is_synthetic_demo=True"


def test_golden_benchmark_dataset_integrity(seeded_db):
    """Verifies that the Golden Benchmark set has exactly 25 records with valid FK relationships."""
    golden_records = seeded_db.query(GoldenRecord).all()
    assert len(golden_records) == 25

    for g in golden_records:
        assert g.raw_record is not None, f"Golden record {g.id} must link to a valid RawRecord"
        assert g.expected_category is not None, f"Golden record {g.id} must link to a valid IssueCategory"
        assert g.expected_relevance in ["highly_relevant", "partially_relevant", "not_relevant"]
        assert g.expected_journey_stage in ["pre_sip", "setup", "active", "instalment_failed", "life_event", "churned"]
        assert g.expected_sip_status in ["active", "paused", "failed", "discontinued", "unknown"]


def test_golden_benchmark_json_export():
    """Verifies that data/golden/benchmark_25.json was exported with 25 records."""
    settings = get_settings()
    json_path = settings.DATA_DIR / "golden" / "benchmark_25.json"
    assert json_path.exists(), "benchmark_25.json must exist on disk"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 25
    first_record = data[0]
    assert "raw_record_id" in first_record
    assert "expected_category_id" in first_record
    assert "expected_relevance" in first_record
    assert "raw_text" in first_record


def test_idempotent_seeding():
    """Verifies that running seed_all multiple times does not add duplicate records."""
    result = seed_all()
    assert result["categories"] == 0
    assert result["records"] == 0
    assert result["golden_benchmarks"] == 0

