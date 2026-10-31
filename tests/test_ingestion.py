"""Unit & Integration tests for Multi-Source Ingestion Engine (Phase 2)."""

import io
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.base import BaseIngestor
from src.ingestion.deduplicator import Deduplicator
from src.ingestion.reddit_collector import RedditCollector
from src.ingestion.review_collector import ReviewCollector
from src.ingestion.doc_collector import DocCollector
from src.ingestion.news_collector import NewsCollector
from src.ingestion.csv_importer import CsvImporter
from src.models.database import Base, RawRecord


@pytest.fixture
def fresh_session():
    """Provides a fresh isolated in-memory SQLite database session for ingestion tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Deduplicator Tests
# ---------------------------------------------------------------------------

class TestDeduplicator:
    def test_hash_normalization(self):
        t1 = "  My SIP payment failed on Groww.  \n"
        t2 = "My SIP payment failed on Groww."
        assert Deduplicator.get_hash(t1) == Deduplicator.get_hash(t2)

    def test_filter_batch_duplicates(self, fresh_session):
        batch = [
            {"raw_text": "First unique complaint about AutoPay."},
            {"raw_text": "Second unique complaint about XIRR."},
            {"raw_text": "First unique complaint about AutoPay."},  # Duplicate in batch
            {"raw_text": "   "},  # Empty invalid
        ]
        unique, dups = Deduplicator.filter_batch(fresh_session, batch)
        assert len(unique) == 2
        assert len(dups) == 2

    def test_filter_batch_against_db(self, fresh_session):
        # Save one record to DB
        text = "Existing record in database about bounce fees."
        h = Deduplicator.get_hash(text)
        rec = RawRecord(
            id="rec_exist",
            source_type="reddit",
            platform="Reddit",
            raw_text=text,
            sanitized_text=text,
            content_hash=h,
        )
        fresh_session.add(rec)
        fresh_session.commit()

        # Now test filtering candidate batch containing same text
        candidate_batch = [
            {"raw_text": text},
            {"raw_text": "Brand new candidate record."},
        ]
        unique, dups = Deduplicator.filter_batch(fresh_session, candidate_batch)
        assert len(unique) == 1
        assert len(dups) == 1
        assert unique[0]["raw_text"] == "Brand new candidate record."


# ---------------------------------------------------------------------------
# Reddit Collector Tests
# ---------------------------------------------------------------------------

class TestRedditCollector:
    def test_reddit_fetch_mock(self):
        collector = RedditCollector()
        records = collector.fetch("Groww SIP failed")
        assert len(records) > 0
        for r in records:
            assert r["source_type"] == "reddit"
            assert r["platform"] == "Reddit"
            assert "reddit.com" in r["source_url"]
            assert len(r["raw_text"]) > 10

    def test_reddit_ingest_and_deduplication(self, fresh_session):
        collector = RedditCollector()
        inserted1, skipped1 = collector.ingest(fresh_session, "Groww AutoPay issue")
        assert inserted1 > 0
        assert skipped1 == 0

        # Ingest again: should detect all as duplicates
        inserted2, skipped2 = collector.ingest(fresh_session, "Groww AutoPay issue")
        assert inserted2 == 0
        assert skipped2 == inserted1


# ---------------------------------------------------------------------------
# App Store Review Collector Tests
# ---------------------------------------------------------------------------

class TestReviewCollector:
    def test_balanced_ratings_ingestion(self, fresh_session):
        collector = ReviewCollector()
        inserted, _ = collector.ingest(fresh_session)
        assert inserted > 0

        # Verify rating balance in DB
        low_ratings = fresh_session.query(RawRecord).filter(
            RawRecord.source_type == "app_store",
            RawRecord.rating <= 2
        ).count()
        high_ratings = fresh_session.query(RawRecord).filter(
            RawRecord.source_type == "app_store",
            RawRecord.rating >= 4
        ).count()

        assert low_ratings > 0, "Must have negative reviews"
        assert high_ratings > 0, "Must have positive reviews to prevent research skew"

    def test_normalize_custom_reviews(self):
        collector = ReviewCollector()
        custom = [
            {"platform": "GooglePlay", "rating": 1, "title": "Crash", "text": "App crashed", "review_id": "c1"},
            {"platform": "AppStore", "rating": 5, "title": "Good", "text": "Very smooth", "review_id": "c2"},
        ]
        records = collector.fetch({"reviews_data": custom})
        assert len(records) == 2
        assert records[0]["rating"] == 1
        assert records[1]["rating"] == 5


# ---------------------------------------------------------------------------
# Official Doc Collector Tests
# ---------------------------------------------------------------------------

class TestDocCollector:
    def test_doc_fetch_all_and_filtering(self):
        collector = DocCollector()
        all_docs = collector.fetch()
        assert len(all_docs) >= 5

        # Test filtering by platform
        sebi_docs = collector.fetch({"platform": "SEBI"})
        assert len(sebi_docs) > 0
        for doc in sebi_docs:
            assert doc["platform"] == "SEBI"
            assert doc["is_synthetic_demo"] is False

    def test_doc_ingest(self, fresh_session):
        collector = DocCollector()
        inserted, _ = collector.ingest(fresh_session)
        assert inserted >= 5
        db_docs = fresh_session.query(RawRecord).filter_by(source_type="official_doc").all()
        platforms = {d.platform for d in db_docs}
        assert "Groww" in platforms
        assert "SEBI" in platforms
        assert "AMFI" in platforms


# ---------------------------------------------------------------------------
# News Collector Tests
# ---------------------------------------------------------------------------

class TestNewsCollector:
    def test_news_fetch_and_ingest(self, fresh_session):
        collector = NewsCollector()
        records = collector.fetch()
        assert len(records) >= 3
        for r in records:
            assert r["source_type"] == "news"
            assert "http" in r["source_url"]

        inserted, _ = collector.ingest(fresh_session)
        assert inserted >= 3
        news_in_db = fresh_session.query(RawRecord).filter_by(source_type="news").count()
        assert news_in_db == inserted


# ---------------------------------------------------------------------------
# CSV & Interview Importer Tests
# ---------------------------------------------------------------------------

class TestCsvImporter:
    def test_import_from_csv_string(self, fresh_session):
        csv_data = """anonymous_id,transcript,sip_status,first_time_investor,date
