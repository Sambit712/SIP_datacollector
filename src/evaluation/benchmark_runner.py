"""Golden Benchmark Evaluation Harness.

Executes extraction and classification pipelines against the 25-record
hand-annotated Golden Benchmark dataset. Computes Accuracy, Macro-F1,
per-category Precision/Recall, 13x13 Confusion Matrix, and detects
unsupported claims/hallucinations.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from config.settings import get_settings
from src.models.database import (
    EvaluationRun,
    GoldenRecord,
    IssueCategory,
    RawRecord,
    generate_uuid,
    get_session,
)
from src.nlp.fallback_engine import FallbackEngine
from src.nlp.llm_client import GroqLLMClient
from src.nlp.pipeline import AnalysisPipeline

logger = logging.getLogger("ai_discovery_engine.evaluation")


class BenchmarkRunner:
    """Automated benchmark test harness for AI extraction & classification accuracy."""

    def __init__(
        self,
        session: Optional[Session] = None,
        llm_client: Optional[GroqLLMClient] = None,
    ):
        self.session = session or get_session()
        self.llm = llm_client or GroqLLMClient()
        self.pipeline = AnalysisPipeline(self.llm)
        self.taxonomy = FallbackEngine.get_taxonomy()
        self.category_codes = [c["code"] for c in self.taxonomy]
        self.category_ids = [c["id"] for c in self.taxonomy]
        self.code_to_id = {c["code"]: c["id"] for c in self.taxonomy}
        self.id_to_code = {c["id"]: c["code"] for c in self.taxonomy}

    def load_golden_records(self) -> List[Dict[str, Any]]:
        """Loads golden records from DB or JSON file fallback."""
        records = (
            self.session.query(GoldenRecord, RawRecord)
            .join(RawRecord, GoldenRecord.raw_record_id == RawRecord.id)
            .all()
        )

        if records:
            items = []
            for g, r in records:
                items.append({
                    "raw_record_id": r.id,
                    "raw_text": r.raw_text,
                    "sanitized_text": r.sanitized_text,
                    "platform": r.platform,
                    "source_type": r.source_type,
                    "expected_relevance": g.expected_relevance,
                    "expected_category_id": g.expected_category_id,
                    "expected_journey_stage": g.expected_journey_stage,
                    "expected_first_hand": g.expected_first_hand,
                    "expected_sip_status": g.expected_sip_status,
                    "expected_stated_reason": g.expected_stated_reason,
                    "reviewer_notes": g.reviewer_notes,
                })
            return items

        # Fallback to benchmark_25.json on disk
        settings = get_settings()
        json_path = settings.DATA_DIR / "golden" / "benchmark_25.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return []

    def run_evaluation(self, save_to_db: bool = True) -> Dict[str, Any]:
        """Executes full evaluation suite against the 25 golden benchmark records.

        Returns:
            Dictionary containing accuracy, macro-F1, confusion matrix, and misclassification diffs.
        """
        golden_set = self.load_golden_records()
        if not golden_set:
            raise ValueError("No golden benchmark records found in database or data/golden/benchmark_25.json.")

        total = len(golden_set)
        correct_categories = 0
        correct_relevance = 0
        unsupported_claims_count = 0
        detailed_diffs: List[Dict[str, Any]] = []

        # Initialize 13x13 Confusion Matrix: {expected_id: {predicted_id: count}}
        confusion_matrix: Dict[str, Dict[str, int]] = {
            exp_id: {pred_id: 0 for pred_id in self.category_ids}
            for exp_id in self.category_ids
        }

        # Per-category stats: {cat_id: {"tp": int, "fp": int, "fn": int}}
        category_stats: Dict[str, Dict[str, int]] = {
            cat_id: {"tp": 0, "fp": 0, "fn": 0} for cat_id in self.category_ids
        }

        model_name = (
            f"groq:{self.llm.primary_model}"
            if self.llm.is_available
            else "deterministic_fallback_engine"
        )

        for item in golden_set:
            raw_text = item.get("sanitized_text") or item["raw_text"]
            platform = item.get("platform", "Groww")
            expected_cat_id = item["expected_category_id"]
            expected_relevance = item["expected_relevance"]

            # 1. Pipeline Relevance Prediction
            pred_relevance, _, _ = self.pipeline.relevance_filter.classify_record(raw_text)
            if pred_relevance == expected_relevance:
                correct_relevance += 1

            # 2. Pipeline Complaint Extraction
            extracted_issue = self.pipeline.extractor.extract_issue(raw_text, platform=platform)

            # Substring verification test: Check for hallucinated quotes
            is_substring_verified = extracted_issue.verbatim_excerpt in raw_text
            if not is_substring_verified:
                unsupported_claims_count += 1

            # 3. Pipeline Category Classification
            pred_cat_id, pred_code, conf, is_emergent = self.pipeline.classifier.classify(
                extracted_issue.verbatim_excerpt,
                extracted_issue.core_problem,
            )

            # Update Confusion Matrix
            if expected_cat_id in confusion_matrix and pred_cat_id in confusion_matrix[expected_cat_id]:
                confusion_matrix[expected_cat_id][pred_cat_id] += 1

            # Check Match
            is_cat_correct = (pred_cat_id == expected_cat_id)
            if is_cat_correct:
                correct_categories += 1
                category_stats[expected_cat_id]["tp"] += 1
            else:
                category_stats[expected_cat_id]["fn"] += 1
                if pred_cat_id in category_stats:
                    category_stats[pred_cat_id]["fp"] += 1

                detailed_diffs.append({
                    "raw_record_id": item.get("raw_record_id"),
                    "raw_text_snippet": raw_text[:140] + "...",
                    "expected_category_id": expected_cat_id,
                    "expected_category_name": self.id_to_code.get(expected_cat_id, expected_cat_id),
                    "predicted_category_id": pred_cat_id,
                    "predicted_category_name": self.id_to_code.get(pred_cat_id, pred_cat_id),
                    "extracted_problem": extracted_issue.core_problem,
                    "verbatim_excerpt": extracted_issue.verbatim_excerpt,
                    "is_substring_verified": is_substring_verified,
                    "reviewer_notes": item.get("reviewer_notes"),
                })

        # Calculate Macro Metrics
        overall_accuracy = correct_categories / total if total > 0 else 0.0
        relevance_accuracy = correct_relevance / total if total > 0 else 0.0

        precisions = []
        recalls = []
        f1_scores = []

        per_category_metrics: Dict[str, Dict[str, float]] = {}
        for cat_id, stats in category_stats.items():
            tp = stats["tp"]
            fp = stats["fp"]
            fn = stats["fn"]

            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

            per_category_metrics[cat_id] = {
                "name": self.id_to_code.get(cat_id, cat_id),
                "precision": round(p, 4),
                "recall": round(r, 4),
                "f1": round(f1, 4),
                "support": tp + fn,
            }

            # Only include categories present in the golden dataset for macro averages
            if (tp + fn) > 0:
                precisions.append(p)
                recalls.append(r)
                f1_scores.append(f1)

        macro_precision = sum(precisions) / len(precisions) if precisions else 0.0
        macro_recall = sum(recalls) / len(recalls) if recalls else 0.0
        macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

        results = {
            "total_evaluated": total,
            "overall_accuracy": round(overall_accuracy, 4),
            "relevance_accuracy": round(relevance_accuracy, 4),
            "macro_precision": round(macro_precision, 4),
            "macro_recall": round(macro_recall, 4),
            "macro_f1": round(macro_f1, 4),
            "unsupported_claims_count": unsupported_claims_count,
            "confusion_matrix": confusion_matrix,
            "per_category_metrics": per_category_metrics,
            "misclassifications": detailed_diffs,
            "model_used": model_name,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist EvaluationRun to database
        if save_to_db:
            run_record = EvaluationRun(
                id=generate_uuid(),
                executed_at=datetime.now(timezone.utc),
                total_records_evaluated=total,
                accuracy=round(overall_accuracy, 4),
                macro_precision=round(macro_precision, 4),
                macro_recall=round(macro_recall, 4),
                macro_f1=round(macro_f1, 4),
                confusion_matrix_json=json.dumps(confusion_matrix),
                misclassification_diffs=json.dumps(detailed_diffs),
                model_used=model_name,
            )
            self.session.add(run_record)
            self.session.commit()
            results["evaluation_run_id"] = run_record.id

        return results

