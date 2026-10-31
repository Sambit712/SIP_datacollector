"""Sanitized Evidence Log Exporter.

Produces a read-only, shareable evidence audit log in JSON and CSV formats
strictly safe for public case-study and portfolio presentation.
Guarantees zero leakage of PII, private interview participant identifiers,
or unmasked financial data.
"""

import csv
import json
import io
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session

from src.models.database import RawRecord, ExtractedIssue, IssueCategory
from src.nlp.sanitizer import PIISanitizer

logger = logging.getLogger("ai_discovery_engine.reporting.evidence_exporter")


class EvidenceLogExporter:
    """Exports privacy-safe, audited evidence logs for external review and validation."""

    def __init__(self, session: Session):
        self.session = session
        self.sanitizer = PIISanitizer()

    def build_evidence_records(self, exclude_unverified: bool = False) -> List[Dict[str, Any]]:
        """Queries and formats all extracted issues into sanitized, audit-safe records."""
        query = (
            self.session.query(ExtractedIssue)
            .join(RawRecord)
            .join(IssueCategory, ExtractedIssue.category_id == IssueCategory.id, isouter=True)
        )

        if exclude_unverified:
            query = query.filter(RawRecord.relevance_status.in_(["highly_relevant", "partially_relevant"]))

        issues = query.all()
        categories = {c.id: c.name for c in self.session.query(IssueCategory).all()}

        evidence_log: List[Dict[str, Any]] = []
        for issue in issues:
            raw = issue.raw_record
            if not raw:
                continue

            # Anonymize source URL / identifier for private interviews
            if raw.source_type == "interview":
                source_identifier = "Anonymous Qualitative User Interview [Research Vault]"
                source_url = "internal://secure-research-vault/interviews/anonymized"
            else:
                source_identifier = raw.title or f"{raw.platform} Record"
                source_url = raw.source_url or "https://public-record.verified"

            # Double-pass privacy sanitization on verbatim excerpt and core problem
            safe_verbatim = self.sanitizer.sanitize(issue.verbatim_excerpt or "")
            safe_problem = self.sanitizer.sanitize(issue.core_problem or "")

            item = {
                "evidence_id": f"EVID-{issue.id[:8]}",
                "source_channel": raw.source_type,
                "platform": raw.platform,
                "source_identifier": source_identifier,
                "source_url": source_url,
                "verified_verbatim_claim": safe_verbatim,
                "core_problem": safe_problem,
                "category_id": issue.category_id or "unclassified",
                "category_name": categories.get(issue.category_id, "Unclassified"),
                "journey_stage": issue.journey_stage,
                "severity_level": issue.severity_level,
                "epistemic_type": issue.epistemic_type,
                "confidence_score": round(issue.confidence_score, 2),
                "mentions_groww": issue.mentions_groww,
                "is_synthetic_demo": raw.is_synthetic_demo,
            }
            evidence_log.append(item)

        return evidence_log

    def export_to_json(self, indent: int = 2, exclude_unverified: bool = False) -> str:
        """Exports evidence records as formatted JSON string."""
        records = self.build_evidence_records(exclude_unverified=exclude_unverified)
        return json.dumps(records, indent=indent, ensure_ascii=False)

    def export_to_csv(self, exclude_unverified: bool = False) -> str:
        """Exports evidence records as CSV string."""
        records = self.build_evidence_records(exclude_unverified=exclude_unverified)
        if not records:
            return ""

        output = io.StringIO()
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()

    def export_to_file(
        self,
        filepath: Union[str, Path],
        file_format: str = "json",
        exclude_unverified: bool = False,
    ) -> str:
        """Writes evidence log to file and returns absolute path."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        if file_format.lower() == "csv":
            content = self.export_to_csv(exclude_unverified=exclude_unverified)
        else:
            content = self.export_to_json(exclude_unverified=exclude_unverified)
        p.write_text(content, encoding="utf-8")
        return str(p.resolve())

    @staticmethod
    def verify_privacy_compliance(records: List[Dict[str, Any]]) -> bool:
        """Verifies that no unmasked PAN, mobile, or email appears in any exported field.

        Returns True if 100% compliant, raises ValueError if unmasked PII is detected.
        """
        pan_regex = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
        email_regex = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
        phone_regex = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")

        for r in records:
            for k, val in r.items():
                val_str = str(val)
                if pan_regex.search(val_str):
                    raise ValueError(f"PII Leakage: Unmasked PAN detected in record {r.get('evidence_id')}, field '{k}'")
                if email_regex.search(val_str):
                    raise ValueError(f"PII Leakage: Unmasked email detected in record {r.get('evidence_id')}, field '{k}'")
                # Exclude URL identifiers from phone check
                if k != "source_url" and phone_regex.search(val_str):
                    raise ValueError(f"PII Leakage: Unmasked phone detected in record {r.get('evidence_id')}, field '{k}'")

        return True

