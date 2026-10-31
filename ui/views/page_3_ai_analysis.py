"""Page 3: AI Analysis & Semantic Problem Clusters."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import IssueCluster, ExtractedIssue, IssueCategory
from ui.components.cards import render_epistemic_badge, render_tier_badge


def render(session: Session, filters: dict):
    """Renders semantic problem clusters, category breakdown, and epistemic fact vs interpretation analysis."""
    st.title("🧠 AI Analysis & Semantic Clusters")
    st.caption("AI-synthesized problem clusters, centroid narratives, and epistemic triangulation boundaries.")

    clusters = session.query(IssueCluster).all()
    categories = {c.id: c.name for c in session.query(IssueCategory).all()}
    issues = session.query(ExtractedIssue).all()

    # --- Epistemic Triangulation Breakdown ---
    st.subheader("🛡️ Epistemic Triangulation (Fact vs. Interpretation)")
    ep_counts = {"observed_evidence": 0, "interpretation": 0, "hypothesis": 0}
    for i in issues:
        ep_counts[i.epistemic_type] = ep_counts.get(i.epistemic_type, 0) + 1

    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        st.markdown(render_epistemic_badge("observed_evidence"), unsafe_allow_html=True)
        st.metric("Direct Ground Truth Claims", ep_counts.get("observed_evidence", 0), help="Character-exact verbatim quotes from first-hand users")
    with col_e2:
        st.markdown(render_epistemic_badge("interpretation"), unsafe_allow_html=True)
        st.metric("Analytical Interpretations", ep_counts.get("interpretation", 0), help="Synthesized deductions by research analysts or media")
    with col_e3:
        st.markdown(render_epistemic_badge("hypothesis"), unsafe_allow_html=True)
        st.metric("Unverified Hypotheses", ep_counts.get("hypothesis", 0), help="Working assumptions requiring primary telemetry confirmation")

    st.markdown("---")

    # --- Semantic Clusters List ---
    st.subheader(f"🧩 Synthesized Problem Clusters ({len(clusters)})")

    if not clusters:
        st.info("No clusters synthesized yet. Run analysis pipeline to generate clusters.")
        return

    for c in clusters:
        tier_html = render_tier_badge(c.evidence_tier)
        with st.expander(f"{c.theme_title} ({c.supporting_record_count} supporting records)"):
            st.markdown(f"**Evidence Tier:** {tier_html}", unsafe_allow_html=True)
            st.markdown(f"**Root Cause:** `{c.primary_root_cause or 'Under Investigation'}`")
            st.markdown(f"**Cluster Narrative:** {c.summary_description}")

            # Counter evidence notes
            if c.counter_evidence_notes:
                st.warning(f"**Counter-Evidence / Dissensus Note:** {c.counter_evidence_notes}")

            # Linked extracted issues
            linked_issues = session.query(ExtractedIssue).filter_by(cluster_id=c.id).all()
            if linked_issues:
                st.markdown("##### Supporting Issue Excerpts:")
                for li in linked_issues[:5]:
                    badge = render_epistemic_badge(li.epistemic_type)
                    st.markdown(
                        f"- *\"{li.verbatim_excerpt}\"* — **{li.core_problem}** "
                        f"(Stage: `{li.journey_stage}`, Severity: `{li.severity_level}`) {badge}",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No individual issue excerpts directly linked.")

