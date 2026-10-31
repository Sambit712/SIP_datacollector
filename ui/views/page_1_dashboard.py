"""Page 1: Executive Research Dashboard."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import RawRecord, ExtractedIssue, IssueCluster, OpportunityScore, IssueCategory
from ui.components.metrics import render_kpi_card


def render(session: Session, filters: dict):
    """Renders the macro KPI dashboard and source distribution overview."""
    st.title("📊 Executive Research Dashboard")
    st.caption("AI-Powered Discovery Engine investigating 12-Month Mutual Fund SIP Persistency on Groww")

    # Apply global channel/platform filters
    raw_query = session.query(RawRecord)
    if filters.get("channels"):
        raw_query = raw_query.filter(RawRecord.source_type.in_(filters["channels"]))
    if filters.get("platforms"):
        raw_query = raw_query.filter(RawRecord.platform.in_(filters["platforms"]))

    raw_records = raw_query.all()
    record_ids = [r.id for r in raw_records]

    # Filtered issues
    issue_query = session.query(ExtractedIssue)
    if record_ids:
        issue_query = issue_query.filter(ExtractedIssue.raw_record_id.in_(record_ids))
    issues = issue_query.all()

    clusters = session.query(IssueCluster).all()
    categories = {c.id: c.name for c in session.query(IssueCategory).all()}

    # --- Macro KPIs ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card(
            title="Ingested Records",
            value=str(len(raw_records)),
            subtitle="Across 5 research channels",
            border_color="#0284c7",
        )
    with c2:
        render_kpi_card(
            title="Extracted Issues",
            value=str(len(issues)),
            subtitle="Verified exact excerpts",
            border_color="#047857",
        )
    with c3:
        render_kpi_card(
            title="Problem Clusters",
            value=str(len(clusters)),
            subtitle="Synthesized friction themes",
            border_color="#7c3aed",
        )
    with c4:
        groww_pct = round(sum(1 for i in issues if i.mentions_groww) / max(1, len(issues)) * 100, 1)
        render_kpi_card(
            title="Groww Platform Mentions",
            value=f"{groww_pct}%",
            subtitle=f"{sum(1 for i in issues if i.mentions_groww)} direct issues",
            border_color="#ea580c",
        )

    st.markdown("---")

    # --- Two Columns for Charts ---
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("📁 Ingestion Inventory by Channel")
        ch_counts = {}
        for r in raw_records:
            ch_counts[r.source_type.replace("_", " ").title()] = ch_counts.get(r.source_type.replace("_", " ").title(), 0) + 1
        if ch_counts:
            df_ch = pd.DataFrame(list(ch_counts.items()), columns=["Source Channel", "Records"]).set_index("Source Channel")
            st.bar_chart(df_ch, color="#0284c7")
        else:
            st.info("No records match the active filter.")

    with col_right:
        st.subheader("🏷️ Category Distribution")
        cat_counts = {}
        for i in issues:
            c_name = categories.get(i.category_id, "Unclassified")
            cat_counts[c_name] = cat_counts.get(c_name, 0) + 1
        if cat_counts:
            df_cat = pd.DataFrame(list(cat_counts.items()), columns=["Category", "Issues"]).sort_values("Issues", ascending=False).set_index("Category")
            st.bar_chart(df_cat, color="#047857")
        else:
            st.info("No extracted issues match current filter.")

    # --- Recent Activity Stream ---
    st.markdown("---")
    st.subheader("🕒 Recent Research Ingestion Stream")
    stream_data = []
    for r in raw_records[:10]:
        stream_data.append({
            "Platform": r.platform,
            "Channel": r.source_type,
            "Title / Excerpt": (r.title or r.sanitized_text[:75] + "..."),
            "Relevance": r.relevance_status.replace("_", " ").title(),
            "Verified": "✅ Yes" if r.is_user_verified else "⏳ AI Classified",
        })

    if stream_data:
        st.dataframe(pd.DataFrame(stream_data), use_container_width=True, hide_index=True)
    else:
        st.info("No ingestion stream data available.")

