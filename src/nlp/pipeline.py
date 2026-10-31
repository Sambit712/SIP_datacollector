"""End-to-End NLP & AI Intelligence Pipeline Orchestrator.

Sequences:
1. Relevance Filtering (RelevanceFilter)
2. Complaint & Entity Extraction (ComplaintExtractor)
3. Taxonomy Classification & Emergence Check (TaxonomyClassifier)
4. Epistemic Triangulation (EpistemicTriangulator)
5. Semantic Clustering & Centroid Synthesis (IssueClusterer)
6. Immutable Audit Trail Logging (EvidenceAudit)
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from src.models.database import (
    EvidenceAudit,
    ExtractedIssue,
    IssueCategory,
    IssueCluster,
    RawRecord,
    generate_uuid,
)
from src.nlp.classifier import TaxonomyClassifier
from src.nlp.clusterer import IssueClusterer
from src.nlp.extractor import ComplaintExtractor
from src.nlp.llm_client import GroqLLMClient
from src.nlp.relevance_filter import RelevanceFilter
from src.nlp.triangulator import EpistemicTriangulator

logger = logging.getLogger("ai_discovery_engine.pipeline")


class AnalysisPipeline:
    """Orchestrates end-to-end AI analysis across raw research records."""

    def __init__(self, llm_client: Optional[GroqLLMClient] = None):
        self.llm = llm_client or GroqLLMClient()
        self.relevance_filter = RelevanceFilter(self.llm)
        self.extractor = ComplaintExtractor(self.llm)
        self.classifier = TaxonomyClassifier(self.llm)
        self.clusterer = IssueClusterer(self.llm)

    def process_record(self, session: Session, record: RawRecord) -> Optional[ExtractedIssue]:
        """Processes a single RawRecord through filtering, extraction, and audit logging."""
        # 1. Relevance Classification
        status, conf, reason = self.relevance_filter.classify_record(record.sanitized_text, record.title)
        record.relevance_status = status

        if status == "not_relevant":
            session.commit()
            return None

        # 2. Complaint & Entity Extraction
        extracted_schema = self.extractor.extract_issue(record.sanitized_text, record.platform)

        # 3. Taxonomy Classification
        cat_id, cat_code, cat_conf, is_emergent = self.classifier.classify(
            extracted_schema.verbatim_excerpt,
            extracted_schema.core_problem,
        )

        # 4. Epistemic Triangulation
        epistemic_type, epistemic_note = EpistemicTriangulator.classify_claim(
            extracted_schema.verbatim_excerpt,
            extracted_schema.is_first_hand_experience,
        )

        # 5. Persist ExtractedIssue
        issue = ExtractedIssue(
            id=generate_uuid(),
            raw_record_id=record.id,
            category_id=cat_id,
            core_problem=extracted_schema.core_problem,
            verbatim_excerpt=extracted_schema.verbatim_excerpt,
            journey_stage=extracted_schema.journey_stage,
            mentions_groww=extracted_schema.mentions_groww,
            is_first_hand_experience=extracted_schema.is_first_hand_experience,
            sip_status=extracted_schema.sip_status,
            stated_discontinuation_reason=extracted_schema.stated_discontinuation_reason,
            severity_level=extracted_schema.severity_level,
            epistemic_type=epistemic_type,
            confidence_score=cat_conf,
        )
        session.add(issue)

        # 6. Immutable Evidence Audit Log
        audit = EvidenceAudit(
            id=generate_uuid(),
            raw_record_id=record.id,
            extracted_issue_id=issue.id,
            source_url=record.source_url,
            exact_quote=extracted_schema.verbatim_excerpt,
            verification_status="verified_accurate" if extracted_schema.verbatim_excerpt in record.sanitized_text else "unverified",
        )
        session.add(audit)
        session.commit()

        return issue

    def process_all_unanalyzed(self, session: Session, batch_size: int = 50) -> Dict[str, int]:
        """Processes all unanalyzed raw records in the database."""
        records = (
            session.query(RawRecord)
            .filter(RawRecord.relevance_status == "unanalyzed")
            .limit(batch_size)
            .all()
        )

        processed = 0
        relevant = 0
        excluded = 0

        for r in records:
            issue = self.process_record(session, r)
            processed += 1
            if issue:
                relevant += 1
            else:
                excluded += 1

        # Recluster after new issues are extracted
        clusters_created = 0
        if relevant > 0:
            clusters_created = self.cluster_all_extracted_issues(session)

        return {
            "processed": processed,
            "relevant": relevant,
            "excluded": excluded,
            "clusters_updated": clusters_created,
        }

    def cluster_all_extracted_issues(self, session: Session) -> int:
        """Clusters all extracted issues and creates/updates IssueCluster entities."""
        issues = session.query(ExtractedIssue).all()
        if not issues:
            return 0

        # Convert to dicts for clusterer
        issue_dicts = [
            {
                "id": i.id,
                "core_problem": i.core_problem,
                "verbatim_excerpt": i.verbatim_excerpt,
                "category_id": i.category_id,
            }
            for i in issues
        ]

        synthesized_clusters = self.clusterer.cluster_issues(issue_dicts)

        # Clear existing clusters for clean rebuild
        session.query(IssueCluster).delete()
        session.commit()

        clusters_saved = 0
        for sc in synthesized_clusters:
            cluster_id = generate_uuid()
            cluster = IssueCluster(
                id=cluster_id,
                category_id=sc.get("category_id"),
                theme_title=sc["theme_title"],
                summary_description=sc["summary_description"],
                primary_root_cause=sc.get("primary_root_cause"),
                supporting_record_count=sc["supporting_record_count"],
                evidence_tier=sc["evidence_tier"],
            )
            session.add(cluster)

            # Assign cluster_id to member issues
            member_ids = sc.get("member_ids", [])
            if member_ids:
                session.query(ExtractedIssue).filter(ExtractedIssue.id.in_(member_ids)).update(
                    {ExtractedIssue.cluster_id: cluster_id},
                    synchronize_session=False,
                )

            clusters_saved += 1

        session.commit()
        return clusters_saved

