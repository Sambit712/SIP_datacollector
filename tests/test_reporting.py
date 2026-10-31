"""Unit & Integration tests for Phase 6: Reporting & Export System."""

import json
import zipfile
from pathlib import Path
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
    compute_content_hash,
)
from src.reporting.report_builder import ReportBuilder
from src.reporting.exporters import (
    MarkdownExporter,
    CsvExporter,
    PdfExporter,
)
from src.reporting.evidence_exporter import EvidenceLogExporter


@pytest.fixture
def populated_session(tmp_path):
    """Provides a database populated with sample categories, records, issues, clusters, and scores."""
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
        raw_text="AutoPay mandate failed with error code MD01 on Groww.",
        sanitized_text="AutoPay mandate failed with error code MD01 on Groww.",
        content_hash=compute_content_hash("AutoPay mandate failed on Groww"),
        relevance_status="highly_relevant",
    )
    r2 = RawRecord(
        id="raw_02",
        source_type="interview",
        platform="Groww",
        title="User Interview #4",
        raw_text="I could not find the pause button so I stopped my SIP.",
        sanitized_text="I could not find the pause button so I stopped my SIP.",
        content_hash=compute_content_hash("I could not find the pause button"),
        relevance_status="highly_relevant",
    )
    r3 = RawRecord(
        id="raw_03",
        source_type="official_doc",
        platform="SEBI",
        title="SEBI Study 2024",
        raw_text="40% of first-time mutual fund SIPs stop within 12 months.",
        sanitized_text="40% of first-time mutual fund SIPs stop within 12 months.",
        content_hash=compute_content_hash("40% of first-time mutual fund SIPs stop"),
        relevance_status="highly_relevant",
    )
    session.add_all([r1, r2, r3])
    session.flush()

    # 3. Issue Clusters
    cl1 = IssueCluster(
        id="cl_01",
        category_id="cat_01",
        theme_title="Silent Bank Mandate Dropoffs",
        summary_description="Users experience AutoPay failures without plain explanations.",
        evidence_tier="strong",
        supporting_record_count=10,
    )
    cl2 = IssueCluster(
        id="cl_02",
        category_id="cat_04",
        theme_title="Buried Pause Option Triggers Churn",
        summary_description="Pause feature is buried causing users to cancel.",
        evidence_tier="moderate",
        supporting_record_count=4,
    )
    session.add_all([cl1, cl2])
    session.flush()

    # 4. Extracted Issues
    iss1 = ExtractedIssue(
        id="iss_01",
        raw_record_id=r1.id,
        category_id=cat1.id,
        cluster_id=cl1.id,
        core_problem="AutoPay mandate rejection",
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
        core_problem="Missing pause button",
        verbatim_excerpt="could not find the pause button",
        journey_stage="active",
        severity_level="medium",
        epistemic_type="observed_evidence",
        mentions_groww=False,
    )
    session.add_all([iss1, iss2])
    session.commit()

    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# ReportBuilder Tests
# ==============================================================================

class TestReportBuilder:
    """Tests compilation of all 12 PRD-mandated research dossier chapters."""

    def test_build_full_dossier_structure(self, populated_session):
        builder = ReportBuilder(populated_session)
        dossier = builder.build_full_dossier()

        assert "metadata" in dossier
        assert "inventory_stats" in dossier
        assert "feedback_stats" in dossier
        assert "chapters" in dossier
        assert len(dossier["chapters"]) == 12

        # Verify sequential numbering 1 to 12
        for idx, ch in enumerate(dossier["chapters"], start=1):
            assert ch["chapter_number"] == idx
            assert len(ch["title"]) > 0
            assert len(ch["content"]) > 30

    def test_dossier_contains_live_stats(self, populated_session):
        builder = ReportBuilder(populated_session)
        dossier = builder.build_full_dossier()

        inv = dossier["inventory_stats"]
        assert inv["total_records"] == 3
        assert "reddit" in inv["by_channel"]
        assert "interview" in inv["by_channel"]
        assert "official_doc" in inv["by_channel"]

        feed = dossier["feedback_stats"]
        assert feed["total_issues"] == 2
        assert feed["groww_mentions"] == 1


# ==============================================================================
# MarkdownExporter Tests
# ==============================================================================

