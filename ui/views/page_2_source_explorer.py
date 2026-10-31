"""Page 2: Source Explorer & Raw Ingestion Grid."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import RawRecord, ExtractedIssue, IssueCategory
from src.reporting.exporters import PdfExporter


def render(session: Session, filters: dict):
    """Renders the searchable, paginated data grid with detail drawer and relevance controls."""
    st.title("🔍 Source Explorer & Ingestion Grid")
    st.caption("Inspect raw ingested feedback, review PII-sanitized text, and manage relevance status.")

    # Search & Local Filters
    col_search, col_rel, col_status = st.columns([3, 1, 1])
    with col_search:
        search_kw = st.text_input("Search raw text, title, or platform keywords:", placeholder="e.g., AutoPay, mandate, pause, charges...")
    with col_rel:
        rel_filter = st.selectbox("Relevance Status:", ["All", "highly_relevant", "partially_relevant", "not_relevant"])
    with col_status:
        synthetic_filter = st.selectbox("Dataset:", ["All", "Real Corpus", "Synthetic Demo"])

    query = session.query(RawRecord)
    if filters.get("channels"):
        query = query.filter(RawRecord.source_type.in_(filters["channels"]))
    if filters.get("platforms"):
        query = query.filter(RawRecord.platform.in_(filters["platforms"]))
    if rel_filter != "All":
        query = query.filter(RawRecord.relevance_status == rel_filter)
    if synthetic_filter == "Real Corpus":
        query = query.filter(RawRecord.is_synthetic_demo == False)
    elif synthetic_filter == "Synthetic Demo":
        query = query.filter(RawRecord.is_synthetic_demo == True)

    records = query.all()

    # Client-side keyword search
    if search_kw:
        records = [r for r in records if search_kw.lower() in (r.sanitized_text or "").lower() or search_kw.lower() in (r.title or "").lower()]

    col_info, col_export = st.columns([3, 1])
    with col_info:
        st.write(f"Showing **{len(records)}** records:")
    with col_export:
        if st.button("📕 Export Records (PDF)", key="btn_export_records_pdf", use_container_width=True):
            with st.spinner("Generating PDF..."):
                st.session_state["explorer_pdf_bytes"] = PdfExporter.export_records_ledger_pdf_to_bytes(
                    session,
                    records=records,
                    limit=500,
                    title="Groww SIP Ingestion: Records Catalog",
                )

    if "explorer_pdf_bytes" in st.session_state:
        st.download_button(
            "⬇️ Download PDF File",
            data=st.session_state["explorer_pdf_bytes"],
            file_name="groww_sip_records_export.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    if not records:
        st.info("No records match the current filters.")
        return

    # Data Grid
    table_rows = []
    for r in records:
        table_rows.append({
            "ID": r.id[:8],
            "Channel": r.source_type,
            "Platform": r.platform,
            "Title": r.title or "Untitled",
            "Relevance": r.relevance_status,
            "Verified": "✅" if r.is_user_verified else "—",
            "Demo": "Demo" if r.is_synthetic_demo else "Real",
        })
    df_grid = pd.DataFrame(table_rows)
    st.dataframe(df_grid, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📝 Record Inspector & Relevance Toggler")

    # Select box to inspect specific record
    record_options = {f"[{r.platform}] {r.title or r.id[:8]} ({r.id[:8]})": r for r in records}
    selected_label = st.selectbox("Select record to inspect details:", list(record_options.keys()))

    if selected_label:
        rec = record_options[selected_label]
        col_meta, col_actions = st.columns([2, 1])

        with col_meta:
            st.markdown(f"**Platform:** `{rec.platform}` | **Channel:** `{rec.source_type}` | **Content Hash:** `{rec.content_hash[:16]}...`")
            if rec.source_url:
                st.markdown(f"**Source URL:** [{rec.source_url}]({rec.source_url})")

            st.markdown("##### PII-Sanitized Content:")
            st.info(rec.sanitized_text)

        with col_actions:
            st.markdown("##### Manual Relevance Override")
            new_status = st.selectbox(
                "Change status:",
                ["highly_relevant", "partially_relevant", "not_relevant"],
                index=["highly_relevant", "partially_relevant", "not_relevant"].index(rec.relevance_status) if rec.relevance_status in ["highly_relevant", "partially_relevant", "not_relevant"] else 0,
                key=f"status_{rec.id}",
            )
            is_verified = st.checkbox("Mark as Verified by PM", value=rec.is_user_verified, key=f"ver_{rec.id}")

            if st.button("Save Override", key=f"save_{rec.id}", type="primary"):
                rec.relevance_status = new_status
                rec.is_user_verified = is_verified
                session.commit()
                st.success("Record updated successfully!")
                st.rerun()

