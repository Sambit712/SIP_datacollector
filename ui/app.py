"""Main Application Entry Point: Antigravity PM Research Dashboard.

Streamlit application providing 10 dedicated views for Product Managers
investigating 12-Month Mutual Fund SIP Persistency on Groww.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import get_settings
from src.models.database import get_session, init_db, RawRecord, IssueCluster
from src.nlp.pipeline import AnalysisPipeline
from src.prioritization.scorer import OpportunityScorer

from ui.views import (
    page_1_dashboard,
    page_2_source_explorer,
    page_3_ai_analysis,
    page_4_sip_lifecycle,
    page_5_competitive_groww,
    page_6_research_questions,
    page_7_prioritization,
    page_8_evaluation_golden,
    page_9_evidence_log,
    page_10_report_generator,
)

# Configure wide layout and page metadata
st.set_page_config(
    page_title="Groww Mutual Fund SIP Persistency Discovery",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    settings = get_settings()
    init_db()
    session = get_session()

    # Self-healing database check: Seed initial records if database is empty on fresh deploy
    if session.query(RawRecord).count() == 0:
        try:
            from data.seed_data import seed_all
            seed_all()
        except Exception as e:
            st.error(f"Database initialization warning: {e}")

    # --- Sidebar Header & Status ---
    st.sidebar.title("📈 Groww SIP Engine")
    st.sidebar.caption("AI-Powered Discovery Engine | 12-Month Persistency Research")

    # System Status Indicator
    if settings.is_offline or not settings.GROQ_API_KEY:
        st.sidebar.warning("🟡 **Offline Mode:** Deterministic Fallback Engine Active")
    else:
        st.sidebar.success(f"🟢 **Online:** Groq LPU (`{settings.GROQ_MODEL}`)")

    st.sidebar.markdown("---")

    # --- Navigation Router (10 Dedicated Views) ---
    st.sidebar.subheader("Navigation")
    pages = {
        "📊 1. Executive Dashboard": page_1_dashboard,
        "🔍 2. Source Explorer": page_2_source_explorer,
        "🧠 3. AI Analysis & Clusters": page_3_ai_analysis,
        "🔄 4. SIP 12-Month Lifecycle": page_4_sip_lifecycle,
        "⚔️ 5. Competitive & Groww Deep Dive": page_5_competitive_groww,
        "🎯 6. PM Discovery Questions": page_6_research_questions,
        "⚖️ 7. Opportunity Prioritization": page_7_prioritization,
        "🎯 8. Golden Benchmark Evaluation": page_8_evaluation_golden,
        "🛡️ 9. Research Evidence Log": page_9_evidence_log,
        "📄 10. PM Report Generator": page_10_report_generator,
    }

    selected_page_name = st.sidebar.radio(
        "Go to View:",
        list(pages.keys()),
        index=0,
    )

    st.sidebar.markdown("---")

    # --- Global Faceted Filters ---
    st.sidebar.subheader("Global Filters")
    channel_options = ["reddit", "app_store", "official_doc", "news", "interview"]
    selected_channels = st.sidebar.multiselect(
        "Filter by Research Channel:",
        channel_options,
        default=[],
        placeholder="All channels included",
    )

    platform_options = ["Groww", "GooglePlay", "AppStore", "Reddit", "SEBI", "AMFI"]
    selected_platforms = st.sidebar.multiselect(
        "Filter by Platform:",
        platform_options,
        default=[],
        placeholder="All platforms included",
    )

    filters = {
        "channels": selected_channels,
        "platforms": selected_platforms,
    }

    # --- Quick Maintenance Actions ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Quick Pipeline Actions")

    if st.sidebar.button("⚡ Run Extraction & Recluster", use_container_width=True):
        with st.sidebar.status("Running AI Discovery Pipeline..."):
            pipeline = AnalysisPipeline()
            unanalyzed = session.query(RawRecord).all()
            for r in unanalyzed:
                pipeline.process_record(session, r)
            pipeline.cluster_all_extracted_issues(session)
            scorer = OpportunityScorer()
            scorer.score_all_clusters(session, persist=True)
            st.sidebar.success("Pipeline executed successfully!")
            st.rerun()

    if st.sidebar.button("🔄 Recalculate Opportunity Scores", use_container_width=True):
        scorer = OpportunityScorer()
        scorer.score_all_clusters(session, persist=True)
        st.sidebar.success("Scores updated!")
        st.rerun()

    st.sidebar.caption("Antigravity AI Discovery Engine v1.0 • Groq LPU Powered")

    # --- Render Selected Page ---
    page_module = pages[selected_page_name]
    try:
        page_module.render(session, filters)
    finally:
        session.close()


if __name__ == "__main__":
    main()

