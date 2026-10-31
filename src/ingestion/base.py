"""Base Ingestion Interface & Abstract Ingestor.

Provides standardized contract for all multi-source ingestion connectors:
- Reddit discussions
- Google Play & Apple App Store reviews
- Official documentation & regulatory reports (Groww, SEBI, AMFI)
- Financial news & research publications
- Qualitative user interviews & CSV uploads
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from config.settings import setup_logging
from src.ingestion.deduplicator import Deduplicator
from src.models.database import RawRecord, generate_uuid
from src.nlp.sanitizer import sanitize_text

logger = setup_logging()


class BaseIngestor(ABC):
    """Abstract base class for all research source connectors."""

    def __init__(self, source_type: str, platform: str):
        self.source_type = source_type
        self.platform = platform

    @abstractmethod
    def fetch(self, query_or_params: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Fetches raw candidate records from the source.

        Args:
            query_or_params: Search keywords, date ranges, file paths, or API parameters.

        Returns:
            List of raw record dictionaries.
        """
        pass

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """Validates that candidate dictionary contains required fields and non-empty text."""
        raw_text = record.get("raw_text")
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            return False
        if not record.get("source_type") or not record.get("platform"):
            return False
        return True

    def sanitize_and_prepare(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Scrubs PII and computes deterministic SHA-256 content fingerprint."""
        raw_text = record["raw_text"]
        sanitized = sanitize_text(raw_text)
        content_hash = Deduplicator.get_hash(raw_text)

        prepared = dict(record)
        prepared["id"] = prepared.get("id") or generate_uuid()
        prepared["source_type"] = prepared.get("source_type") or self.source_type
        prepared["platform"] = prepared.get("platform") or self.platform
        prepared["sanitized_text"] = sanitized
        prepared["content_hash"] = content_hash
        prepared["relevance_status"] = prepared.get("relevance_status", "unanalyzed")
        prepared["is_user_verified"] = prepared.get("is_user_verified", False)
        prepared["is_synthetic_demo"] = prepared.get("is_synthetic_demo", False)
        return prepared

    def save_batch(
        self,
        session: Session,
        raw_records: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """Validates, deduplicates, and saves candidate records to the database.

        Args:
            session: Active SQLAlchemy database session.
            raw_records: List of raw candidate record dictionaries.

        Returns:
            Tuple of (inserted_count, skipped_count).
        """
        valid_records: List[Dict[str, Any]] = []
        invalid_count = 0

        for r in raw_records:
            r["source_type"] = r.get("source_type") or self.source_type
            r["platform"] = r.get("platform") or self.platform
            if self.validate_record(r):
                valid_records.append(r)
            else:
                invalid_count += 1

        unique_records, duplicates = Deduplicator.filter_batch(session, valid_records)
        skipped_count = len(duplicates) + invalid_count

        inserted_count = 0
        for rec in unique_records:
            prepared = self.sanitize_and_prepare(rec)
            db_record = RawRecord(
                id=prepared["id"],
                source_type=prepared["source_type"],
                source_url=prepared.get("source_url"),
                platform=prepared["platform"],
                title=prepared.get("title"),
                raw_text=prepared["raw_text"],
                sanitized_text=prepared["sanitized_text"],
                content_hash=prepared["content_hash"],
                rating=prepared.get("rating"),
                publication_date=prepared.get("publication_date"),
                relevance_status=prepared.get("relevance_status", "unanalyzed"),
                is_user_verified=prepared.get("is_user_verified", False),
                is_synthetic_demo=prepared.get("is_synthetic_demo", False),
            )
            session.add(db_record)
            inserted_count += 1

        if inserted_count > 0:
            session.commit()

        logger.info(
            f"[{self.source_type.upper()}] Ingestion completed: {inserted_count} inserted, {skipped_count} skipped."
        )
        return inserted_count, skipped_count

    def ingest(
        self,
        session: Session,
        query_or_params: Optional[Any] = None,
    ) -> Tuple[int, int]:
        """Convenience method orchestrating fetch and database persistence."""
        records = self.fetch(query_or_params)
        return self.save_batch(session, records)