class TestMarkdownExporter:
    """Tests Markdown serialization, table formatting, and file exports."""

    def test_export_to_string_contents(self, populated_session):
        builder = ReportBuilder(populated_session)
        dossier = builder.build_full_dossier()

        md = MarkdownExporter.export_to_string(dossier)
        assert "# Groww Mutual Fund SIP Persistency Research Dossier" in md
        assert "## Executive Ingestion & Research Inventory" in md
        assert "## Top Prioritized Product Opportunities Leaderboard" in md
        assert "## Table of Contents" in md

        # Verify all 12 chapters are present in the markdown
        for i in range(1, 13):
            assert f"## Chapter {i}:" in md

    def test_export_to_file(self, populated_session, tmp_path):
        builder = ReportBuilder(populated_session)
        dossier = builder.build_full_dossier()

        out_path = tmp_path / "test_dossier.md"
        result_path = MarkdownExporter.export_to_file(dossier, out_path)

        assert Path(result_path).exists()
        assert Path(result_path).stat().st_size > 1000


# ==============================================================================
# CsvExporter Tests
# ==============================================================================

class TestCsvExporter:
    """Tests CSV serialization of database tables and zip packaging."""

    def test_export_raw_records_csv(self, populated_session):
        csv_str = CsvExporter.export_raw_records_csv(populated_session)
        assert "source_type,platform,title" in csv_str
        assert "reddit,Reddit" in csv_str
        assert "official_doc,SEBI" in csv_str

    def test_export_extracted_issues_csv(self, populated_session):
        csv_str = CsvExporter.export_extracted_issues_csv(populated_session)
        assert "raw_record_id,category_id" in csv_str
        assert "AutoPay mandate rejection" in csv_str
        assert "Missing pause button" in csv_str

    def test_export_opportunities_csv(self, populated_session):
        builder = ReportBuilder(populated_session)
        builder.build_full_dossier()

        csv_str = CsvExporter.export_opportunities_csv(populated_session)
        assert "rank,cluster_id,theme_title" in csv_str
        assert "Silent Bank Mandate Dropoffs" in csv_str

    def test_export_all_to_zip(self, populated_session, tmp_path):
        builder = ReportBuilder(populated_session)
        builder.build_full_dossier()

        zip_path = tmp_path / "research_bundle.zip"
        result = CsvExporter.export_all_to_zip(populated_session, zip_path)

        assert Path(result).exists()
        with zipfile.ZipFile(result, "r") as zf:
            namelist = zf.namelist()
            assert "raw_records.csv" in namelist
            assert "extracted_issues.csv" in namelist
            assert "prioritized_opportunities.csv" in namelist


# ==============================================================================
# PdfExporter Tests
# ==============================================================================

class TestPdfExporter:
    """Tests ReportLab PDF document compilation and byte generation."""

    def test_export_to_bytes(self, populated_session):
        builder = ReportBuilder(populated_session)
        dossier = builder.build_full_dossier()

        pdf_bytes = PdfExporter.export_to_bytes(dossier)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 2000
        # Valid PDF magic header
        assert pdf_bytes.startswith(b"%PDF-")

    def test_export_to_file(self, populated_session, tmp_path):
        builder = ReportBuilder(populated_session)
        dossier = builder.build_full_dossier()

        pdf_path = tmp_path / "test_dossier.pdf"
        out = PdfExporter.export_to_file(dossier, pdf_path)

        assert Path(out).exists()
        assert Path(out).stat().st_size > 2000


# ==============================================================================
# EvidenceLogExporter Tests
# ==============================================================================

class TestEvidenceLogExporter:
    """Tests sanitized, privacy-safe read-only evidence log generation."""

    def test_build_evidence_records(self, populated_session):
        exporter = EvidenceLogExporter(populated_session)
        records = exporter.build_evidence_records()

        assert len(records) == 2
        # Check that interview record is properly anonymized
        interview_rec = next(r for r in records if r["source_channel"] == "interview")
        assert "Anonymous" in interview_rec["source_identifier"]
        assert "internal://secure-research-vault" in interview_rec["source_url"]

    def test_export_to_json_and_csv(self, populated_session):
        exporter = EvidenceLogExporter(populated_session)
        json_str = exporter.export_to_json()
        csv_str = exporter.export_to_csv()

        data = json.loads(json_str)
        assert len(data) == 2
        assert "evidence_id" in csv_str
        assert "verified_verbatim_claim" in csv_str

    def test_privacy_compliance_check(self, populated_session):
        exporter = EvidenceLogExporter(populated_session)
        records = exporter.build_evidence_records()
        assert EvidenceLogExporter.verify_privacy_compliance(records) is True

    def test_privacy_compliance_raises_on_leakage(self):
        leaked_records = [
            {
                "evidence_id": "EVID-001",
                "verified_verbatim_claim": "My PAN is ABCDE1234F and it was rejected.",
            }
        ]
        with pytest.raises(ValueError, match="Unmasked PAN detected"):
            EvidenceLogExporter.verify_privacy_compliance(leaked_records)

