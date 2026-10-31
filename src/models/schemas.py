"""Pydantic Validation Schemas for Ingestion, AI Processing & Presentation.

Provides data integrity validation, type safety, and serialization between
the storage layer, Groq LLM pipelines, and the PM Dashboard UI.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums / Literal Type Definitions
# ---------------------------------------------------------------------------

SourceTypeLiteral = Literal["reddit", "app_store", "official_doc", "news", "interview"]
PlatformLiteral = Literal["Groww", "GooglePlay", "AppStore", "Reddit", "SEBI", "AMFI", "News", "Interview"]
RelevanceStatusLiteral = Literal["highly_relevant", "partially_relevant", "not_relevant", "unanalyzed"]
JourneyStageLiteral = Literal["pre_sip", "setup", "active", "instalment_failed", "life_event", "churned"]
SipStatusLiteral = Literal["active", "paused", "failed", "discontinued", "unknown"]
SeverityLiteral = Literal["low", "medium", "high", "critical"]
EpistemicLiteral = Literal["observed_evidence", "interpretation", "hypothesis"]
EvidenceTierLiteral = Literal["strong", "moderate", "weak"]
VerificationStatusLiteral = Literal["unverified", "verified_accurate", "corrected", "rejected"]


# ---------------------------------------------------------------------------
# Raw Record Schemas
# ---------------------------------------------------------------------------

class RawRecordBase(BaseModel):
    source_type: SourceTypeLiteral
    source_url: Optional[str] = None
    platform: str
    title: Optional[str] = None
    raw_text: str
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    publication_date: Optional[str] = None
    relevance_status: RelevanceStatusLiteral = "unanalyzed"
    is_user_verified: bool = False
    is_synthetic_demo: bool = False


class RawRecordCreate(RawRecordBase):
    pass


class RawRecordRead(RawRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sanitized_text: str
    content_hash: str
    ingestion_timestamp: datetime


# ---------------------------------------------------------------------------
# Issue Category Schemas
# ---------------------------------------------------------------------------

class IssueCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str
    is_predefined: bool = True


# ---------------------------------------------------------------------------
# Extracted Issue Schemas (Used by Groq LLM JSON output & DB)
# ---------------------------------------------------------------------------

class ExtractedIssueSchema(BaseModel):
    """Schema enforced on LLM extraction responses."""
    core_problem: str = Field(description="Clear, single-sentence summary of the user problem")
    verbatim_excerpt: str = Field(description="Exact snippet from source text corroborating the issue")
    journey_stage: JourneyStageLiteral = Field(description="Point in investment lifecycle where problem occurs")
    mentions_groww: bool = Field(default=False, description="Whether Groww is explicitly referenced")
    is_first_hand_experience: bool = Field(default=True, description="True if lived experience, False if hypothetical")
    sip_status: SipStatusLiteral = Field(default="unknown", description="Active state of user's SIP")
    stated_discontinuation_reason: Optional[str] = Field(default=None, description="Explicit stated reason for quitting")
    severity_level: SeverityLiteral = Field(default="medium", description="Severity of reported obstacle")
    epistemic_type: EpistemicLiteral = Field(default="observed_evidence", description="Knowledge boundary")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    suggested_category_code: Optional[str] = Field(default=None, description="Taxonomy category code")


class ExtractedIssueRead(ExtractedIssueSchema):
    model_config = ConfigDict(from_attributes=True)

    id: str
    raw_record_id: str
    category_id: Optional[str] = None
    cluster_id: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Issue Cluster Schemas
# ---------------------------------------------------------------------------

class IssueClusterBase(BaseModel):
    category_id: Optional[str] = None
    theme_title: str
    summary_description: str
    primary_root_cause: Optional[str] = None
    supporting_record_count: int = 0
    evidence_tier: EvidenceTierLiteral = "moderate"
    counter_evidence_notes: Optional[str] = None


class IssueClusterRead(IssueClusterBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Opportunity Score Schemas
# ---------------------------------------------------------------------------

class OpportunityScoreBase(BaseModel):
    cluster_id: str
    frequency_score: float = Field(ge=0.0, le=1.0)
    severity_score: float = Field(ge=0.0, le=1.0)
    business_relevance_score: float = Field(ge=0.0, le=1.0)
    evidence_confidence_score: float = Field(ge=0.0, le=1.0)
    actionability_score: float = Field(ge=0.0, le=1.0)
    implementation_effort_score: float = Field(ge=0.0, le=1.0)
    composite_priority_score: float = Field(ge=0.0, le=1.0)
    score_rationale: Optional[str] = None
    pm_notes: Optional[str] = None


class OpportunityScoreUpdate(BaseModel):
    pm_notes: Optional[str] = None
    frequency_score: Optional[float] = None
    severity_score: Optional[float] = None
    business_relevance_score: Optional[float] = None
    evidence_confidence_score: Optional[float] = None
    actionability_score: Optional[float] = None
    implementation_effort_score: Optional[float] = None


class OpportunityScoreRead(OpportunityScoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    last_calculated_at: datetime


# ---------------------------------------------------------------------------
# Golden Record Benchmark Schemas
# ---------------------------------------------------------------------------

class GoldenRecordBase(BaseModel):
    raw_record_id: str
    expected_relevance: RelevanceStatusLiteral
    expected_category_id: str
    expected_journey_stage: JourneyStageLiteral
    expected_first_hand: bool = True
    expected_sip_status: SipStatusLiteral
    expected_stated_reason: Optional[str] = None
    reviewer_notes: Optional[str] = None
    annotator_id: Optional[str] = "lead_pm_annotator"


class GoldenRecordCreate(GoldenRecordBase):
    pass


class GoldenRecordRead(GoldenRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Evaluation Run Schemas
# ---------------------------------------------------------------------------

class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    executed_at: datetime
    total_records_evaluated: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    confusion_matrix_json: str
    misclassification_diffs: Optional[str] = None
    model_used: str


# ---------------------------------------------------------------------------
# Evidence Audit Schemas
# ---------------------------------------------------------------------------

class EvidenceAuditBase(BaseModel):
    extracted_issue_id: Optional[str] = None
    raw_record_id: str
    source_url: Optional[str] = None
    exact_quote: str
    verification_status: VerificationStatusLiteral = "unverified"
    human_correction_note: Optional[str] = None


class EvidenceAuditUpdate(BaseModel):
    verification_status: VerificationStatusLiteral
    human_correction_note: Optional[str] = None


class EvidenceAuditRead(EvidenceAuditBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    verified_at: Optional[datetime] = None
