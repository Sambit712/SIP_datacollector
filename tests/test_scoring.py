"""Unit tests for Phase 5: Opportunity Prioritization & Damping Engine."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import (
    Base,
    IssueCategory,
    IssueCluster,
    ExtractedIssue,
    RawRecord,
    OpportunityScore,
    compute_content_hash,
)
from src.prioritization.dampener import FrequencyDampener
from src.prioritization.scorer import (
    OpportunityScorer,
    PrioritizationWeights,
    CATEGORY_HEURISTICS,
)
from src.prioritization.explainer import OpportunityExplainer


@pytest.fixture
def session():
    """Provides a fresh in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    sess = session_factory()
    try:
        yield sess
    finally:
        sess.close()


# ==============================================================================
# Frequency Dampener Tests
# ==============================================================================

class TestFrequencyDampener:
    """Tests logarithmic damping and anti-vocal-minority mathematical guarantees."""

    def test_anti_vocal_minority_reddit_vs_official(self):
        """Verifies that 100 Reddit rants alone do NOT outrank 1 official SEBI report."""
        dampener = FrequencyDampener(scale_factor=10.0)

        # 100 Reddit complaints, 0 interviews, no official report
        score_100_reddit = dampener.calculate_damped_frequency(
            n_reddit=100,
            n_interviews=0,
            has_official=False,
        )

        # 1 Official Regulatory finding, 0 Reddit, 0 interviews
        score_1_official = dampener.calculate_damped_frequency(
            n_reddit=0,
            n_interviews=0,
            has_official=True,
        )

        # 1 official (5.0 / 10 = 0.50) must beat 100 reddit (ln(101) / 10 = 0.4615)
        assert score_1_official > score_100_reddit
        assert score_1_official == 0.50
        assert score_100_reddit < 0.47

    def test_logarithmic_damping_curve(self):
        """Verifies diminishing returns as social media volume scales up."""
        dampener = FrequencyDampener(scale_factor=10.0)

        score_10 = dampener.calculate_damped_frequency(n_reddit=10)
        score_50 = dampener.calculate_damped_frequency(n_reddit=50)
        score_200 = dampener.calculate_damped_frequency(n_reddit=200)

        # Growth from 10 to 50 should be larger than 50 to 200 due to log compression
        delta_1 = score_50 - score_10
        delta_2 = score_200 - score_50
        assert delta_1 > delta_2

    def test_interview_weighting(self):
        """Verifies qualitative user interviews carry higher weight than raw forum mentions."""
        dampener = FrequencyDampener(scale_factor=10.0)

        score_3_interviews = dampener.calculate_damped_frequency(n_interviews=3)
        score_3_reddit = dampener.calculate_damped_frequency(n_reddit=3)

        assert score_3_interviews > score_3_reddit

    def test_boundary_clipping(self):
        """Verifies score is strictly bounded in [0.0, 1.0]."""
        dampener = FrequencyDampener(scale_factor=5.0)
        score = dampener.calculate_damped_frequency(
            n_reddit=500,
            n_interviews=20,
            has_official=True,
            n_app_store=500,
            n_news=100,
        )
        assert score == 1.0

        score_zero = dampener.calculate_damped_frequency(0, 0, False, 0, 0)
        assert score_zero == 0.0

    def test_calculate_for_cluster_traversal(self, session):
        """Verifies calculating frequency by traversing cluster -> issues -> raw records."""
        cluster = IssueCluster(
            id="cl_test_01",
            theme_title="Test Mandate Rejection",
            summary_description="Summary",
            evidence_tier="strong",
            supporting_record_count=2,
        )
        session.add(cluster)

        # Add 1 official doc record and 1 reddit record
        rec_official = RawRecord(
            id="raw_off_01",
            source_type="official_doc",
            platform="SEBI",
            raw_text="SEBI study on mutual fund persistency",
            sanitized_text="SEBI study on mutual fund persistency",
            content_hash=compute_content_hash("SEBI study on mutual fund persistency"),
        )
        rec_reddit = RawRecord(
            id="raw_red_01",
            source_type="reddit",
            platform="Reddit",
            raw_text="My Groww mandate failed",
            sanitized_text="My Groww mandate failed",
            content_hash=compute_content_hash("My Groww mandate failed"),
        )
        session.add_all([rec_official, rec_reddit])
        session.flush()

        issue_1 = ExtractedIssue(
            id="iss_01",
            raw_record_id=rec_official.id,
            cluster_id=cluster.id,
            core_problem="Mandate churn",
            verbatim_excerpt="SEBI study",
            journey_stage="instalment_failed",
        )
        issue_2 = ExtractedIssue(
            id="iss_02",
            raw_record_id=rec_reddit.id,
            cluster_id=cluster.id,
            core_problem="Groww mandate failure",
            verbatim_excerpt="mandate failed",
            journey_stage="setup",
        )
        session.add_all([issue_1, issue_2])
        session.commit()

        dampener = FrequencyDampener(scale_factor=10.0)
        score = dampener.calculate_for_cluster(cluster)
        # 1 official (5.0) + 1 reddit (ln(2)=0.693) => 5.693 / 10 = 0.5693
        assert score == pytest.approx(0.5693, abs=0.01)


