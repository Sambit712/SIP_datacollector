"""Opportunity Prioritization Scoring Engine.

Implements the 6-dimensional weighted prioritization matrix to rank discovered
problem clusters objectively and transparently for Product Managers.

Mathematical Formulation:
    Composite Score = w_biz * S_biz + w_sev * S_sev + w_act * S_act
                    + w_conf * S_conf + w_freq * S_freq + w_eff * (1.0 - S_eff)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from src.models.database import IssueCluster, OpportunityScore, generate_uuid
from src.prioritization.dampener import FrequencyDampener
from src.prioritization.explainer import OpportunityExplainer

logger = logging.getLogger("ai_discovery_engine.prioritization.scorer")


class PrioritizationWeights(BaseModel):
    """Dynamic weight configuration for the 6 prioritization dimensions."""

    business_relevance: float = Field(0.25, ge=0.0, description="Impact on 12-Month SIP continuation")
    severity: float = Field(0.20, ge=0.0, description="Severity of user financial/emotional pain")
    actionability: float = Field(0.20, ge=0.0, description="Feasibility within Groww's product scope")
    evidence_confidence: float = Field(0.15, ge=0.0, description="Evidence triangulation confidence")
    frequency: float = Field(0.10, ge=0.0, description="Log-damped multi-channel frequency")
    implementation_effort: float = Field(0.10, ge=0.0, description="Engineering/compliance cost (inverted)")

    def normalized(self) -> "PrioritizationWeights":
        """Returns a new PrioritizationWeights instance normalized so sum(weights) == 1.0."""
        total = (
            self.business_relevance
            + self.severity
            + self.actionability
            + self.evidence_confidence
            + self.frequency
            + self.implementation_effort
        )
        if total <= 0.0:
            # Fall back to equal weights
            equal = 1.0 / 6.0
            return PrioritizationWeights(
                business_relevance=equal,
                severity=equal,
                actionability=equal,
                evidence_confidence=equal,
                frequency=equal,
                implementation_effort=equal,
            )
        return PrioritizationWeights(
            business_relevance=self.business_relevance / total,
            severity=self.severity / total,
            actionability=self.actionability / total,
            evidence_confidence=self.evidence_confidence / total,
            frequency=self.frequency / total,
            implementation_effort=self.implementation_effort / total,
        )


# Default category-level baseline heuristics when cluster lacks fine-grained overrides
CATEGORY_HEURISTICS: Dict[str, Dict[str, float]] = {
    "cat_01": {"biz": 0.95, "act": 0.85, "eff": 0.50},  # autopay_mandate
    "cat_02": {"biz": 0.90, "act": 0.85, "eff": 0.40},  # kyc_bank_verification
    "cat_03": {"biz": 0.90, "act": 0.80, "eff": 0.30},  # hidden_charges_penalties
    "cat_04": {"biz": 0.85, "act": 0.95, "eff": 0.35},  # discontinuation_friction
    "cat_05": {"biz": 0.85, "act": 0.75, "eff": 0.30},  # market_volatility_panic
    "cat_06": {"biz": 0.80, "act": 0.85, "eff": 0.30},  # unintended_debt_exposure
    "cat_07": {"biz": 0.85, "act": 0.90, "eff": 0.40},  # cash_flow_mismatch
    "cat_08": {"biz": 0.70, "act": 0.90, "eff": 0.35},  # ui_ux_complexity
    "cat_09": {"biz": 0.65, "act": 0.85, "eff": 0.25},  # educational_guidance
    "cat_10": {"biz": 0.60, "act": 0.70, "eff": 0.30},  # tax_implication_confusion
    "cat_11": {"biz": 0.70, "act": 0.75, "eff": 0.35},  # goal_horizon_misalignment
    "cat_12": {"biz": 0.75, "act": 0.55, "eff": 0.60},  # partner_bank_downtime
    "cat_13": {"biz": 0.70, "act": 0.80, "eff": 0.45},  # customer_support_delays
}

SEVERITY_MAP = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
}

CONFIDENCE_MAP = {
    "strong": 1.0,
    "moderate": 0.65,
    "weak": 0.35,
}


class OpportunityScorer:
    """Calculates multidimensional priority scores and ranks problem clusters."""

    def __init__(self, dampener: Optional[FrequencyDampener] = None):
        self.dampener = dampener or FrequencyDampener()

    @staticmethod
    def min_max_normalize(
        values: List[float],
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> List[float]:
        """Normalizes a list of values onto [0.0, 1.0] using min-max scaling."""
        if not values:
            return []
        lo = min_val if min_val is not None else min(values)
        hi = max_val if max_val is not None else max(values)
        if hi == lo:
            return [0.5 for _ in values]
        return [round((v - lo) / (hi - lo), 4) for v in values]

    def estimate_cluster_dimensions(self, cluster: IssueCluster) -> Dict[str, float]:
        """Infers the 6 base dimension scores from cluster metadata and linked issues."""
        cat_id = getattr(cluster, "category_id", "") or ""
        heuristics = CATEGORY_HEURISTICS.get(cat_id, {"biz": 0.60, "act": 0.65, "eff": 0.45})

        # 1. Frequency Score via Anti-Vocal-Minority Dampener
        freq_score = self.dampener.calculate_for_cluster(cluster)

        # 2. Severity Score: Average severity of underlying issues
        issues = getattr(cluster, "extracted_issues", []) or []
        if issues:
            sev_scores = [SEVERITY_MAP.get(getattr(i, "severity_level", "medium"), 0.50) for i in issues]
            sev_score = sum(sev_scores) / len(sev_scores)
        else:
            sev_score = 0.60

        # 3. Business Relevance
        biz_score = heuristics["biz"]

        # 4. Evidence Confidence
        tier = getattr(cluster, "evidence_tier", "moderate")
        conf_score = CONFIDENCE_MAP.get(tier, 0.65)

        # 5. Actionability
        act_score = heuristics["act"]

        # 6. Implementation Effort
        eff_score = heuristics["eff"]

        return {
            "frequency": round(min(1.0, max(0.0, freq_score)), 4),
            "severity": round(min(1.0, max(0.0, sev_score)), 4),
            "business_relevance": round(min(1.0, max(0.0, biz_score)), 4),
            "evidence_confidence": round(min(1.0, max(0.0, conf_score)), 4),
            "actionability": round(min(1.0, max(0.0, act_score)), 4),
            "implementation_effort": round(min(1.0, max(0.0, eff_score)), 4),
        }

    def compute_composite_score(
        self,
        dimensions: Dict[str, float],
        weights: Optional[PrioritizationWeights] = None,
    ) -> float:
        """Computes composite priority score given dimension values and weights.

        Formula:
            w_biz * S_biz + w_sev * S_sev + w_act * S_act + w_conf * S_conf + w_freq * S_freq + w_eff * (1.0 - S_eff)
        """
        w = (weights or PrioritizationWeights()).normalized()

        s_biz = dimensions.get("business_relevance", 0.0)
        s_sev = dimensions.get("severity", 0.0)
        s_act = dimensions.get("actionability", 0.0)
        s_conf = dimensions.get("evidence_confidence", 0.0)
        s_freq = dimensions.get("frequency", 0.0)
        s_eff = dimensions.get("implementation_effort", 0.0)

        composite = (
            w.business_relevance * s_biz
            + w.severity * s_sev
            + w.actionability * s_act
            + w.evidence_confidence * s_conf
            + w.frequency * s_freq
            + w.implementation_effort * (1.0 - s_eff)
        )
        return round(min(1.0, max(0.0, composite)), 4)

    def score_cluster(
        self,
        cluster: IssueCluster,
        weights: Optional[PrioritizationWeights] = None,
        manual_overrides: Optional[Dict[str, float]] = None,
    ) -> OpportunityScore:
        """Calculates OpportunityScore entity for a single IssueCluster."""
        dims = self.estimate_cluster_dimensions(cluster)
        if manual_overrides:
            dims.update(manual_overrides)

        composite = self.compute_composite_score(dims, weights)

        opp_score = OpportunityScore(
            id=generate_uuid(),
            cluster_id=cluster.id,
            frequency_score=dims["frequency"],
            severity_score=dims["severity"],
            business_relevance_score=dims["business_relevance"],
            evidence_confidence_score=dims["evidence_confidence"],
            actionability_score=dims["actionability"],
            implementation_effort_score=dims["implementation_effort"],
            composite_priority_score=composite,
            score_rationale="",
            last_calculated_at=datetime.now(timezone.utc),
        )
        return opp_score

    def score_all_clusters(
        self,
        session: Any,
        weights: Optional[PrioritizationWeights] = None,
        persist: bool = True,
    ) -> List[Tuple[IssueCluster, OpportunityScore]]:
        """Scores all IssueClusters in database, ranks them, generates rationales, and persists.

        Returns:
            List of (IssueCluster, OpportunityScore) tuples sorted descending by composite priority score.
        """
        clusters = session.query(IssueCluster).all()
        if not clusters:
            return []

        scored_pairs: List[Tuple[IssueCluster, OpportunityScore]] = []
        for cluster in clusters:
            opp_score = self.score_cluster(cluster, weights=weights)
            scored_pairs.append((cluster, opp_score))

        # Sort descending by composite score
        scored_pairs.sort(key=lambda pair: pair[1].composite_priority_score, reverse=True)
        total = len(scored_pairs)

        # Generate rationales with ranks
        for rank, (cluster, opp_score) in enumerate(scored_pairs, start=1):
            rationale = OpportunityExplainer.generate_rationale(
                score=opp_score,
                cluster=cluster,
                rank=rank,
                total_clusters=total,
            )
            opp_score.score_rationale = rationale

        if persist:
            for cluster, opp_score in scored_pairs:
                existing = session.query(OpportunityScore).filter_by(cluster_id=cluster.id).first()
                if existing:
                    existing.frequency_score = opp_score.frequency_score
                    existing.severity_score = opp_score.severity_score
                    existing.business_relevance_score = opp_score.business_relevance_score
                    existing.evidence_confidence_score = opp_score.evidence_confidence_score
                    existing.actionability_score = opp_score.actionability_score
                    existing.implementation_effort_score = opp_score.implementation_effort_score
                    existing.composite_priority_score = opp_score.composite_priority_score
                    existing.score_rationale = opp_score.score_rationale
                    existing.last_calculated_at = datetime.now(timezone.utc)
                else:
                    session.add(opp_score)
            session.commit()

        return scored_pairs
