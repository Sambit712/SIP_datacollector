"""Rationale & PM Explainer Engine for Opportunity Prioritization.

Generates transparent, plain-language PM rationale tooltips, executive summaries,
and auditable score breakdowns for every ranked problem cluster.
"""

from typing import Any, Dict, List, Optional


class OpportunityExplainer:
    """Generates transparent PM rationales explaining cluster priority rankings."""

    @staticmethod
    def generate_rationale(
        score: Any,
        cluster: Any,
        rank: int = 1,
        total_clusters: int = 1,
        source_counts: Optional[Dict[str, int]] = None,
    ) -> str:
        """Generates a cohesive plain-language rationale paragraph for the PM dashboard.

        Args:
            score: OpportunityScore instance or dict with score attributes.
            cluster: IssueCluster instance or dict.
            rank: 1-indexed rank of this opportunity.
            total_clusters: Total number of evaluated problem clusters.
            source_counts: Optional dictionary of channel counts.

        Returns:
            Human-readable multi-sentence PM rationale.
        """
        composite = getattr(score, "composite_priority_score", 0.0)
        biz = getattr(score, "business_relevance_score", 0.0)
        sev = getattr(score, "severity_score", 0.0)
        act = getattr(score, "actionability_score", 0.0)
        conf = getattr(score, "evidence_confidence_score", 0.0)
        freq = getattr(score, "frequency_score", 0.0)
        eff = getattr(score, "implementation_effort_score", 0.0)

        theme = getattr(cluster, "theme_title", "Problem Cluster")
        tier = getattr(cluster, "evidence_tier", "moderate")

        lines: List[str] = []
        lines.append(f"Ranked #{rank} of {total_clusters} (Composite Priority: {composite:.2f}/1.00).")

        # Key drivers
        drivers = []
        if biz >= 0.75:
            drivers.append(f"critical business relevance to 12-month retention ({biz:.2f})")
        if act >= 0.75:
            drivers.append(f"high Groww product actionability ({act:.2f})")
        if sev >= 0.75:
            drivers.append(f"high user financial friction ({sev:.2f})")
        if conf >= 0.80:
            drivers.append(f"verified {tier} evidence backing ({conf:.2f})")

        if drivers:
            lines.append(f"Primary ranking drivers: {', '.join(drivers)}.")
        else:
            lines.append("Scored moderately across all evaluation dimensions.")

        # Frequency & Damping context
        if source_counts:
            n_reddit = source_counts.get("reddit", 0)
            n_official = source_counts.get("official_doc", 0)
            n_int = source_counts.get("interview", 0)
            if n_official > 0:
                lines.append(
                    f"Corroborated by official regulatory data ({n_official} doc(s)) and {n_int} in-depth interview(s), "
                    f"yielding a robust damped frequency score of {freq:.2f} resistant to forum skew."
                )
            elif n_reddit > 10:
                lines.append(
                    f"High social volume ({n_reddit} Reddit/review posts) logarithmically damped to {freq:.2f} "
                    f"to avoid vocal minority distortion."
                )
        else:
            if freq >= 0.60:
                lines.append(f"Strong cross-channel corroboration (damped frequency: {freq:.2f}).")
            else:
                lines.append(f"Controlled frequency weight ({freq:.2f}) prevents social volume distortion.")

        # Feasibility / Drag factor
        if eff <= 0.35:
            lines.append(f"Favorable ROI with low implementation effort ({eff:.2f}).")
        elif eff >= 0.70:
            lines.append(
                f"Implementation effort ({eff:.2f}) represents a noticeable engineering investment "
                f"that slightly moderates final priority."
            )

        return " ".join(lines)

    @staticmethod
    def generate_card_summary(score: Any, cluster: Any, rank: int = 1) -> Dict[str, Any]:
        """Provides structured highlight tags and metrics for UI rendering."""
        composite = getattr(score, "composite_priority_score", 0.0)
        biz = getattr(score, "business_relevance_score", 0.0)
        act = getattr(score, "actionability_score", 0.0)
        eff = getattr(score, "implementation_effort_score", 0.0)
        sev = getattr(score, "severity_score", 0.0)

        positives = []
        if biz >= 0.70:
            positives.append(f"High Retention Impact ({biz:.0%})")
        if act >= 0.70:
            positives.append(f"Direct Product Control ({act:.0%})")
        if sev >= 0.70:
            positives.append(f"Severe User Pain ({sev:.0%})")
        if eff <= 0.35:
            positives.append("Quick Win (Low Effort)")

        cautions = []
        if eff >= 0.70:
            cautions.append("High Dev/Integration Complexity")
        if act <= 0.40:
            cautions.append("External Partner/Regulatory Dependency")
        if biz <= 0.40:
            cautions.append("Low Direct Impact on Churn")

        priority_tier = "Critical" if composite >= 0.75 else "High" if composite >= 0.60 else "Medium" if composite >= 0.45 else "Low"

        return {
            "rank": rank,
            "priority_tier": priority_tier,
            "composite_score": composite,
            "positives": positives,
            "cautions": cautions,
            "quick_win": eff <= 0.35 and act >= 0.70,
        }

