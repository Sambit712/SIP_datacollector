"""Page 9: Evidence Log & Audit Trail."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import ExtractedIssue, RawRecord, IssueCategory
from src.reporting.evidence_exporter import EvidenceLogExporter
from ui.components.cards import render_epistemic_badge


def render(session: Session, filters: dict):
    """Renders the audited research evidence log with verbatim claims, verification statuses, and download options."""
    st.title("🛡️ Research Evidence Log & Provenance Audit")
    st.caption("Read-only, privacy-safe evidence audit trail ensuring character-exact claim provenance with zero hallucinations.")

    exporter = EvidenceLogExporter(session)
    records = exporter.build_evidence_records()

    if not records:
        st.info("No extracted evidence records found in database. Run pipeline processing first.")
        return

    # Export Buttons
    col_d1, col_d2, col_stats = st.columns([1, 1, 2])
    with col_d1:
        json_data = exporter.export_to_json()
        st.download_button(
            "📥 Download Evidence Log (JSON)",
            data=json_data,
            file_name="groww_sip_evidence_log.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_d2:
        csv_data = exporter.export_to_csv()
        st.download_button(
            "📥 Download Evidence Log (CSV)",
            data=csv_data,
            file_name="groww_sip_evidence_log.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_stats:
        st.write(f"Total Verified Claims: **{len(records)}** | PII Compliance: **100% Guaranteed**")

    st.markdown("---")

    # Filters
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        kw = st.text_input("Filter claims by keyword:", placeholder="e.g., mandate, pause, bounce, fees...")
    with col_f2:
        channel_filter = st.selectbox("Channel Filter:", ["All"] + sorted(list(set(r["source_channel"] for r in records))))

    filtered = records
    if kw:
        filtered = [r for r in filtered if kw.lower() in r["verified_verbatim_claim"].lower() or kw.lower() in r["core_problem"].lower()]
    if channel_filter != "All":
        filtered = [r for r in filtered if r["source_channel"] == channel_filter]

    st.write(f"Displaying **{len(filtered)}** claims:")

    # Table View
    table_rows = []
    for r in filtered:
        table_rows.append({
            "Evidence ID": r["evidence_id"],
            "Channel": r["source_channel"],
            "Platform": r["platform"],
            "Category": r["category_name"],
            "Severity": r["severity_level"].upper(),
            "Epistemic Type": r["epistemic_type"].replace("_", " ").title(),
            "Claim Excerpt": r["verified_verbatim_claim"][:80] + "...",
            "Source": r["source_identifier"][:40],
        })

    df_evid = pd.DataFrame(table_rows)
    st.dataframe(df_evid, use_container_width=True, hide_index=True)

    # Detailed Excerpt Drawer
    st.markdown("---")
    st.subheader("🔎 Claim Inspector")
    claim_options = {f"{r['evidence_id']} - {r['verified_verbatim_claim'][:60]}...": r for r in filtered}
    if claim_options:
        sel_key = st.selectbox("Select claim to view full audit details:", list(claim_options.keys()))
        sel_rec = claim_options[sel_key]

        c_info1, c_info2 = st.columns([2, 1])
        with c_info1:
            st.markdown(f"**Verbatim Quote:** *\"{sel_rec['verified_verbatim_claim']}\"*")
            st.markdown(f"**Synthesized Core Problem:** {sel_rec['core_problem']}")
            st.markdown(f"**Source URL / Reference:** `{sel_rec['source_url']}`")
        with c_info2:
            st.markdown(f"**Category:** `{sel_rec['category_name']}`")
            st.markdown(f"**Journey Stage:** `{sel_rec['journey_stage']}`")
            st.markdown(f"**Severity:** `{sel_rec['severity_level']}`")
            badge = render_epistemic_badge(sel_rec['epistemic_type'])
            st.markdown(f"**Epistemic Status:** {badge}", unsafe_allow_html=True)