# ==============================================================================
# Prioritization Weights Tests
# ==============================================================================

class TestPrioritizationWeights:
    """Tests weight normalization and dynamic reconfiguration."""

    def test_default_weights_sum_to_one(self):
        """Default weights must sum exactly to 1.0."""
        w = PrioritizationWeights()
        total = (
            w.business_relevance
            + w.severity
            + w.actionability
            + w.evidence_confidence
            + w.frequency
            + w.implementation_effort
        )
        assert pytest.approx(total, 1e-5) == 1.0

    def test_custom_weight_normalization(self):
        """Custom unnormalized weights must be scaled proportionally to sum to 1.0."""
        w = PrioritizationWeights(
            business_relevance=50.0,
            severity=50.0,
            actionability=0.0,
            evidence_confidence=0.0,
            frequency=0.0,
            implementation_effort=0.0,
        )
        norm_w = w.normalized()
        assert norm_w.business_relevance == 0.5
        assert norm_w.severity == 0.5
        assert norm_w.actionability == 0.0

    def test_all_zero_weights_fallback(self):
        """If all weights are set to 0, it falls back to equal weighting."""
        w = PrioritizationWeights(
            business_relevance=0.0,
            severity=0.0,
            actionability=0.0,
            evidence_confidence=0.0,
            frequency=0.0,
            implementation_effort=0.0,
        )
        norm_w = w.normalized()
        assert pytest.approx(norm_w.business_relevance, 1e-4) == 1.0 / 6.0


# ==============================================================================
# Opportunity Scorer Tests
# ==============================================================================

