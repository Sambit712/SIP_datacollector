"""Epistemic Triangulation Engine.

Enforces strict ontological boundaries between:
- Observed Evidence: What the user or authoritative report explicitly stated.
- Interpretation: What the researcher infers may explain the observation.
- Hypothesis: What still requires validation and testing.

Prevents speculative AI claims from being presented to Product Managers as confirmed facts.
"""

from typing import Any, Dict, Literal, Tuple

EpistemicType = Literal["observed_evidence", "interpretation", "hypothesis"]


class EpistemicTriangulator:
    """Classifies claims and distinguishes verified facts from interpretations and hypotheses."""

    OBSERVED_MARKERS = [
        "i was charged", "deducted", "failed on", "my salary", "hospital",
        "error code", "sebi survey", "amfi data", "groww app", "received", "cancelled",
    ]

    HYPOTHESIS_MARKERS = [
        "would have", "might help", "could reduce", "if groww", "we believe",
        "assumption", "hypothesis", "perhaps", "should implement", "probably",
    ]

    INTERPRETATION_MARKERS = [
        "likely due to", "indicates that", "suggests that", "root cause seems to be",
        "caused by", "reflects", "points to", "inferred",
    ]

    @classmethod
    def classify_claim(cls, text: str, is_first_hand: bool = True) -> Tuple[EpistemicType, str]:
        """Classifies the epistemic type of a claim or observation.

        Args:
            text: Text snippet or claim.
            is_first_hand: Whether the source describes first-hand lived experience.

        Returns:
            Tuple of (epistemic_type, rationale).
        """
        lower = text.lower()

        # Check hypothesis markers
        if any(h in lower for h in cls.HYPOTHESIS_MARKERS):
            return (
                "hypothesis",
                "Contains speculative or prospective intervention phrasing requiring product validation.",
            )

        # Check interpretation markers
        if any(i in lower for i in cls.INTERPRETATION_MARKERS):
            return (
                "interpretation",
                "Represents an explanatory inference linking observations to potential mechanisms.",
            )

        # First-hand lived experiences or regulatory survey data are observed evidence
        if is_first_hand or any(o in lower for o in cls.OBSERVED_MARKERS):
            return (
                "observed_evidence",
                "Explicitly stated lived user experience or documented regulatory observation.",
            )

        return (
            "observed_evidence",
            "Direct empirical observation from source text.",
        )

