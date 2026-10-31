"""Human Reviewer Calibration Store & Performance Delta Calculator.

Enables Product Managers to:
1. Review AI misclassifications from benchmark runs.
2. Submit human ground-truth corrections or calibration notes.
3. Compute Before vs. After performance deltas (Δ Accuracy, Δ Macro-F1).
4. Export calibrated golden datasets.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from config.settings import get_settings
from src.models.database import EvaluationRun, GoldenRecord, RawRecord

logger = logging.getLogger("ai_discovery_engine.calibrator")


class CalibrationStore:
    """Manages human-in-the-loop review, record correction, and before/after comparisons."""

    @staticmethod
    def submit_correction(
        session: Session,
        golden_record_id: str,
        new_expected_category_id: str,
        reviewer_notes: str,
        annotator_id: str = "lead_pm_reviewer",
    ) -> GoldenRecord:
        """Applies a human reviewer correction to a Golden Benchmark record.

        Args:
            session: Active database session.
            golden_record_id: ID of the GoldenRecord to correct.
            new_expected_category_id: Updated ground truth category ID (e.g. cat_01).
            reviewer_notes: Explanation of why the ground truth was updated.
            annotator_id: Name or ID of the reviewer.

        Returns:
            Updated GoldenRecord instance.
        """
        record = session.query(GoldenRecord).filter_by(id=golden_record_id).first()
        if not record:
            raise ValueError(f"GoldenRecord with ID '{golden_record_id}' not found.")

        old_cat = record.expected_category_id
        record.expected_category_id = new_expected_category_id
        record.reviewer_notes = (
            f"[Correction {datetime.now(timezone.utc).strftime('%Y-%m-%d')} by {annotator_id}] "
            f"Changed from {old_cat} to {new_expected_category_id}. Notes: {reviewer_notes}"
        )
        record.annotator_id = annotator_id

        session.commit()
        logger.info(f"Golden record {golden_record_id} corrected: {old_cat} -> {new_expected_category_id}")

        # Update disk export file
        CalibrationStore.export_calibrated_golden_set(session)
        return record

    @staticmethod
    def compute_before_after_delta(
        previous_run: Dict[str, Any],
        current_run: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculates performance deltas between two evaluation runs.

        Args:
            previous_run: Dictionary from earlier BenchmarkRunner.run_evaluation().
            current_run: Dictionary from latest BenchmarkRunner.run_evaluation().

        Returns:
            Dict containing delta metrics and resolved/broken record diffs.
        """
        prev_acc = previous_run.get("overall_accuracy", 0.0)
        curr_acc = current_run.get("overall_accuracy", 0.0)
        delta_acc = round(curr_acc - prev_acc, 4)

        prev_f1 = previous_run.get("macro_f1", 0.0)
        curr_f1 = current_run.get("macro_f1", 0.0)
        delta_f1 = round(curr_f1 - prev_f1, 4)

        prev_rel_acc = previous_run.get("relevance_accuracy", 0.0)
        curr_rel_acc = current_run.get("relevance_accuracy", 0.0)
        delta_rel_acc = round(curr_rel_acc - prev_rel_acc, 4)

        # Compare misclassifications
        prev_failed_ids = {
            m.get("raw_record_id") for m in previous_run.get("misclassifications", [])
        }
        curr_failed_ids = {
            m.get("raw_record_id") for m in current_run.get("misclassifications", [])
        }

        resolved_records = list(prev_failed_ids - curr_failed_ids)
        regressed_records = list(curr_failed_ids - prev_failed_ids)

        summary_message = (
            f"Overall Accuracy: {prev_acc * 100:.1f}% -> {curr_acc * 100:.1f}% "
            f"({'▲ +' if delta_acc >= 0 else '▼ '}{delta_acc * 100:.1f}%). "
            f"Macro-F1: {prev_f1:.3f} -> {curr_f1:.3f} "
            f"({'▲ +' if delta_f1 >= 0 else '▼ '}{delta_f1:.3f})."
        )

        return {
            "previous_accuracy": prev_acc,
            "current_accuracy": curr_acc,
            "delta_accuracy": delta_acc,
            "previous_macro_f1": prev_f1,
            "current_macro_f1": curr_f1,
            "delta_macro_f1": delta_f1,
            "delta_relevance_accuracy": delta_rel_acc,
            "resolved_count": len(resolved_records),
            "regressed_count": len(regressed_records),
            "resolved_record_ids": resolved_records,
            "regressed_record_ids": regressed_records,
            "summary": summary_message,
        }

    @staticmethod
    def export_calibrated_golden_set(
        session: Session,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Exports the current calibrated Golden Benchmark records to JSON."""
        settings = get_settings()
        dest = output_path or (settings.DATA_DIR / "golden" / "benchmark_25.json")
        dest.parent.mkdir(parents=True, exist_ok=True)

        records = (
            session.query(GoldenRecord, RawRecord)
            .join(RawRecord, GoldenRecord.raw_record_id == RawRecord.id)
            .all()
        )

        export_data = []
        for g, r in records:
            export_data.append({
                "raw_record_id": r.id,
                "raw_text": r.raw_text,
                "platform": r.platform,
                "source_type": r.source_type,
                "expected_relevance": g.expected_relevance,
                "expected_category_id": g.expected_category_id,
                "expected_journey_stage": g.expected_journey_stage,
                "expected_first_hand": g.expected_first_hand,
                "expected_sip_status": g.expected_sip_status,
                "expected_stated_reason": g.expected_stated_reason,
                "reviewer_notes": g.reviewer_notes,
                "annotator_id": g.annotator_id,
            })

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return dest

