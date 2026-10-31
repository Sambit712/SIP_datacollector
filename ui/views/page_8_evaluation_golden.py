"""Page 8: Golden Benchmark Evaluation & Human-in-the-Loop Calibration."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import GoldenRecord, EvaluationRun, IssueCategory
from src.evaluation.benchmark_runner import BenchmarkRunner
from src.evaluation.calibrator import CalibrationStore


def render(session: Session, filters: dict):
    """Renders the AI Golden Benchmark evaluation dashboard, confusion matrix, and human-in-the-loop correction editor."""
    st.title("🎯 AI Golden Benchmark & HITL Calibration")
    st.caption("25-record curated ground truth evaluation suite, 13x13 category confusion matrix, and prompt calibration loop.")

    runner = BenchmarkRunner(session)

    golden_count = session.query(GoldenRecord).count()
    st.write(f"Benchmark Dataset Size: **{golden_count}** Curated Ground Truth Records")

    # Run Benchmark Action
    col_act1, col_act2 = st.columns([1, 3])
    with col_act1:
        if st.button("🚀 Run Benchmark Evaluation", type="primary"):
            with st.spinner("Evaluating AI Pipeline against 25 Golden Records..."):
                run = runner.run_evaluation(use_offline_fallback=True)
                st.success(f"Benchmark completed! Accuracy: {run.accuracy:.1%}")
                st.rerun()

    # Fetch latest evaluation run
    latest_run = session.query(EvaluationRun).order_by(EvaluationRun.executed_at.desc()).first()

    if not latest_run:
        st.info("No benchmark evaluation has been run yet. Click 'Run Benchmark Evaluation' above.")
        return

    # Scorecards
    st.subheader("📊 Accuracy & Performance Scorecards")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Macro Accuracy", f"{latest_run.accuracy:.1%}")
    with m2:
        st.metric("Macro Precision", f"{latest_run.macro_precision:.1%}")
    with m3:
        st.metric("Macro Recall", f"{latest_run.macro_recall:.1%}")
    with m4:
        st.metric("Macro F1-Score", f"{latest_run.macro_f1:.1%}")

    st.markdown("---")

    # Confusion Matrix
    st.subheader("🔲 13x13 Category Confusion Matrix")
    import json
    raw_cm = getattr(latest_run, "confusion_matrix_json", None) or getattr(latest_run, "confusion_matrix", {})
    if isinstance(raw_cm, str):
        try:
            cm = json.loads(raw_cm)
        except Exception:
            cm = {}
    elif isinstance(raw_cm, dict):
        cm = raw_cm
    else:
        cm = {}

    if cm:
        cat_codes = sorted(cm.keys())
        df_cm = pd.DataFrame(index=cat_codes, columns=cat_codes)
        for expected, row in cm.items():
            for pred, count in row.items():
                df_cm.loc[expected, pred] = count
        df_cm = df_cm.fillna(0).astype(int)
        st.dataframe(df_cm, use_container_width=True)
    else:
        st.caption("Confusion matrix data not recorded.")

    st.markdown("---")

    # Human-in-the-loop Benchmark Editor
    st.subheader("✍️ Human-in-the-Loop Ground Truth Editor")
    golden_records = session.query(GoldenRecord).all()
    categories = {c.id: f"{c.code} ({c.name})" for c in session.query(IssueCategory).all()}

    if golden_records:
        rec_options = {f"Golden #{idx+1} [ID: {g.id[:8]}] - {g.raw_record.sanitized_text[:60]}...": g for idx, g in enumerate(golden_records)}
        selected_key = st.selectbox("Select Golden Record to review or calibrate:", list(rec_options.keys()))

        if selected_key:
            selected_g = rec_options[selected_key]
            st.markdown(f"**Raw Text:** *\"{selected_g.raw_record.sanitized_text}\"*")

            c_edit1, c_edit2 = st.columns(2)
            with c_edit1:
                cur_cat = selected_g.expected_category_id
                cat_keys = list(categories.keys())
                cur_idx = cat_keys.index(cur_cat) if cur_cat in cat_keys else 0
                new_cat = st.selectbox("Expected Category:", cat_keys, index=cur_idx, format_func=lambda x: categories.get(x, x))
                new_stage = st.selectbox(
                    "Expected Journey Stage:",
                    ["pre_sip", "setup", "active", "instalment_failed", "life_event", "churned"],
                    index=["pre_sip", "setup", "active", "instalment_failed", "life_event", "churned"].index(selected_g.expected_journey_stage) if selected_g.expected_journey_stage in ["pre_sip", "setup", "active", "instalment_failed", "life_event", "churned"] else 0,
                )

            with c_edit2:
                new_notes = st.text_input("Reviewer Calibration Notes:", value=selected_g.reviewer_notes or "")
                annotator = st.text_input("Annotator ID:", value=selected_g.annotator_id or "lead_pm")

            if st.button("Submit Ground Truth Calibration", type="primary"):
                CalibrationStore.submit_correction(
                    session=session,
                    golden_record_id=selected_g.id,
                    new_expected_category_id=new_cat,
                    reviewer_notes=new_notes,
                    annotator_id=annotator,
                )
                st.success("Ground truth record updated successfully! Run benchmark to measure delta.")
                st.rerun()
