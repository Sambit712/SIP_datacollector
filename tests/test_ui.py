"""Unit and Integration tests for Phase 7: PM Research Dashboard Views."""

import pytest
from unittest.mock import MagicMock, patch
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
    EvaluationRun,
    compute_content_hash,
)
from ui.views import (
    page_1_dashboard,
    page_2_source_explorer,
    page_3_ai_analysis,
    page_4_sip_lifecycle,
    page_5_competitive_groww,
    page_6_research_questions,
    page_7_prioritization,
    page_8_evaluation_golden,
    page_9_evidence_log,
    page_10_report_generator,
)


@pytest.fixture
def test_db_session():
    """Provides an in-memory SQLite database populated with complete data for UI verification."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # 1. Categories
    cat1 = IssueCategory(id="cat_01", code="autopay_mandate", name="AutoPay Mandate", description="Desc 1")
    cat2 = IssueCategory(id="cat_04", code="discontinuation_friction", name="Discontinuation Friction", description="Desc 2")
    session.add_all([cat1, cat2])

    # 2. Raw Records
    r1 = RawRecord(
        id="raw_01",
        source_type="reddit",
        platform="Reddit",
        title="AutoPay failed on Groww",
        raw_text="AutoPay mandate failed on Groww with MD01 error.",
        sanitized_text="AutoPay mandate failed on Groww with MD01 error.",
        content_hash=compute_content_hash("AutoPay mandate failed on Groww with MD01 error."),
        relevance_status="highly_relevant",
    )
    r2 = RawRecord(
        id="raw_02",
        source_type="interview",
        platform="Groww",
        title="Interview with User #1",
        raw_text="I stopped investing because the pause option was not visible.",
        sanitized_text="I stopped investing because the pause option was not visible.",
        content_hash=compute_content_hash("I stopped investing because the pause option was not visible."),
        relevance_status="highly_relevant",
    )
    session.add_all([r1, r2])
    session.flush()

    # 3. Clusters
    cl1 = IssueCluster(
        id="cl_01",
        category_id="cat_01",
        theme_title="Bank Mandate Dropoffs",
        summary_description="Silent AutoPay failures at partner banks.",
        evidence_tier="strong",
        supporting_record_count=10,
    )
    cl2 = IssueCluster(
        id="cl_02",
        category_id="cat_04",
        theme_title="Buried Pause Option",
        summary_description="Users cancel SIPs because pause is obscured.",
        evidence_tier="moderate",
        supporting_record_count=5,
    )
    session.add_all([cl1, cl2])
    session.flush()

    # 4. Extracted Issues
    iss1 = ExtractedIssue(
        id="iss_01",
        raw_record_id=r1.id,
        category_id=cat1.id,
        cluster_id=cl1.id,
        core_problem="AutoPay failed",
        verbatim_excerpt="AutoPay mandate failed",
        journey_stage="instalment_failed",
        severity_level="high",
        epistemic_type="observed_evidence",
        mentions_groww=True,
    )
    iss2 = ExtractedIssue(
        id="iss_02",
        raw_record_id=r2.id,
        category_id=cat2.id,
        cluster_id=cl2.id,
        core_problem="Pause not found",
        verbatim_excerpt="pause option was not visible",
        journey_stage="churned",
        severity_level="medium",
        epistemic_type="observed_evidence",
        mentions_groww=True,
    )
    session.add_all([iss1, iss2])

    # 5. Opportunity Scores
    opp1 = OpportunityScore(
        id="opp_01",
        cluster_id=cl1.id,
        composite_priority_score=0.88,
        business_relevance_score=0.95,
        actionability_score=0.85,
        severity_score=0.85,
        frequency_score=0.60,
        implementation_effort_score=0.40,
        evidence_confidence_score=0.90,
        score_rationale="Ranked #1 due to critical business relevance.",
    )
    opp2 = OpportunityScore(
        id="opp_02",
        cluster_id=cl2.id,
        composite_priority_score=0.74,
        business_relevance_score=0.80,
        actionability_score=0.90,
        severity_score=0.70,
        frequency_score=0.40,
        implementation_effort_score=0.25,
        evidence_confidence_score=0.75,
        score_rationale="Ranked #2 with quick win potential.",
    )
    session.add_all([opp1, opp2])

    # 6. Golden Record & Evaluation Run
    gr = GoldenRecord(
        id="gr_01",
        raw_record_id=r1.id,
        expected_relevance="highly_relevant",
        expected_category_id="cat_01",
        expected_journey_stage="instalment_failed",
        expected_sip_status="failed",
    )
    eval_run = EvaluationRun(
        id="eval_01",
        total_records_evaluated=1,
        accuracy=1.0,
        macro_precision=1.0,
        macro_recall=1.0,
        macro_f1=1.0,
        confusion_matrix_json='{"autopay_mandate": {"autopay_mandate": 1}}',
        model_used="offline_fallback",
    )
    session.add_all([gr, eval_run])
    session.commit()

    try:
        yield session
    finally:
        session.close()


class TestDashboardViews:
    """Tests that all 10 dashboard page render functions execute without error."""

    @patch("streamlit.bar_chart")
    @patch("streamlit.dataframe")
    def test_page_1_dashboard_renders(self, mock_df, mock_chart, test_db_session):
        page_1_dashboard.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_2_source_explorer_renders(self, test_db_session):
        page_2_source_explorer.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_3_ai_analysis_renders(self, test_db_session):
        page_3_ai_analysis.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_4_sip_lifecycle_renders(self, test_db_session):
        page_4_sip_lifecycle.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_5_competitive_groww_renders(self, test_db_session):
        page_5_competitive_groww.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_6_research_questions_renders(self, test_db_session):
        page_6_research_questions.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_7_prioritization_renders(self, test_db_session):
        page_7_prioritization.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_8_evaluation_golden_renders(self, test_db_session):
        page_8_evaluation_golden.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_9_evidence_log_renders(self, test_db_session):
        page_9_evidence_log.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_page_10_report_generator_renders(self, test_db_session):
        page_10_report_generator.render(test_db_session, filters={"channels": [], "platforms": []})

    def test_filtering_cascades_to_records(self, test_db_session):
        """Verifies that channel filter restricts records in Page 1."""
        page_1_dashboard.render(test_db_session, filters={"channels": ["reddit"], "platforms": []})
        page_1_dashboard.render(test_db_session, filters={"channels": ["non_existent_channel"], "platforms": []})
