"""Unit & Integration tests for AI Intelligence & NLP Pipeline (Phase 3)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, RawRecord, IssueCategory, ExtractedIssue, IssueCluster, EvidenceAudit
from src.models.schemas import ExtractedIssueSchema
from src.nlp.llm_client import GroqLLMClient, GroqOfflineError
from src.nlp.fallback_engine import FallbackEngine
from src.nlp.relevance_filter import RelevanceFilter
from src.nlp.extractor import ComplaintExtractor
from src.nlp.classifier import TaxonomyClassifier
from src.nlp.clusterer import IssueClusterer
from src.nlp.triangulator import EpistemicTriangulator
from src.nlp.pipeline import AnalysisPipeline


@pytest.fixture
def test_session():
    """Provides an isolated in-memory database session."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        # Pre-seed taxonomy
        for cat in FallbackEngine.get_taxonomy():
            session.add(IssueCategory(
                id=cat["id"],
                code=cat["code"],
                name=cat["name"],
                description=cat["description"],
            ))
        session.commit()
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Groq LLM Client Tests
# ---------------------------------------------------------------------------

class TestGroqLLMClient:
    def test_offline_mode_behavior(self):
        client = GroqLLMClient(api_key="")
        assert client.is_available is False
        with pytest.raises(GroqOfflineError):
            client.generate_chat_completion([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# Fallback Engine Tests
# ---------------------------------------------------------------------------

class TestFallbackEngine:
    def test_relevance_classification_positive(self):
        text = "My Groww SIP failed on the 5th because salary arrived late. Bank charged ₹295 penalty."
        status, conf, reason = FallbackEngine.classify_relevance(text)
        assert status == "highly_relevant"
        assert conf >= 0.8

    def test_relevance_classification_crypto_exclusion(self):
        text = "Sold all assets and bought Bitcoin and Solana on Binance for 10x returns."
        status, conf, reason = FallbackEngine.classify_relevance(text)
        assert status == "not_relevant"

    def test_relevance_classification_intraday_exclusion(self):
        text = "Looking for intraday Nifty call options breakout setups with 5x margin."
        status, conf, reason = FallbackEngine.classify_relevance(text)
        assert status == "not_relevant"

    def test_extract_issue_and_substring_guarantee(self):
        text = "Every month my SIP is scheduled for 5th. AutoPay debit failed and HDFC charged me ₹295 bounce charge! I cancelled my SIP."
        issue = FallbackEngine.extract_issue(text, platform="Groww")
        assert isinstance(issue, ExtractedIssueSchema)
        assert issue.mentions_groww is True
        assert issue.sip_status == "discontinued"
        assert issue.journey_stage == "instalment_failed"
        assert issue.severity_level == "critical"

        # Character-exact substring verification
        assert issue.verbatim_excerpt in text, f"verbatim_excerpt '{issue.verbatim_excerpt}' must be an exact substring of raw text"

    def test_taxonomy_keyword_classification(self):
        code1, _ = FallbackEngine.classify_category("Salary was late so bank account had insufficient funds on debit date.")
        assert code1 == "cash_flow_mismatch"

        code2, _ = FallbackEngine.classify_category("Mandate was rejected by NPCI with error code MD01.")
        assert code2 == "autopay_mandate"

        code3, _ = FallbackEngine.classify_category("Market crashed 500 points and my portfolio is deep in the red.")
        assert code3 == "volatility_anxiety"

    def test_cluster_issues_offline(self):
        issues = [
            {"id": "1", "core_problem": "Salary late debit failed", "verbatim_excerpt": "Salary late", "suggested_category_code": "cash_flow_mismatch"},
            {"id": "2", "core_problem": "Salary credited on 7th instead of 1st", "verbatim_excerpt": "Salary credited on 7th", "suggested_category_code": "cash_flow_mismatch"},
            {"id": "3", "core_problem": "Mandate rejected by bank", "verbatim_excerpt": "Mandate rejected", "suggested_category_code": "autopay_mandate"},
        ]
        clusters = FallbackEngine.cluster_issues_offline(issues, n_clusters=2)
        assert len(clusters) == 2
        for c in clusters:
            assert "theme_title" in c
            assert c["supporting_record_count"] >= 1
            assert c["evidence_tier"] in ["strong", "moderate", "weak"]


# ---------------------------------------------------------------------------
# Extractor Substring Guarantee Tests
# ---------------------------------------------------------------------------

class TestComplaintExtractor:
    def test_extractor_verbatim_substring_integrity(self):
        extractor = ComplaintExtractor()
        raw = "I started an SIP on Groww. In month 3, my salary arrived 2 days late so the AutoPay bounced. The bank charged ₹295 penalty. I decided to stop investing."
        issue = extractor.extract_issue(raw, platform="Groww")
        assert issue.verbatim_excerpt in raw
        assert issue.mentions_groww is True
        assert issue.sip_status == "discontinued"


# ---------------------------------------------------------------------------
# Taxonomy Classifier Tests
# ---------------------------------------------------------------------------

class TestTaxonomyClassifier:
    def test_classifier_maps_to_canonical_ids(self):
        classifier = TaxonomyClassifier()
        cat_id, code, conf, is_emergent = classifier.classify("AutoPay mandate rejected repeatedly with MD01 error.")
        assert cat_id == "cat_04"
        assert code == "autopay_mandate"
        assert conf > 0.6
        assert is_emergent is False


# ---------------------------------------------------------------------------
# Epistemic Triangulator Tests
# ---------------------------------------------------------------------------

class TestEpistemicTriangulator:
    def test_observed_evidence_classification(self):
        claim = "HDFC bank debited ₹295 ECS bounce fee from my account on Friday."
        ep_type, note = EpistemicTriangulator.classify_claim(claim, is_first_hand=True)
        assert ep_type == "observed_evidence"

    def test_interpretation_classification(self):
        claim = "The failure was likely due to a timing mismatch between corporate payroll and the NPCI debit cycle."
        ep_type, note = EpistemicTriangulator.classify_claim(claim)
        assert ep_type == "interpretation"

    def test_hypothesis_classification(self):
        claim = "If Groww introduces a dynamic 3-day buffer reminder, it would reduce user drop-offs."
        ep_type, note = EpistemicTriangulator.classify_claim(claim)
        assert ep_type == "hypothesis"


# ---------------------------------------------------------------------------
# Semantic Clusterer Tests
# ---------------------------------------------------------------------------

class TestIssueClusterer:
    def test_cluster_issues_multi_member(self):
        clusterer = IssueClusterer()
        issues = [
            {"id": "i1", "core_problem": "Delayed salary credit", "verbatim_excerpt": "Salary delayed", "category_id": "cat_01"},
            {"id": "i2", "core_problem": "Debit date before salary", "verbatim_excerpt": "Debit before salary", "category_id": "cat_01"},
            {"id": "i3", "core_problem": "Mandate OTP failed", "verbatim_excerpt": "OTP failed", "category_id": "cat_04"},
            {"id": "i4", "core_problem": "Mandate verification timeout", "verbatim_excerpt": "Verification timeout", "category_id": "cat_04"},
        ]
        clusters = clusterer.cluster_issues(issues)
        assert len(clusters) >= 2
        for cl in clusters:
            assert cl["supporting_record_count"] >= 1
            assert cl["evidence_tier"] in ["strong", "moderate", "weak"]
            assert len(cl["summary_description"]) > 10


# ---------------------------------------------------------------------------
# End-to-End Pipeline Execution Tests
# ---------------------------------------------------------------------------

class TestAnalysisPipeline:
    def test_process_record_end_to_end(self, test_session):
        pipeline = AnalysisPipeline()

        record = RawRecord(
            id="pipe_test_rec",
            source_type="reddit",
            platform="Reddit",
            title="Groww AutoPay failed",
            raw_text="My Groww AutoPay failed on 5th. Bank charged ₹295 penalty. I stopped my SIP.",
            sanitized_text="My Groww AutoPay failed on 5th. Bank charged ₹295 penalty. I stopped my SIP.",
            content_hash="pipe_hash_1",
            relevance_status="unanalyzed",
        )
        test_session.add(record)
        test_session.commit()

        # Execute pipeline
        issue = pipeline.process_record(test_session, record)
        assert issue is not None
        assert issue.core_problem is not None
        assert issue.verbatim_excerpt in record.sanitized_text
        assert issue.category_id is not None
        assert issue.epistemic_type == "observed_evidence"

        # Verify EvidenceAudit log created
        audit = test_session.query(EvidenceAudit).filter_by(raw_record_id=record.id).first()
        assert audit is not None
        assert audit.exact_quote == issue.verbatim_excerpt
        assert audit.verification_status == "verified_accurate"

    def test_process_excluded_record(self, test_session):
        pipeline = AnalysisPipeline()

        record = RawRecord(
            id="crypto_test_rec",
            source_type="reddit",
            platform="Reddit",
            title="Crypto gains",
            raw_text="Sold all mutual funds to buy Bitcoin and Ethereum on Binance.",
            sanitized_text="Sold all mutual funds to buy Bitcoin and Ethereum on Binance.",
            content_hash="crypto_hash_1",
            relevance_status="unanalyzed",
        )
        test_session.add(record)
        test_session.commit()

        issue = pipeline.process_record(test_session, record)
        assert issue is None
        assert record.relevance_status == "not_relevant"

