"""Page 7: Opportunity Prioritization & Dynamic Weighting Matrix."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import IssueCluster, OpportunityScore
from src.prioritization.scorer import OpportunityScorer, PrioritizationWeights
from ui.components.cards import render_opportunity_card


def render(session: Session, filters: dict):
    """Renders the dynamic 6-dimensional opportunity prioritization matrix with interactive weight sliders."""
    st.title("⚖️ Opportunity Prioritization & Dynamic Matrix")
    st.caption("Customizable 6-dimensional mathematical scoring framework with logarithmic anti-vocal-minority frequency damping.")

    # --- Interactive PM Weight Sliders ---
    with st.expander("⚙️ Customize PM Prioritization Weights", expanded=False):
        st.write("Adjust dimension weights. The engine dynamically normalizes the sum to 1.0.")
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            w_biz = st.slider("Business Impact (12-Mo Retention)", 0.0, 1.0, 0.25, 0.05)
            w_sev = st.slider("User Pain Severity", 0.0, 1.0, 0.20, 0.05)
        with col_w2:
            w_act = st.slider("Groww Product Actionability", 0.0, 1.0, 0.20, 0.05)
            w_conf = st.slider("Evidence Confidence Tier", 0.0, 1.0, 0.15, 0.05)
        with col_w3:
            w_freq = st.slider("Damped Multi-Source Frequency", 0.0, 1.0, 0.10, 0.05)
            w_eff = st.slider("Implementation Feasibility (1 - Effort)", 0.0, 1.0, 0.10, 0.05)

    weights = PrioritizationWeights(
        business_relevance=w_biz,
        severity=w_sev,
        actionability=w_act,
        evidence_confidence=w_conf,
        frequency=w_freq,
        implementation_effort=w_eff,
    ).normalized()

    # Score clusters with the active weights
    scorer = OpportunityScorer()
    scored_pairs = scorer.score_all_clusters(session, weights=weights, persist=True)

    if not scored_pairs:
        st.info("No problem clusters available to prioritize. Run ingestion and analysis first.")
        return

    # Leaderboard Table
    st.subheader(f"🏆 Opportunity Leaderboard ({len(scored_pairs)} Ranked Themes)")

    table_data = []
    for rank, (cluster, opp) in enumerate(scored_pairs, start=1):
        table_data.append({
            "Rank": f"#{rank}",
            "Theme": cluster.theme_title,
            "Priority Score": f"{opp.composite_priority_score:.2f}",
            "Biz Impact": f"{opp.business_relevance_score:.2f}",
            "Actionability": f"{opp.actionability_score:.2f}",
            "Severity": f"{opp.severity_score:.2f}",
            "Feasibility": f"{(1.0 - opp.implementation_effort_score):.2f}",
            "Evidence Tier": cluster.evidence_tier.upper(),
        })

    df_lead = pd.DataFrame(table_data)
    st.dataframe(df_lead, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📋 Opportunity Dossier & PM Note Taking")

    for rank, (cluster, opp) in enumerate(scored_pairs, start=1):
        opp_dict = {
            "rank": rank,
            "theme_title": cluster.theme_title,
            "composite_score": opp.composite_priority_score,
            "evidence_tier": cluster.evidence_tier,
            "business_relevance": opp.business_relevance_score,
            "actionability": opp.actionability_score,
            "severity": opp.severity_score,
            "frequency": opp.frequency_score,
            "implementation_effort": opp.implementation_effort_score,
            "rationale": opp.score_rationale or "",
        }
        render_opportunity_card(opp_dict)

        # PM Notes Editor per cluster
        with st.expander(f"📝 PM Strategy Notes for #{rank} {cluster.theme_title}", expanded=False):
            current_note = opp.pm_notes or ""
            new_note = st.text_area("Internal PM Notes / Sprint Decisions:", value=current_note, key=f"note_{opp.id}")
            if st.button("Save PM Note", key=f"btn_note_{opp.id}"):
                opp.pm_notes = new_note
                session.commit()
                st.success("PM Note saved to database!")