class TestOpportunityScorer:
    """Tests composite mathematical formula, ranking, and database persistence."""

    def test_min_max_normalize(self):
        """Verifies min-max scaling across arrays."""
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        norm = OpportunityScorer.min_max_normalize(vals)
        assert norm == [0.0, 0.25, 0.5, 0.75, 1.0]

        # Uniform array
        uniform = OpportunityScorer.min_max_normalize([5.0, 5.0, 5.0])
        assert uniform == [0.5, 0.5, 0.5]

    def test_composite_score_math(self):
        """Tests manual calculation against the 6-dimensional formula."""
        scorer = OpportunityScorer()
        weights = PrioritizationWeights(
            business_relevance=0.25,
            severity=0.20,
            actionability=0.20,
            evidence_confidence=0.15,
            frequency=0.10,
            implementation_effort=0.10,
        )

        # Low effort (0.20) should yield (1 - 0.20) = 0.80 contribution
        dims = {
            "business_relevance": 1.0,  # 0.25 * 1.0 = 0.25
            "severity": 1.0,            # 0.20 * 1.0 = 0.20
            "actionability": 1.0,       # 0.20 * 1.0 = 0.20
            "evidence_confidence": 1.0, # 0.15 * 1.0 = 0.15
            "frequency": 1.0,           # 0.10 * 1.0 = 0.10
            "implementation_effort": 0.20, # 0.10 * (1.0 - 0.20) = 0.08
        }
        score = scorer.compute_composite_score(dims, weights)
        # Expected: 0.25 + 0.20 + 0.20 + 0.15 + 0.10 + 0.08 = 0.98
        assert score == 0.98

    def test_high_effort_penalty(self):
        """High implementation effort should reduce the composite priority score."""
        scorer = OpportunityScorer()
        weights = PrioritizationWeights()

        dims_low_effort = {
            "business_relevance": 0.8,
            "severity": 0.8,
            "actionability": 0.8,
            "evidence_confidence": 0.8,
            "frequency": 0.5,
            "implementation_effort": 0.2,  # easy
        }
        dims_high_effort = dict(dims_low_effort)
        dims_high_effort["implementation_effort"] = 0.9  # hard

        score_easy = scorer.compute_composite_score(dims_low_effort, weights)
        score_hard = scorer.compute_composite_score(dims_high_effort, weights)

        assert score_easy > score_hard

    def test_rank_shift_on_weight_change(self):
        """Verifies changing PM weights alters the relative ranking of opportunities."""
        scorer = OpportunityScorer()

        # Opportunity A: High Business Impact, High Effort (Hard Long-term Bet)
        dims_a = {
            "business_relevance": 0.95,
            "severity": 0.85,
            "actionability": 0.70,
            "evidence_confidence": 0.80,
            "frequency": 0.50,
            "implementation_effort": 0.90,  # very difficult
        }

        # Opportunity B: Moderate Impact, Very Low Effort (Quick Win)
        dims_b = {
            "business_relevance": 0.70,
            "severity": 0.60,
            "actionability": 0.85,
            "evidence_confidence": 0.70,
            "frequency": 0.50,
            "implementation_effort": 0.10,  # quick win
        }

        # Under default weights (business impact prioritized)
        default_weights = PrioritizationWeights()
        score_a_default = scorer.compute_composite_score(dims_a, default_weights)
        score_b_default = scorer.compute_composite_score(dims_b, default_weights)
        assert score_a_default > score_b_default

        # Under Quick-Win weights (effort is weighted heavily at 40%)
        quick_win_weights = PrioritizationWeights(
            business_relevance=0.10,
            severity=0.10,
            actionability=0.20,
            evidence_confidence=0.10,
            frequency=0.10,
            implementation_effort=0.40,
        )
        score_a_qw = scorer.compute_composite_score(dims_a, quick_win_weights)
        score_b_qw = scorer.compute_composite_score(dims_b, quick_win_weights)
        # Opportunity B should now outrank Opportunity A
        assert score_b_qw > score_a_qw

    def test_full_database_scoring_and_persistence(self, session):
        """Verifies scoring multiple clusters, ranking them, and persisting to SQLite."""
        # Create 2 categories
        cat1 = IssueCategory(id="cat_01", code="autopay_mandate", name="AutoPay Mandate", description="Desc")
        cat2 = IssueCategory(id="cat_08", code="ui_ux_complexity", name="UI/UX Friction", description="Desc")
        session.add_all([cat1, cat2])

        # Create 2 clusters
        cl1 = IssueCluster(
            id="cl_01",
            category_id="cat_01",
            theme_title="Bank Mandate AutoPay Dropoffs",
            summary_description="Mandates fail silently at partner banks.",
            evidence_tier="strong",
            supporting_record_count=15,
        )
        cl2 = IssueCluster(
            id="cl_02",
            category_id="cat_08",
            theme_title="Confusing Portfolio Charts",
            summary_description="XIRR vs absolute return display confuses users.",
            evidence_tier="weak",
            supporting_record_count=3,
        )
        session.add_all([cl1, cl2])
        session.commit()

        scorer = OpportunityScorer()
        results = scorer.score_all_clusters(session, persist=True)

        assert len(results) == 2
        top_cluster, top_score = results[0]
        # cat_01 (mandate) should rank #1 over cat_08 (ui friction)
        assert top_cluster.id == "cl_01"
        assert top_score.composite_priority_score > results[1][1].composite_priority_score

        # Check persistence in database
        db_scores = session.query(OpportunityScore).all()
        assert len(db_scores) == 2
        score_record = session.query(OpportunityScore).filter_by(cluster_id="cl_01").first()
        assert score_record is not None
        assert score_record.composite_priority_score == top_score.composite_priority_score
        assert len(score_record.score_rationale) > 20
        assert "Ranked #1" in score_record.score_rationale


# ==============================================================================
# Opportunity Explainer Tests
# ==============================================================================

class TestOpportunityExplainer:
    """Tests plain-language PM rationale generation and UI card summaries."""

    def test_generate_rationale(self):
        """Verifies that generated rationale contains key drivers, ranks, and citations."""
        score = OpportunityScore(
            composite_priority_score=0.88,
            business_relevance_score=0.95,
            severity_score=0.85,
            actionability_score=0.90,
            evidence_confidence_score=0.90,
            frequency_score=0.65,
            implementation_effort_score=0.30,
        )
        cluster = IssueCluster(
            theme_title="Bank AutoPay Failures",
            evidence_tier="strong",
        )

        rationale = OpportunityExplainer.generate_rationale(
            score=score,
            cluster=cluster,
            rank=1,
            total_clusters=5,
            source_counts={"official_doc": 2, "interview": 3, "reddit": 25},
        )

        assert "Ranked #1 of 5" in rationale
        assert "critical business relevance" in rationale
        assert "high Groww product actionability" in rationale
        assert "official regulatory data (2 doc(s))" in rationale
        assert "Favorable ROI with low implementation effort" in rationale

    def test_generate_card_summary(self):
        """Verifies UI card summary tags."""
        score = OpportunityScore(
            composite_priority_score=0.82,
            business_relevance_score=0.90,
            severity_score=0.80,
            actionability_score=0.85,
            evidence_confidence_score=0.80,
            frequency_score=0.50,
            implementation_effort_score=0.25,
        )
        cluster = IssueCluster(theme_title="AutoPay Drop")

        card = OpportunityExplainer.generate_card_summary(score, cluster, rank=1)
        assert card["rank"] == 1
        assert card["priority_tier"] == "Critical"
        assert card["quick_win"] is True
        assert len(card["positives"]) >= 3

