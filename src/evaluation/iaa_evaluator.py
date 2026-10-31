"""Inter-Annotator Agreement (IAA) Evaluator.

Calculates Cohen's Kappa (κ) to measure statistical agreement between
multiple human annotators or between human benchmarks and automated classifiers.
Guarantees ground-truth consistency before evaluating AI performance.
"""

from typing import Any, Dict, List, Tuple


class IAAEvaluator:
    """Calculates inter-rater reliability metrics."""

    @staticmethod
    def compute_cohens_kappa(rater1_labels: List[str], rater2_labels: List[str]) -> Tuple[float, str]:
        """Computes Cohen's Kappa (κ) between two label sequences.

        Formula:
            κ = (p_o - p_e) / (1 - p_e)
        Where:
            p_o: Relative observed agreement among raters.
            p_e: Hypothetical probability of chance agreement.

        Args:
            rater1_labels: First annotator's categorical assignments.
            rater2_labels: Second annotator's categorical assignments.

        Returns:
            Tuple of (kappa_score, interpretation_string).
        """
        if len(rater1_labels) != len(rater2_labels) or not rater1_labels:
            raise ValueError("Label lists must be non-empty and of identical length.")

        n = len(rater1_labels)
        categories = sorted(list(set(rater1_labels) | set(rater2_labels)))

        # 1. Observed agreement (p_o)
        agree_count = sum(1 for a, b in zip(rater1_labels, rater2_labels) if a == b)
        p_o = agree_count / n

        # 2. Expected agreement by chance (p_e)
        p_e = 0.0
        for cat in categories:
            count1 = sum(1 for label in rater1_labels if label == cat)
            count2 = sum(1 for label in rater2_labels if label == cat)
            p_e += (count1 / n) * (count2 / n)

        # 3. Kappa Calculation
        if p_e >= 1.0:
            kappa = 1.0
        elif (1.0 - p_e) == 0:
            kappa = 0.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

        interpretation = IAAEvaluator.interpret_kappa(kappa)
        return round(kappa, 4), interpretation

    @staticmethod
    def interpret_kappa(kappa: float) -> str:
        """Interprets Cohen's Kappa according to Landis & Koch (1977) scale."""
        if kappa < 0.0:
            return "Poor agreement (less than chance)"
        elif kappa <= 0.20:
            return "Slight agreement"
        elif kappa <= 0.40:
            return "Fair agreement"
        elif kappa <= 0.60:
            return "Moderate agreement"
        elif kappa <= 0.80:
            return "Substantial agreement"
        else:
            return "Almost perfect agreement"

    @staticmethod
    def resolve_disagreements(
        records: List[Dict[str, Any]],
        rater1_key: str = "label_rater1",
        rater2_key: str = "label_rater2",
        arbitrator_key: str = "arbitrated_label",
    ) -> List[Dict[str, Any]]:
        """Identifies disagreements and assigns arbitrated ground truth."""
        resolved = []
        for r in records:
            item = dict(r)
            l1 = item.get(rater1_key)
            l2 = item.get(rater2_key)
            if l1 == l2:
                item[arbitrator_key] = l1
                item["has_disagreement"] = False
            else:
                # If explicit arbitration provided, keep it; otherwise default to rater1
                item[arbitrator_key] = item.get(arbitrator_key) or l1
                item["has_disagreement"] = True
            resolved.append(item)
        return resolved

