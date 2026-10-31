"""Page 10: PM Research Report Generator & Multi-Format Exporter."""

import io
import streamlit as st
from sqlalchemy.orm import Session

from src.reporting.report_builder import ReportBuilder
from src.reporting.exporters import MarkdownExporter, CsvExporter, PdfExporter


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