USER_TEST_01,"My salary arrives on 7th so 1st debit bounced with ₹295 charge.",discontinued,true,2026-06-01
USER_TEST_02,"Pausing SIP was difficult because skip button didn't work.",paused,true,2026-06-05
"""
        importer = CsvImporter()
        records = importer.fetch(csv_data)
        assert len(records) == 2
        assert "USER_TEST_01" in records[0]["raw_text"]
        assert records[0]["source_type"] == "interview"

        inserted, _ = importer.save_batch(fresh_session, records)
        assert inserted == 2

    def test_import_notes_with_pii_sanitization(self, fresh_session):
        importer = CsvImporter()
        raw_notes = "Participant Rahul (phone: 9876543210, PAN: ABCDE1234F) said AutoPay failed on HDFC a/c 123456789012."
        note_dict = importer.import_notes_text(
            anonymous_id="USER_ANON_99",
            notes_text=raw_notes,
            sip_status="failed",
        )
        assert "9876543210" not in note_dict["raw_text"] or "[REDACTED_PHONE]" in note_dict["raw_text"]

        inserted, _ = importer.save_batch(fresh_session, [note_dict])
        assert inserted == 1

        db_rec = fresh_session.query(RawRecord).filter_by(source_type="interview").first()
        assert "[REDACTED_PAN]" in db_rec.sanitized_text
        assert "ABCDE1234F" not in db_rec.sanitized_text

    def test_import_file_like_object(self, fresh_session):
        csv_content = "anonymous_id,notes,sip_status\nUSER_FILE_01,Interview about salary mismatch,active\n"
        file_obj = io.StringIO(csv_content)
        file_obj.name = "test_upload.csv"

        importer = CsvImporter()
        records = importer.fetch(file_obj)
        assert len(records) == 1
        assert "USER_FILE_01" in records[0]["raw_text"]

