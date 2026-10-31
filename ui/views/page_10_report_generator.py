"""Page 10: PM Research Report Generator & Multi-Format Exporter."""

import io
import streamlit as st
from typing import Optional
from sqlalchemy.orm import Session

from src.reporting.report_builder import ReportBuilder
from src.reporting.exporters import MarkdownExporter, CsvExporter, PdfExporter


@st.cache_data(ttl=3600, show_spinner="Compiling records into multi-page PDF catalog...")
def _generate_records_catalog_pdf(scope: str) -> bytes:
    from src.models.database import get_session, RawRecord
    s = get_session()
    try:
        if scope == "Top 500 Records":
            return PdfExporter.export_records_ledger_pdf_to_bytes(
                s, limit=500, title="Groww Mutual Fund SIP Persistency: Top 500 Ingested Records"
            )
        elif scope == "Top 1000 Records":
            return PdfExporter.export_records_ledger_pdf_to_bytes(
                s, limit=1000, title="Groww Mutual Fund SIP Persistency: Top 1000 Ingested Records"
            )
        elif scope == "Relevant & Partially Relevant Only":
            records = (
                s.query(RawRecord)
                .filter(RawRecord.relevance_status.in_(["highly_relevant", "partially_relevant"]))
                .all()
            )
            return PdfExporter.export_records_ledger_pdf_to_bytes(
                s, records=records, title="Groww Mutual Fund SIP Persistency: Relevant Records Catalog"
            )
        else:  # All Records
            return PdfExporter.export_records_ledger_pdf_to_bytes(
                s, limit=None, title="Groww Mutual Fund SIP Persistency: Complete Ingested Records Catalog"
            )
    finally:
        s.close()


def render(session: Session, filters: dict):
    """Renders the 12-chapter PM Research Dossier preview and 1-click PDF, Markdown, CSV download buttons."""
    st.title("📄 PM Research Dossier Generator")
    st.caption("Generate, preview, and download the comprehensive 12-chapter research report matching the PRD specification.")

    builder = ReportBuilder(session)
    dossier = builder.build_full_dossier()

    # --- 1-Click Multi-Format Export Buttons ---
    st.subheader("📥 Export Complete Research Bundle")
    col_pdf, col_md, col_csv = st.columns(3)

    with col_pdf:
        pdf_bytes = PdfExporter.export_to_bytes(dossier)
        st.download_button(
            "📕 Download PDF Dossier",
            data=pdf_bytes,
            file_name="groww_sip_research_dossier.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

    with col_md:
        md_text = MarkdownExporter.export_to_string(dossier)
        st.download_button(
            "📘 Download Markdown Dossier",
            data=md_text,
            file_name="groww_sip_research_dossier.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col_csv:
        zip_buffer = io.BytesIO()
        import zipfile
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("raw_records.csv", CsvExporter.export_raw_records_csv(session))
            zf.writestr("extracted_issues.csv", CsvExporter.export_extracted_issues_csv(session))
            zf.writestr("prioritized_opportunities.csv", CsvExporter.export_opportunities_csv(session))
        st.download_button(
            "📦 Download CSV Data Bundle (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="groww_sip_data_bundle.zip",
            mime="application/zip",
            use_container_width=True,
        )

    st.markdown("---")

    # --- Ingestion Ledger & Records Catalog PDF ---
    st.subheader("📑 Collected Records Ledger & Catalog (PDF)")
    st.caption("Export all raw and PII-sanitized research records collected across Play Store, Reddit, regulatory publications, and interviews into a publication-ready PDF catalog.")

    col_scope, col_btn = st.columns([3, 2])
    with col_scope:
        scope = st.selectbox(
            "Select Records Scope for PDF Catalog:",
            [
                "All Records (Full Catalog - 6,536 records)",
                "Relevant & Partially Relevant Only",
                "Top 1000 Records",
                "Top 500 Records",
            ],
            key="records_pdf_scope",
        )
    with col_btn:
        st.write("")
        st.write("")
        if st.button("⚡ Generate PDF Catalog", key="btn_gen_records_pdf", use_container_width=True):
            with st.spinner("Compiling records into PDF catalog..."):
                st.session_state["records_catalog_pdf"] = _generate_records_catalog_pdf(scope)
                st.session_state["records_catalog_scope"] = scope
                st.success(f"PDF Catalog ready ({len(st.session_state['records_catalog_pdf']) / 1024:.1f} KB)!")

    if "records_catalog_pdf" in st.session_state:
        st.download_button(
            f"📕 Download Records Catalog PDF ({st.session_state.get('records_catalog_scope', 'Catalog')})",
            data=st.session_state["records_catalog_pdf"],
            file_name=f"groww_sip_records_catalog_{st.session_state.get('records_catalog_scope', 'all').lower().replace(' ', '_')[:25]}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

    st.markdown("---")

    # --- Live Dossier Interactive Chapter Preview ---
    st.subheader("📖 Interactive Dossier Reader")
    chapters = dossier.get("chapters", [])
    ch_options = {f"Chapter {c['chapter_number']}: {c['title']}": c for c in chapters}

    view_mode = st.radio("View Mode:", ["Browse by Chapter", "Read Full 12-Chapter Document"], horizontal=True)

    if view_mode == "Browse by Chapter":
        sel_ch_title = st.selectbox("Select Chapter to read:", list(ch_options.keys()))
        if sel_ch_title:
            sel_ch = ch_options[sel_ch_title]
            st.markdown(f"### {sel_ch_title}")
            st.markdown(sel_ch["content"])
    else:
        st.markdown(f"# {dossier['metadata']['title']}")
        st.caption(f"{dossier['metadata']['subtitle']} | {dossier['metadata']['generated_at']}")
        st.divider()
        for ch in chapters:
            st.markdown(f"### Chapter {ch['chapter_number']}: {ch['title']}")
            st.markdown(ch["content"])
            st.divider()

