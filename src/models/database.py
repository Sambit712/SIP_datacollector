"""SQLAlchemy ORM Database Models & Session Management.

Defines the relational schema for the AI Discovery Engine:
- RawRecord: Ingested text and metadata from 5 channels
- IssueCategory: Canonical 13 categories + emergent themes
- IssueCluster: Semantic problem clusters & centroids
- ExtractedIssue: Schema-validated entity and problem extractions
- OpportunityScore: 6-dimensional weighted prioritization scores
- GoldenRecord: Hand-labelled ground truth benchmark dataset
- EvaluationRun: Historical evaluation snapshots and confusion matrices
- EvidenceAudit: Immutable verification log and audit trail
"""

from datetime import datetime, timezone
import hashlib
from typing import Generator
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    relationship,
    sessionmaker,
)

from config.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""
    pass


def generate_uuid() -> str:
    """Generates a standard 36-character UUID string."""
    return str(uuid.uuid4())


def compute_content_hash(text: str) -> str:
    """Computes a SHA-256 fingerprint on text for deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class RawRecord(Base):
    """Raw ingested records collected across all 5 research channels."""

    __tablename__ = "raw_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_type = Column(String(50), nullable=False, index=True)  # reddit, app_store, official_doc, news, interview
    source_url = Column(String(500), nullable=True)
    platform = Column(String(50), nullable=False, index=True)  # Groww, GooglePlay, AppStore, Reddit, SEBI, AMFI
    title = Column(String(300), nullable=True)
    raw_text = Column(Text, nullable=False)
    sanitized_text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    rating = Column(Integer, nullable=True)  # 1-5 for app store reviews
    publication_date = Column(String(50), nullable=True)
    ingestion_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    relevance_status = Column(String(30), default="unanalyzed", nullable=False, index=True)  # highly_relevant, partially_relevant, not_relevant, unanalyzed
    is_user_verified = Column(Boolean, default=False, nullable=False)
    is_synthetic_demo = Column(Boolean, default=False, nullable=False)

    # Relationships
    extracted_issues = relationship("ExtractedIssue", back_populates="raw_record", cascade="all, delete-orphan")
    golden_record = relationship("GoldenRecord", back_populates="raw_record", uselist=False, cascade="all, delete-orphan")
    evidence_audits = relationship("EvidenceAudit", back_populates="raw_record", cascade="all, delete-orphan")


class IssueCategory(Base):
    """Taxonomy of mutual fund SIP problem categories (13 default + emergent)."""

    __tablename__ = "issue_categories"

    id = Column(String(50), primary_key=True)  # e.g., cat_01
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    is_predefined = Column(Boolean, default=True, nullable=False)

    # Relationships
    extracted_issues = relationship("ExtractedIssue", back_populates="category")
    clusters = relationship("IssueCluster", back_populates="category")
    golden_records = relationship("GoldenRecord", back_populates="expected_category")


class IssueCluster(Base):
    """Semantic problem clusters grouping similar user friction points."""

    __tablename__ = "issue_clusters"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    category_id = Column(String(50), ForeignKey("issue_categories.id"), nullable=True, index=True)
    theme_title = Column(String(250), nullable=False)
    summary_description = Column(Text, nullable=False)
    primary_root_cause = Column(String(250), nullable=True)
    supporting_record_count = Column(Integer, default=0, nullable=False)
    evidence_tier = Column(String(30), default="moderate", nullable=False)  # strong, moderate, weak
    counter_evidence_notes = Column(Text, nullable=True)  # JSON or text notes on counter-evidence
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    category = relationship("IssueCategory", back_populates="clusters")
    extracted_issues = relationship("ExtractedIssue", back_populates="cluster")
    opportunity_score = relationship("OpportunityScore", back_populates="cluster", uselist=False, cascade="all, delete-orphan")


class ExtractedIssue(Base):
    """Schema-validated structured problem extractions from raw records."""

    __tablename__ = "extracted_issues"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    raw_record_id = Column(String(36), ForeignKey("raw_records.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(50), ForeignKey("issue_categories.id"), nullable=True, index=True)
    cluster_id = Column(String(36), ForeignKey("issue_clusters.id"), nullable=True, index=True)
    core_problem = Column(Text, nullable=False)
    verbatim_excerpt = Column(Text, nullable=False)
    journey_stage = Column(String(50), nullable=False, index=True)  # pre_sip, setup, active, instalment_failed, life_event, churned
    mentions_groww = Column(Boolean, default=False, nullable=False)
    is_first_hand_experience = Column(Boolean, default=True, nullable=False)
    sip_status = Column(String(30), default="unknown", nullable=False)  # active, paused, failed, discontinued, unknown
    stated_discontinuation_reason = Column(Text, nullable=True)
    severity_level = Column(String(20), default="medium", nullable=False)  # low, medium, high, critical
    epistemic_type = Column(String(30), default="observed_evidence", nullable=False)  # observed_evidence, interpretation, hypothesis
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    raw_record = relationship("RawRecord", back_populates="extracted_issues")
    category = relationship("IssueCategory", back_populates="extracted_issues")
    cluster = relationship("IssueCluster", back_populates="extracted_issues")
    evidence_audits = relationship("EvidenceAudit", back_populates="extracted_issue", cascade="all, delete-orphan")


class OpportunityScore(Base):
    """6-Dimensional prioritization scoring matrix for problem clusters."""

    __tablename__ = "opportunity_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cluster_id = Column(String(36), ForeignKey("issue_clusters.id", ondelete="CASCADE"), unique=True, nullable=False)
    frequency_score = Column(Float, nullable=False, default=0.0)
    severity_score = Column(Float, nullable=False, default=0.0)
    business_relevance_score = Column(Float, nullable=False, default=0.0)
    evidence_confidence_score = Column(Float, nullable=False, default=0.0)
    actionability_score = Column(Float, nullable=False, default=0.0)
    implementation_effort_score = Column(Float, nullable=False, default=0.0)
    composite_priority_score = Column(Float, nullable=False, default=0.0, index=True)
    score_rationale = Column(Text, nullable=True)
    pm_notes = Column(Text, nullable=True)
    last_calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    cluster = relationship("IssueCluster", back_populates="opportunity_score")


class GoldenRecord(Base):
    """Curated benchmark ground truth for evaluating AI extraction & classification."""

    __tablename__ = "golden_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    raw_record_id = Column(String(36), ForeignKey("raw_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    expected_relevance = Column(String(30), nullable=False)  # highly_relevant, partially_relevant, not_relevant
    expected_category_id = Column(String(50), ForeignKey("issue_categories.id"), nullable=False)
    expected_journey_stage = Column(String(50), nullable=False)
    expected_first_hand = Column(Boolean, default=True, nullable=False)
    expected_sip_status = Column(String(30), nullable=False)
    expected_stated_reason = Column(Text, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    annotator_id = Column(String(50), default="lead_pm_annotator", nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    raw_record = relationship("RawRecord", back_populates="golden_record")
    expected_category = relationship("IssueCategory", back_populates="golden_records")


class EvaluationRun(Base):
    """Audit log of AI performance evaluation runs against the Golden Dataset."""

    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    total_records_evaluated = Column(Integer, nullable=False)
    accuracy = Column(Float, nullable=False)
    macro_precision = Column(Float, nullable=False)
    macro_recall = Column(Float, nullable=False)
    macro_f1 = Column(Float, nullable=False)
    confusion_matrix_json = Column(Text, nullable=False)  # JSON representation of 13x13 confusion matrix
    misclassification_diffs = Column(Text, nullable=True)  # JSON list of diff objects
    model_used = Column(String(100), default="groq:llama-3.3-70b-versatile", nullable=False)


class EvidenceAudit(Base):
    """Immutable evidence audit trail linking claims to original excerpts & verification."""

    __tablename__ = "evidence_audits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    extracted_issue_id = Column(String(36), ForeignKey("extracted_issues.id", ondelete="CASCADE"), nullable=True, index=True)
    raw_record_id = Column(String(36), ForeignKey("raw_records.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url = Column(String(500), nullable=True)
    exact_quote = Column(Text, nullable=False)
    verification_status = Column(String(30), default="unverified", nullable=False, index=True)  # unverified, verified_accurate, corrected, rejected
    human_correction_note = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Relationships
    extracted_issue = relationship("ExtractedIssue", back_populates="evidence_audits")
    raw_record = relationship("RawRecord", back_populates="evidence_audits")


# ---------------------------------------------------------------------------
# Database Engine & Session Management
# ---------------------------------------------------------------------------

_engine = None
_session_factory = None


def get_engine():
    """Returns the global SQLAlchemy engine instance."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
            echo=False,
        )
    return _engine


def get_session_factory():
    """Returns the SQLAlchemy session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def get_session() -> Session:
    """Creates a new SQLAlchemy database session."""
    factory = get_session_factory()
    return factory()


def get_db() -> Generator[Session, None, None]:
    """Dependency helper yielding a managed database session."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Initializes the database schema by creating all registered tables."""
    settings = get_settings()
    settings.ensure_directories()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

