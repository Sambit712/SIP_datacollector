"""Unit tests for relational database models, constraints, and relationships (Phase 1)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import (
    Base,
    RawRecord,
    IssueCategory,
    IssueCluster,
    ExtractedIssue,
    OpportunityScore,
    GoldenRecord,
    EvidenceAudit,
    compute_content_hash,
)
from src.models.schemas import RawRecordCreate, ExtractedIssueSchema


@pytest.fixture
def in_memory_session():
    """Provides a clean in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_create_raw_record(in_memory_session):
    """Verifies creating and querying a RawRecord instance."""
    raw_text = "Groww AutoPay failed on the 5th."
    record = RawRecord(
        id="test_rec_01",
        source_type="reddit",
        platform="Reddit",
        title="Test Title",
        raw_text=raw_text,
        sanitized_text=raw_text,
        content_hash=compute_content_hash(raw_text),
        relevance_status="highly_relevant",
    )
    in_memory_session.add(record)
    in_memory_session.commit()

    queried = in_memory_session.query(RawRecord).filter_by(id="test_rec_01").first()
    assert queried is not None
    assert queried.platform == "Reddit"
    assert queried.source_type == "reddit"
    assert queried.relevance_status == "highly_relevant"


def test_cascade_delete_raw_record(in_memory_session):
    """Verifies that deleting a RawRecord cascades and deletes associated ExtractedIssue and EvidenceAudit."""
    raw = RawRecord(
        id="parent_rec",
        source_type="app_store",
        platform="GooglePlay",
        raw_text="App crashed when opening SIP.",
        sanitized_text="App crashed when opening SIP.",
        content_hash=compute_content_hash("App crashed when opening SIP."),
    )
    in_memory_session.add(raw)
    in_memory_session.commit()

    issue = ExtractedIssue(
        id="child_issue",
        raw_record_id="parent_rec",
        core_problem="App crashes on SIP tab",
        verbatim_excerpt="App crashed when opening SIP.",
        journey_stage="active",
        mentions_groww=True,
    )
    audit = EvidenceAudit(
        id="child_audit",
        raw_record_id="parent_rec",
        extracted_issue_id="child_issue",
        exact_quote="App crashed when opening SIP.",
    )
    in_memory_session.add(issue)
    in_memory_session.add(audit)
    in_memory_session.commit()

    assert in_memory_session.query(ExtractedIssue).filter_by(id="child_issue").first() is not None
    assert in_memory_session.query(EvidenceAudit).filter_by(id="child_audit").first() is not None

    # Delete parent
    in_memory_session.delete(raw)
    in_memory_session.commit()

    assert in_memory_session.query(RawRecord).filter_by(id="parent_rec").first() is None
    assert in_memory_session.query(ExtractedIssue).filter_by(id="child_issue").first() is None
    assert in_memory_session.query(EvidenceAudit).filter_by(id="child_audit").first() is None


def test_cluster_and_opportunity_score_relationship(in_memory_session):
    """Verifies relationship between IssueCluster and OpportunityScore."""
    cat = IssueCategory(
        id="cat_test",
        code="test_code",
        name="Test Category",
        description="Testing category",
    )
    cluster = IssueCluster(
        id="cluster_01",
        category_id="cat_test",
        theme_title="Salary Date Mismatch",
        summary_description="Salary arriving after debit date",
        supporting_record_count=12,
        evidence_tier="strong",
    )
    score = OpportunityScore(
        id="score_01",
        cluster_id="cluster_01",
        frequency_score=0.8,
        severity_score=0.9,
        business_relevance_score=0.95,
        evidence_confidence_score=0.85,
        actionability_score=0.9,
        implementation_effort_score=0.3,
        composite_priority_score=0.88,
        score_rationale="High retention opportunity",
    )
    in_memory_session.add_all([cat, cluster, score])
    in_memory_session.commit()

    queried_cluster = in_memory_session.query(IssueCluster).filter_by(id="cluster_01").first()
    assert queried_cluster.opportunity_score is not None
    assert queried_cluster.opportunity_score.composite_priority_score == 0.88
    assert queried_cluster.category.code == "test_code"


def test_unique_content_hash_constraint(in_memory_session):
    """Verifies that duplicate content hashes raise integrity error."""
    from sqlalchemy.exc import IntegrityError

    r1 = RawRecord(
        id="rec_1",
        source_type="reddit",
        platform="Reddit",
        raw_text="Same text",
        sanitized_text="Same text",
        content_hash="hash_12345",
    )
    r2 = RawRecord(
        id="rec_2",
        source_type="reddit",
        platform="Reddit",
        raw_text="Same text",
        sanitized_text="Same text",
        content_hash="hash_12345",
    )
    in_memory_session.add(r1)
    in_memory_session.commit()

    in_memory_session.add(r2)
    with pytest.raises(IntegrityError):
        in_memory_session.commit()
    in_memory_session.rollback()

