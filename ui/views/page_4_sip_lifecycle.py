"""Page 4: SIP Lifecycle & 12-Month Discontinuation Funnel."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import ExtractedIssue, RawRecord


def render(session: Session, filters: dict):
    """Renders the 6-stage SIP user journey funnel and 12-month persistency drop-off analysis."""
    st.title("🔄 SIP 12-Month Lifecycle & Churn Funnel")
    st.caption("Mapping user friction and abandonment triggers across the 6 investment journey stages.")

    issues = session.query(ExtractedIssue).all()

    stages_order = [
        ("pre_sip", "1. Pre-SIP Discovery", "Onboarding & Fund Selection", "#0284c7"),
        ("setup", "2. Setup & Mandate", "Bank AutoPay / NPCI e-Mandate", "#0891b2"),
        ("active", "3. Active Investing", "Monthly Debits & Tracking", "#059669"),
        ("instalment_failed", "4. Instalment Failed", "Insufficient Balance / Bank Error", "#ea580c"),
        ("life_event", "5. Liquidity Shock", "Job Change / Urgent Cash Need", "#d97706"),
        ("churned", "6. Churned / Discontinued", "SIP Cancelled / Account Dormant", "#dc2626"),
    ]

    stage_counts = {s[0]: 0 for s in stages_order}
    for i in issues:
        stg = i.journey_stage
        if stg in stage_counts:
            stage_counts[stg] += 1
        else:
            stage_counts["active"] += 1

    # Stage funnel summary columns
    cols = st.columns(6)
    for idx, (code, title, desc, color) in enumerate(stages_order):
        with cols[idx]:
            count = stage_counts[code]
            st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #cbd5e1; border-top: 4px solid {color}; border-radius: 6px; padding: 10px; text-align: center; margin-bottom: 10px;">
                <div style="font-size: 0.72rem; font-weight: 700; color: #475569;">{title}</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #0f172a; margin: 4px 0;">{count}</div>
                <div style="font-size: 0.7rem; color: #64748b;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Stage Deep Dive
    st.subheader("🔍 Friction Deep-Dive by Journey Stage")
    selected_stage = st.selectbox(
        "Select Journey Stage to analyze specific issues:",
        [s[0] for s in stages_order],
        format_func=lambda x: next(s[1] for s in stages_order if s[0] == x),
    )

    stage_issues = [i for i in issues if i.journey_stage == selected_stage]
    st.write(f"Showing **{len(stage_issues)}** extracted complaints in `{selected_stage}` stage:")

    if stage_issues:
        for idx, issue in enumerate(stage_issues[:10], start=1):
            with st.container():
                st.markdown(
                    f"**{idx}. {issue.core_problem}** (Severity: `{issue.severity_level.upper()}`)  \n"
                    f"*Verbatim Excerpt:* \"{issue.verbatim_excerpt}\""
                )
                if issue.stated_discontinuation_reason:
                    st.caption(f"Stated Churn Reason: {issue.stated_discontinuation_reason}")
                st.divider()
    else:
        st.info("No issues recorded under this journey stage.")

