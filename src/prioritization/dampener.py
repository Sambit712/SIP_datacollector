"""Frequency Damping & Anti-Vocal-Minority Dampener Engine.

Prevents vocal minority bias on social media (e.g., hundreds of Reddit rants
or App Store 1-star reviews) from artificially outweighing critical issues
corroborated by official regulatory data (SEBI, AMFI) or in-depth user interviews.

Mathematical formulation:
    S_freq = min(1.0, (ln(1 + N_social) + 2.5 * ln(1 + N_interviews) + 5.0 * I_official) / Scale_Factor)
"""

import math
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("ai_discovery_engine.prioritization.dampener")

DEFAULT_SCALE_FACTOR = 10.0


class FrequencyDampener:
    """Calculates logarithmically damped frequency scores to eliminate vocal-minority bias."""

    def __init__(self, scale_factor: float = DEFAULT_SCALE_FACTOR):
        """Initializes the dampener with a scale factor normalization constant.
        
        Args:
            scale_factor: Normalization divisor (default 10.0) mapping the composite
                          frequency evidence onto [0.0, 1.0].
        """
        self.scale_factor = max(1.0, float(scale_factor))

    def calculate_damped_frequency(
        self,
        n_reddit: int = 0,
        n_interviews: int = 0,
        has_official: bool = False,
        n_app_store: int = 0,
        n_news: int = 0,
        scale_factor: Optional[float] = None,
    ) -> float:
        """Calculates normalized damped frequency score using the anti-vocal-minority formula.

        Args:
            n_reddit: Count of Reddit / forum mentions.
            n_interviews: Count of validated in-depth user interview transcripts.
            has_official: Whether the problem is corroborated by official regulatory
                          reports (e.g. SEBI, AMFI).
            n_app_store: Count of App Store / Play Store reviews.
            n_news: Count of verified financial news reports.
            scale_factor: Optional scale factor override.

        Returns:
            Damped frequency score in [0.0, 1.0].
        """
        factor = scale_factor if scale_factor is not None else self.scale_factor
        factor = max(1.0, float(factor))

        # Social volume combines Reddit and App Store reviews
        n_social = max(0, n_reddit) + max(0, int(n_app_store * 0.8)) + max(0, int(n_news * 0.5))
        n_interviews = max(0, n_interviews)
        i_official = 1.0 if has_official else 0.0

        # Anti-vocal-minority logarithmic damping
        social_term = math.log1p(n_social)
        interview_term = 2.5 * math.log1p(n_interviews)
        official_term = 5.0 * i_official

        raw_score = (social_term + interview_term + official_term) / factor
        return round(min(1.0, max(0.0, raw_score)), 4)

    def calculate_from_counts(
        self,
        counts: Dict[str, int],
        scale_factor: Optional[float] = None,
    ) -> float:
        """Convenience method accepting a dictionary of channel counts.

        Supported keys: 'reddit', 'app_store', 'interview', 'official_doc', 'news'.
        """
        n_reddit = counts.get("reddit", 0)
        n_app_store = counts.get("app_store", 0)
        n_interviews = counts.get("interview", 0)
        n_official = counts.get("official_doc", 0)
        n_news = counts.get("news", 0)
        has_official = n_official > 0

        return self.calculate_damped_frequency(
            n_reddit=n_reddit,
            n_interviews=n_interviews,
            has_official=has_official,
            n_app_store=n_app_store,
            n_news=n_news,
            scale_factor=scale_factor,
        )

    def calculate_for_cluster(
        self,
        cluster: Any,
        scale_factor: Optional[float] = None,
    ) -> float:
        """Extracts channel distribution from an IssueCluster instance and returns damped score.

        Traverses cluster.extracted_issues -> raw_record.source_type.
        """
        counts: Dict[str, int] = {
            "reddit": 0,
            "app_store": 0,
            "interview": 0,
            "official_doc": 0,
            "news": 0,
        }

        issues = getattr(cluster, "extracted_issues", []) or []
        for issue in issues:
            raw_record = getattr(issue, "raw_record", None)
            if raw_record and hasattr(raw_record, "source_type"):
                st = raw_record.source_type
                if st in counts:
                    counts[st] += 1
                else:
                    counts[st] = 1

        # If supporting_record_count is set but extracted_issues list wasn't eagerly loaded
        if not issues and getattr(cluster, "supporting_record_count", 0) > 0:
            counts["reddit"] = cluster.supporting_record_count

        return self.calculate_from_counts(counts, scale_factor=scale_factor)

