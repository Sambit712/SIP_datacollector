"""Page 5: Competitive Research & Groww Workflow Analysis."""

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from src.models.database import ExtractedIssue, RawRecord


def render(session: Session, filters: dict):
    """Renders Groww-specific feature friction points and competitive benchmarking against Zerodha, Kuvera, ET Money."""
    st.title("⚔️ Competitive & Groww Workflow Analysis")
    st.caption("Isolating Groww-specific product friction from macroeconomic and partner bank constraints.")

    groww_issues = session.query(ExtractedIssue).filter_by(mentions_groww=True).all()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Direct Groww Complaints", len(groww_issues), help="Issues explicitly mentioning Groww app flows")
    with c2:
        mandate_issues = sum(1 for i in groww_issues if "mandate" in (i.core_problem or "").lower() or "autopay" in (i.core_problem or "").lower())
        st.metric("AutoPay / Mandate Friction", mandate_issues, help="Bank mandate failures on Groww")
    with c3:
        pause_issues = sum(1 for i in groww_issues if "pause" in (i.core_problem or "").lower() or "cancel" in (i.core_problem or "").lower())
        st.metric("Pause vs Cancel Confusion", pause_issues, help="Users canceling due to hidden pause options")

    st.markdown("---")

    # Workflow Breakdown Tabs
    tab_mandate, tab_pause, tab_returns, tab_matrix = st.tabs([
        "1. AutoPay & Mandates",
        "2. Pause vs. Cancel UX",
        "3. Portfolio Loss Framing",
        "4. Competitor Benchmark Matrix",
    ])

    with tab_mandate:
        st.subheader("AutoPay Mandate Setup & Silent Rejections")
        st.markdown(
            """
            - **Problem:** First-time users set up UPI AutoPay or netbanking e-mandates. When partner banks (HDFC, SBI, ICICI) experience NPCI core banking switch downtime, Groww returns generic error toasts (*'AutoPay setup failed'* or *'Technical Error'*).
            - **User Impact:** Users do not know whether the mandate is active, risk double-debiting, or get hit with ₹295-₹590 bank bounce fees when the debit triggers without sufficient notice.
            - **Groww Attribution:** Groww can implement pre-debit balance verification nudges 48 hours in advance and display explicit plain-English bank error resolutions.
            """
        )

    with tab_pause:
        st.subheader("The 'Buried Pause' vs. 'Prominent Cancel' Trap")
        st.markdown(
            """
            - **Problem:** When users experience temporary liquidity crunches (salary delays, medical bills), they seek temporary relief for 1-2 months.
            - **UX Friction:** In the Groww app, 'Delete / Cancel SIP' is prominently exposed in the primary SIP settings, while 'Pause SIP' is often obscured in secondary submenus or missing for certain fund houses.
            - **Outcome:** Users permanently cancel the SIP instead of temporarily pausing, breaking their rupee cost averaging and permanently compounding churn.
            """
        )

    with tab_returns:
        st.subheader("Short-Term Loss Framing & Daily Return Display")
        st.markdown(
            """
            - **Problem:** Groww's modern dashboard prominently highlights **1-Day Returns** and **Total Return** in bold green or red.
            - **Psychological Friction:** During market pullbacks, first-time investors who began 2-3 months prior see red negative returns (-5% to -10%) and assume mutual funds are failing.
            - **Mitigation:** Contextual loss-aversion nudges and switching default first-year display from daily swings to goal progress / rupee cost averaging benefits.
            """
        )

    with tab_matrix:
        st.subheader("Competitor Feature Comparison Matrix")
        benchmarks = [
            {
                "Feature / Workflow": "1-Click SIP Pause",
                "Groww": "⚠️ Hidden in submenus / limited fund houses",
                "Kuvera": "✅ Prominent 1 to 3 months pause option",
                "Zerodha Coin": "⚠️ Requires mandate modification",
                "ET Money": "✅ Direct 'Pause SIP' toggle",
            },
            {
                "Feature / Workflow": "Smart Pre-Debit Warning",
                "Groww": "⚠️ Generic 24hr notification",
                "Kuvera": "✅ 48hr SMS/WhatsApp balance nudge",
                "Zerodha Coin": "⚠️ Email only",
                "ET Money": "✅ WhatsApp balance reminder",
            },
            {
                "Feature / Workflow": "Auto-Skip on Low Balance",
                "Groww": "❌ Not available (causes bank bounce fees)",
                "Kuvera": "⚠️ Manual skip 2 days before",
                "Zerodha Coin": "❌ Not available",
                "ET Money": "✅ Smart skip buffer",
            },
            {
                "Feature / Workflow": "Error Code Translation",
                "Groww": "❌ Generic error toasts ('Bank Failed')",
                "Kuvera": "✅ Plain English NPCI error explanation",
                "Zerodha Coin": "⚠️ Ticket support required",
                "ET Money": "✅ Suggested alternative bank account",
            },
        ]
        st.dataframe(pd.DataFrame(benchmarks), use_container_width=True, hide_index=True)

