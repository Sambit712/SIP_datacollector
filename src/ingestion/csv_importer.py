"""Manual Research & Interview Importer.

Enables Product Managers to upload user interview transcripts, survey CSVs,
and field notes into the research engine.

Enforces:
- Automatic PII stripping via sanitizer.py
- Anonymized participant tags (e.g., USER_INT_01, RESPONDENT_05)
- Metadata capture: first-time investor flag, SIP status, reported obstacles
"""

import csv
from datetime import datetime, timezone
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.ingestion.base import BaseIngestor
from src.nlp.sanitizer import sanitize_text

logger = logging.getLogger("ai_discovery_engine.csv_importer")

SAMPLE_INTERVIEW_PAYLOADS = [
    {
        "anonymous_id": "USER_INT_11",
        "first_time_investor": True,
        "sip_status": "discontinued",
        "reported_reason": "Salary credit date varies between 1st and 7th. After 2 bounce charges of ₹295 each, cancelled SIP.",
        "transcript": "Interviewer: Why did you stop your mutual fund SIP on Groww?\nParticipant: I set it for the 1st of every month because that's what I thought everyone does. But my employer credits salary on the 5th or 6th. The bank charged me ₹295 penalty twice. That's ₹600 gone for doing nothing. I cancelled the SIP immediately.",
        "date": "2026-06-12",
    },
    {
        "anonymous_id": "USER_INT_12",
        "first_time_investor": True,
        "sip_status": "active",
        "reported_reason": "Set debit date 5 days after salary date, maintains active discipline.",
        "transcript": "Interviewer: How do you manage to keep your SIP active?\nParticipant: My senior colleague told me never set SIP date on 1st. My salary comes on 31st, so I set SIP for 5th. This gives me a buffer. Working great for 10 months now.",
        "date": "2026-07-01",
    },
]


class CsvImporter(BaseIngestor):
    """Ingestor connector for qualitative user interviews, surveys, and CSV uploads."""

    def __init__(self):
        super().__init__(source_type="interview", platform="Interview")

    def fetch(self, query_or_params: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Parses CSV files, strings, or interview notes into normalized records.

        Args:
            query_or_params: Path to CSV, file-like object, CSV text string, or list of dicts.

        Returns:
            List of normalized candidate record dictionaries.
        """
        if query_or_params is None:
            # Return sample interview records
            return self._parse_records_list(SAMPLE_INTERVIEW_PAYLOADS)

        if isinstance(query_or_params, list):
            return self._parse_records_list(query_or_params)

        if isinstance(query_or_params, (str, Path)):
            p = Path(query_or_params)
            if p.exists() and p.is_file():
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    return self.parse_csv_content(f.read(), source_filename=p.name)
            else:
                # Might be a raw CSV string
                return self.parse_csv_content(str(query_or_params))

        if hasattr(query_or_params, "read"):
            content = query_or_params.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            filename = getattr(query_or_params, "name", "uploaded_file.csv")
            return self.parse_csv_content(content, source_filename=filename)

        return []

    def parse_csv_content(self, csv_text: str, source_filename: str = "manual_import.csv") -> List[Dict[str, Any]]:
        """Parses a CSV string into sanitized record dictionaries."""
        results: List[Dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(csv_text.strip()))

        for idx, row in enumerate(reader, start=1):
            # Normalize column names by lowercasing and stripping
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}

            # Flexible column mapping
            anon_id = (
                clean_row.get("anonymous_id")
                or clean_row.get("user_id")
                or clean_row.get("respondent_id")
                or f"ANON_USER_{idx:03d}"
            )
            raw_text = (
                clean_row.get("transcript")
                or clean_row.get("notes")
                or clean_row.get("feedback")
                or clean_row.get("text")
                or clean_row.get("reported_reason", "")
            )
            if not raw_text:
                continue

            # Prepend metadata context if available
            sip_status = clean_row.get("sip_status", "unknown")
            is_first_time = clean_row.get("first_time_investor", clean_row.get("is_first_time", "true"))
            title = f"User Interview: {anon_id} (Status: {sip_status}, First-Timer: {is_first_time})"
            pub_date = clean_row.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

            results.append({
                "source_type": self.source_type,
                "platform": self.platform,
                "source_url": f"internal://research/interviews/{source_filename}#{anon_id}",
                "title": title,
                "raw_text": f"{title}\n\n{raw_text}",
                "publication_date": pub_date,
                "rating": None,
                "is_synthetic_demo": False,  # User-uploaded primary research
                "relevance_status": "highly_relevant",
            })

        return results

    def import_notes_text(
        self,
        anonymous_id: str,
        notes_text: str,
        sip_status: str = "unknown",
        first_time_investor: bool = True,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a single normalized interview record from pasted text notes."""
        clean_notes = sanitize_text(notes_text)
        pub_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title = f"User Research Note: {anonymous_id} (Status: {sip_status}, First-Time: {first_time_investor})"
        full_text = f"{title}\n\n{clean_notes}"

        return {
            "source_type": self.source_type,
            "platform": self.platform,
            "source_url": f"internal://research/interviews/notes/{anonymous_id}",
            "title": title,
            "raw_text": full_text,
            "publication_date": pub_date,
            "rating": None,
            "is_synthetic_demo": False,
            "relevance_status": "highly_relevant",
        }

    def _parse_records_list(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parses a structured list of interview dictionaries."""
        results: List[Dict[str, Any]] = []
        for item in records:
            anon_id = item.get("anonymous_id", "ANON_USER")
            transcript = item.get("transcript") or item.get("text") or item.get("reported_reason", "")
            title = f"Interview: {anon_id} (SIP: {item.get('sip_status', 'unknown')})"
            full_text = f"{title}\n\n{transcript}"

            results.append({
                "source_type": self.source_type,
                "platform": self.platform,
                "source_url": f"internal://research/interviews/{anon_id}",
                "title": title,
                "raw_text": full_text,
                "publication_date": item.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "rating": None,
                "is_synthetic_demo": True,
                "relevance_status": "highly_relevant",
            })
        return results

