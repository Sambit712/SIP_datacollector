"""Content Deduplication & Hash Fingerprinting Engine.

Provides cryptographic SHA-256 fingerprinting on sanitized text to detect
and prevent duplicate ingestion across repeat batches, scrapers, and CSV imports.
"""

import hashlib
from typing import Any, Dict, List, Set, Tuple
from sqlalchemy.orm import Session

from src.models.database import RawRecord, compute_content_hash
from src.nlp.sanitizer import sanitize_text


class Deduplicator:
    """Manages deduplication checks against in-memory batches and database storage."""

    @staticmethod
    def get_hash(text: str) -> str:
        """Computes a normalized SHA-256 content hash."""
        # Sanitize first so PII variations of the same template hash identically
        clean_text = sanitize_text(text).strip()
        return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

    @classmethod
    def is_duplicate_in_db(cls, session: Session, content_hash: str) -> bool:
        """Checks if a record with the same content hash already exists in the database."""
        return session.query(RawRecord.id).filter_by(content_hash=content_hash).first() is not None

    @classmethod
    def filter_batch(
        cls,
        session: Session,
        records: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Separates a batch of candidate records into unique and duplicate sets.

        Checks against:
        1. Duplicate records within the current batch itself.
        2. Existing records already persisted in the database.

        Args:
            session: Active SQLAlchemy database session.
            records: List of raw candidate record dictionaries.

        Returns:
            Tuple of (unique_records, duplicate_records)
        """
        unique_records: List[Dict[str, Any]] = []
        duplicate_records: List[Dict[str, Any]] = []
        seen_in_batch: Set[str] = set()

        # Pre-fetch existing hashes in DB to minimize query overhead
        candidate_hashes = [
            cls.get_hash(r.get("raw_text", ""))
            for r in records
            if r.get("raw_text")
        ]
        existing_db_hashes: Set[str] = set(
            row[0]
            for row in session.query(RawRecord.content_hash)
            .filter(RawRecord.content_hash.in_(candidate_hashes))
            .all()
        )

        for rec in records:
            raw_text = rec.get("raw_text", "")
            if not raw_text or not raw_text.strip():
                duplicate_records.append(rec)
                continue

            content_hash = cls.get_hash(raw_text)
            rec["content_hash"] = content_hash
            rec["sanitized_text"] = sanitize_text(raw_text)

            if content_hash in seen_in_batch or content_hash in existing_db_hashes:
                duplicate_records.append(rec)
            else:
                seen_in_batch.add(content_hash)
                unique_records.append(rec)

        return unique_records, duplicate_records

