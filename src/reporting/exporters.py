"""Multi-Format PM Research Exporters: Markdown, CSV, and PDF (ReportLab).

Generates presentation-ready executive research reports for Product Managers,
leadership, and external case study submissions.
"""

import io
import re
import csv
import zipfile
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session

from src.models.database import (
    RawRecord,
    IssueCategory,
    IssueCluster,
    ExtractedIssue,
    OpportunityScore,
)

logger = logging.getLogger("ai_discovery_engine.reporting.exporters")


class MarkdownExporter:
    """Exports compiled PM research dossiers to GitHub-Flavored Markdown."""

    @staticmethod
    def export_to_string(dossier: Dict[str, Any]) -> str:
        """Serializes a dossier dictionary into a comprehensive Markdown document."""
        meta = dossier.get("metadata", {})
        inventory = dossier.get("inventory_stats", {})
        feedback = dossier.get("feedback_stats", {})
        ranked = dossier.get("ranked_opportunities", [])
        chapters = dossier.get("chapters", [])

        md: List[str] = []

        # Document Header
        md.append(f"# {meta.get('title', 'PM Research Dossier')}")
        md.append(f"### *{meta.get('subtitle', '')}*\n")
        md.append(f"**Generated:** {meta.get('generated_at', '')} | **Platform:** {meta.get('platform', '')} | **Author:** {meta.get('author', '')}\n")
        md.append("---")

        # Executive Metrics Table
        md.append("## Executive Ingestion & Research Inventory\n")
        md.append("| Metric | Value | Detail |")
        md.append("|---|---|---|")
        md.append(f"| **Total Raw Ingested Records** | {inventory.get('total_records', 0)} | Multi-channel corpus across 5 sources |")
        md.append(f"| **Discrete Extracted Issues** | {feedback.get('total_issues', 0)} | Schema-validated with substring integrity |")
        md.append(f"| **Semantic Problem Clusters** | {len(ranked)} | Synthesized issue friction themes |")
        md.append(f"| **Direct Groww Mentions** | {feedback.get('groww_mentions', 0)} | Explicit platform workflow references |")
        md.append("")

        # Source Breakdown Subtable
        ch_dict = inventory.get("by_channel", {})
        if ch_dict:
            md.append("### Ingestion Source Breakdown\n")
            md.append("| Channel | Records Ingested | Primary Focus |")
            md.append("|---|---|---|")
            channel_desc = {
                "reddit": "Community discussions & unprompted complaints",
                "app_store": "Play Store / App Store balanced 1-to-5 star reviews",
                "official_doc": "Regulatory publications (SEBI / AMFI / Groww Help)",
                "news": "Financial investigative journalism & market studies",
                "interview": "In-depth qualitative customer user transcripts",
            }
            for ch, cnt in ch_dict.items():
                desc = channel_desc.get(ch, "Research data")
                md.append(f"| `{ch}` | {cnt} | {desc} |")
            md.append("")

        # Top Prioritized Opportunities Leaderboard Table
        if ranked:
            md.append("## Top Prioritized Product Opportunities Leaderboard\n")
            md.append("| Rank | Problem Theme | Priority Score | Biz Impact | Actionability | Severity | Feasibility | Evidence Tier |")
            md.append("|---|---|---|---|---|---|---|---|")
            for opp in ranked[:10]:
                tier = opp.get("evidence_tier", "moderate").upper()
                md.append(
                    f"| **#{opp['rank']}** | {opp['theme_title']} | **{opp['composite_score']:.2f}** | "
                    f"{opp['business_relevance']:.2f} | {opp['actionability']:.2f} | {opp['severity']:.2f} | "
                    f"{(1.0 - opp['implementation_effort']):.2f} | `{tier}` |"
                )
            md.append("")

        # Table of Contents
        md.append("## Table of Contents\n")
        for ch in chapters:
            num = ch.get("chapter_number", 0)
            title = ch.get("title", "")
            slug = f"chapter-{num}-{title.lower().replace(' ', '-').replace('&', '').replace('---', '-')}"
            md.append(f"- [Chapter {num}: {title}](#chapter-{num}-{title.lower().replace(' ', '-').replace('&', '').replace('---', '-')})")
        md.append("\n---\n")

        # 12 Dossier Chapters
        for ch in chapters:
            num = ch.get("chapter_number", 0)
            title = ch.get("title", "")
            content = ch.get("content", "")
            md.append(f"## Chapter {num}: {title}\n")
            md.append(content)
            md.append("\n---\n")

        return "\n".join(md)

    @classmethod
    def export_to_file(cls, dossier: Dict[str, Any], filepath: Union[str, Path]) -> str:
        """Writes Markdown dossier to disk and returns the string path."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        content = cls.export_to_string(dossier)
        p.write_text(content, encoding="utf-8")
        return str(p.resolve())


class CsvExporter:
    """Exports structured database tables to standardized CSV format."""

    @staticmethod
    def export_raw_records_csv(session: Session) -> str:
        """Exports raw records table to CSV string."""
        records = session.query(RawRecord).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "source_type", "platform", "title", "relevance_status",
            "rating", "publication_date", "is_synthetic_demo", "sanitized_text"
        ])
        for r in records:
            writer.writerow([
                r.id, r.source_type, r.platform, r.title or "", r.relevance_status,
                r.rating or "", r.publication_date or "", r.is_synthetic_demo, r.sanitized_text
            ])
        return output.getvalue()

    @staticmethod
    def export_extracted_issues_csv(session: Session) -> str:
        """Exports extracted issues table to CSV string."""
        issues = session.query(ExtractedIssue).all()
        categories = {c.id: c.name for c in session.query(IssueCategory).all()}
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "raw_record_id", "category_id", "category_name", "core_problem",
            "journey_stage", "severity_level", "epistemic_type", "mentions_groww",
            "is_first_hand_experience", "sip_status", "confidence_score", "verbatim_excerpt"
        ])
        for i in issues:
            cat_name = categories.get(i.category_id, "")
            writer.writerow([
                i.id, i.raw_record_id, i.category_id or "", cat_name, i.core_problem,
                i.journey_stage, i.severity_level, i.epistemic_type, i.mentions_groww,
                i.is_first_hand_experience, i.sip_status, i.confidence_score, i.verbatim_excerpt
            ])
        return output.getvalue()

    @staticmethod
    def export_opportunities_csv(session: Session) -> str:
        """Exports scored opportunity rankings to CSV string."""
        opps = (
            session.query(OpportunityScore)
            .join(IssueCluster)
            .order_by(OpportunityScore.composite_priority_score.desc())
            .all()
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "rank", "cluster_id", "theme_title", "evidence_tier", "composite_priority_score",
            "business_relevance", "severity", "actionability", "evidence_confidence",
            "frequency", "implementation_effort", "score_rationale"
        ])
        for rank, opp in enumerate(opps, start=1):
            cl = opp.cluster
            writer.writerow([
                rank, opp.cluster_id, cl.theme_title if cl else "", cl.evidence_tier if cl else "",
                opp.composite_priority_score, opp.business_relevance_score, opp.severity_score,
                opp.actionability_score, opp.evidence_confidence_score, opp.frequency_score,
                opp.implementation_effort_score, opp.score_rationale or ""
            ])
        return output.getvalue()

    @classmethod
    def export_all_to_zip(cls, session: Session, output_zip_path: Union[str, Path]) -> str:
        """Packages all 3 CSVs into a single ZIP archive for PM download."""
        p = Path(output_zip_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("raw_records.csv", cls.export_raw_records_csv(session))
            zf.writestr("extracted_issues.csv", cls.export_extracted_issues_csv(session))
            zf.writestr("prioritized_opportunities.csv", cls.export_opportunities_csv(session))
        return str(p.resolve())


class PdfExporter:
    """Renders professional PM research dossiers to PDF using ReportLab."""

    @classmethod
    def export_to_file(cls, dossier: Dict[str, Any], filepath: Union[str, Path]) -> str:
        """Compiles and writes PDF dossier to the specified filepath."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        pdf_bytes = cls.export_to_bytes(dossier)
        p.write_bytes(pdf_bytes)
        return str(p.resolve())

    @classmethod
    def export_to_bytes(cls, dossier: Dict[str, Any]) -> bytes:
        """Renders the dossier into an in-memory PDF byte buffer."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        # Custom typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=normal,
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#475569"),
            spaceAfter=14,
        )
        meta_style = ParagraphStyle(
            "DocMeta",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#047857"),
            spaceAfter=14,
        )
        h1_style = ParagraphStyle(
            "SectionH1",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        )
        body_style = ParagraphStyle(
            "BodyDark",
            parent=normal,
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=normal,
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )
        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=12,
            textColor=colors.white,
        )

        meta = dossier.get("metadata", {})
        inventory = dossier.get("inventory_stats", {})
        ranked = dossier.get("ranked_opportunities", [])
        chapters = dossier.get("chapters", [])

        story: List[Any] = []

        # Header Block
        story.append(Paragraph(meta.get("title", "PM Research Dossier"), title_style))
        story.append(Paragraph(meta.get("subtitle", ""), subtitle_style))
        meta_line = f"Generated: {meta.get('generated_at', '')} | Platform: {meta.get('platform', '')} | Engine: Antigravity Discovery Engine"
        story.append(Paragraph(meta_line, meta_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#047857"), spaceAfter=14))

        # Executive Metrics Table
        story.append(Paragraph("Executive Ingestion & Research Inventory", h1_style))
        ch_dict = inventory.get("by_channel", {})
        inv_data = [
            [Paragraph("Data Channel", table_header_style), Paragraph("Records Ingested", table_header_style), Paragraph("Methodological Focus", table_header_style)]
        ]
        channel_desc = {
            "reddit": "Community discussions & unprompted complaints",
            "app_store": "Play Store / App Store balanced 1-to-5 star reviews",
            "official_doc": "Regulatory publications (SEBI / AMFI / Groww Help)",
            "news": "Financial investigative journalism & market studies",
            "interview": "In-depth qualitative customer user transcripts",
        }
        for ch, cnt in ch_dict.items():
            inv_data.append([
                Paragraph(ch.replace("_", " ").title(), table_cell_style),
                Paragraph(str(cnt), table_cell_style),
                Paragraph(channel_desc.get(ch, "Research data"), table_cell_style),
            ])

        if len(inv_data) > 1:
            inv_table = Table(inv_data, colWidths=[120, 100, 310])
            inv_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ]))
            story.append(inv_table)
            story.append(Spacer(1, 14))

        # Top Prioritized Opportunities Table
        if ranked:
            story.append(Paragraph("Top Prioritized Product Opportunities", h1_style))
            opp_data = [
                [
                    Paragraph("Rank", table_header_style),
                    Paragraph("Problem Cluster Theme", table_header_style),
                    Paragraph("Score", table_header_style),
                    Paragraph("Biz Impact", table_header_style),
                    Paragraph("Actionability", table_header_style),
                    Paragraph("Tier", table_header_style),
                ]
            ]
            for opp in ranked[:6]:
                opp_data.append([
                    Paragraph(f"#{opp['rank']}", table_cell_style),
                    Paragraph(opp["theme_title"], table_cell_style),
                    Paragraph(f"{opp['composite_score']:.2f}", table_cell_style),
                    Paragraph(f"{opp['business_relevance']:.2f}", table_cell_style),
                    Paragraph(f"{opp['actionability']:.2f}", table_cell_style),
                    Paragraph(opp.get("evidence_tier", "").upper(), table_cell_style),
                ])
            opp_table = Table(opp_data, colWidths=[40, 240, 60, 65, 75, 50])
            opp_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#047857")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ]))
            story.append(opp_table)
            story.append(Spacer(1, 16))

        # 12 Chapters
        for ch in chapters:
            num = ch.get("chapter_number", 0)
            title = ch.get("title", "")
            raw_content = ch.get("content", "")

            story.append(Paragraph(f"Chapter {num}: {title}", h1_style))
            # Format markdown paragraphs into ReportLab paragraphs
            paragraphs = raw_content.split("\n\n")
            for p_text in paragraphs:
                if not p_text.strip():
                    continue
                # Escape XML characters first
                escaped = (
                    p_text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                # Convert bold **text** to <b>text</b>
                clean_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
                # Convert italics *text* to <i>text</i>
                clean_text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", clean_text)
                # Line breaks
                clean_text = clean_text.replace("\n", "<br/>")
                story.append(Paragraph(clean_text, body_style))
            story.append(Spacer(1, 8))

        doc.build(story)
        return buffer.getvalue()

    @classmethod
    def export_records_ledger_pdf_to_bytes(
        cls,
        session: Session,
        records: Optional[List[RawRecord]] = None,
        limit: Optional[int] = None,
        title: str = "Groww Mutual Fund SIP Persistency: All Collected Records Catalog",
    ) -> bytes:
        """Compiles all collected research records into a professional multi-page PDF catalog.

        Args:
            session: SQLAlchemy database session.
            records: Optional list of RawRecord instances to serialize. If None, queries session.
            limit: Maximum number of records to include in the PDF.
            title: Title to display on document header.

        Returns:
            Raw PDF bytes suitable for download or disk persistence.
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )

        if records is None:
            query = session.query(RawRecord).order_by(
                RawRecord.relevance_status.asc(),
                RawRecord.ingestion_timestamp.desc(),
            )
            if limit:
                query = query.limit(limit)
            records = query.all()
        elif limit:
            records = records[:limit]

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        title_style = ParagraphStyle(
            "LedgerTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "LedgerSubTitle",
            parent=normal,
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10,
        )
        meta_style = ParagraphStyle(
            "LedgerMeta",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#047857"),
            spaceAfter=10,
        )
        table_header_style = ParagraphStyle(
            "LedgerTableHeader",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        )
        cell_meta_style = ParagraphStyle(
            "LedgerCellMeta",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#1e293b"),
        )
        cell_text_style = ParagraphStyle(
            "LedgerCellText",
            parent=normal,
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#334155"),
        )

        story: List[Any] = []

        # Document Header
        story.append(Paragraph(title, title_style))
        story.append(Paragraph("Complete Ingestion Ledger: Raw user feedback, regulatory studies, and PII-sanitized text", subtitle_style))
        meta_line = f"Total Records in PDF: {len(records)} | PII Compliance: 100% Sanitized (Zero PAN, Phone, Email) | Antigravity AI Discovery Engine"
        story.append(Paragraph(meta_line, meta_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#047857"), spaceAfter=12))

        # Channel Breakdown Summary
        by_channel = {}
        by_rel = {}
        for r in records:
            by_channel[r.source_type] = by_channel.get(r.source_type, 0) + 1
            by_rel[r.relevance_status] = by_rel.get(r.relevance_status, 0) + 1

        summary_data = [
            [
                Paragraph("<b>Research Channel</b>", cell_meta_style),
                Paragraph("<b>Count</b>", cell_meta_style),
                Paragraph("<b>Relevance Tier</b>", cell_meta_style),
                Paragraph("<b>Count</b>", cell_meta_style),
            ]
        ]
        ch_items = list(by_channel.items())
        rel_items = list(by_rel.items())
        max_rows = max(len(ch_items), len(rel_items))
        for idx in range(max_rows):
            ch_txt = ch_items[idx][0].replace("_", " ").title() if idx < len(ch_items) else ""
            ch_cnt = str(ch_items[idx][1]) if idx < len(ch_items) else ""
            rel_txt = rel_items[idx][0].replace("_", " ").title() if idx < len(rel_items) else ""
            rel_cnt = str(rel_items[idx][1]) if idx < len(rel_items) else ""
            summary_data.append([
                Paragraph(ch_txt, cell_text_style),
                Paragraph(ch_cnt, cell_text_style),
                Paragraph(rel_txt, cell_text_style),
                Paragraph(rel_cnt, cell_text_style),
            ])

        sum_table = Table(summary_data, colWidths=[140, 60, 200, 130])
        sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 12))

        # Records Table
        table_data = [
            [
                Paragraph("# & Source", table_header_style),
                Paragraph("Status & Rating", table_header_style),
                Paragraph("PII-Sanitized Record Content", table_header_style),
            ]
        ]

        for idx, rec in enumerate(records, start=1):
            src_str = f"<b>#{idx}</b><br/>{rec.platform}<br/><i>{rec.source_type}</i>"
            rel_str = f"<b>{rec.relevance_status.replace('_', ' ').title()}</b>"
            if rec.rating:
                rel_str += f"<br/>Rating: {rec.rating}★"
            if rec.publication_date:
                rel_str += f"<br/>Date: {rec.publication_date}"

            clean_text = (
                (rec.sanitized_text or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            # Clip very long texts if necessary to prevent single-cell overflow
            if len(clean_text) > 600:
                clean_text = clean_text[:600] + "..."

            table_data.append([
                Paragraph(src_str, cell_meta_style),
                Paragraph(rel_str, cell_meta_style),
                Paragraph(clean_text, cell_text_style),
            ])

        records_table = Table(table_data, colWidths=[90, 110, 330], repeatRows=1)
        records_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#047857")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ]))
        story.append(records_table)

        doc.build(story)
        return buffer.getvalue()

    @classmethod
    def export_records_ledger_pdf_to_file(
        cls,
        session: Session,
        filepath: Union[str, Path],
        records: Optional[List[RawRecord]] = None,
        limit: Optional[int] = None,
        title: str = "Groww Mutual Fund SIP Persistency: All Collected Records Catalog",
    ) -> str:
        """Writes the collected records catalog PDF to disk."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        pdf_bytes = cls.export_records_ledger_pdf_to_bytes(session, records=records, limit=limit, title=title)
        p.write_bytes(pdf_bytes)
        return str(p.resolve())

