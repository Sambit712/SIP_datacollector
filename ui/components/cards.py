"""Reusable card widgets and badge renderers for PM views."""

import streamlit as st
from typing import Any, Dict, Optional


def render_epistemic_badge(epistemic_type: str) -> str:
    """Returns HTML badge for epistemic classification."""
    colors = {
        "observed_evidence": ("#ecfdf5", "#065f46", "Observed Evidence"),
        "interpretation": ("#eff6ff", "#1e40af", "Analytical Interpretation"),
        "hypothesis": ("#fef3c7", "#92400e", "Hypothesis"),
    }
    bg, fg, label = colors.get(epistemic_type, ("#f1f5f9", "#475569", epistemic_type.title()))
    return f"""<span style="
        background-color: {bg};
        color: {fg};
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 9999px;
        display: inline-block;
        border: 1px solid {fg}33;
    ">{label}</span>"""


def render_tier_badge(tier: str) -> str:
    """Returns HTML badge for evidence confidence tier."""
    colors = {
        "strong": ("#ecfdf5", "#047857", "STRONG TIER"),
        "moderate": ("#eff6ff", "#2563eb", "MODERATE TIER"),
        "weak": ("#fff7ed", "#ea580c", "WEAK TIER"),
    }
    bg, fg, label = colors.get(tier.lower(), ("#f1f5f9", "#64748b", tier.upper()))
    return f"""<span style="
        background-color: {bg};
        color: {fg};
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        padding: 2px 7px;
        border-radius: 4px;
        border: 1px solid {fg}44;
    ">{label}</span>"""


def render_opportunity_card(opp: Dict[str, Any]):
    """Renders a comprehensive opportunity card with 6-dimension scores and badges."""
    rank = opp.get("rank", 1)
    title = opp.get("theme_title", "Opportunity")
    score = opp.get("composite_score", 0.0)
    tier = opp.get("evidence_tier", "moderate")
    biz = opp.get("business_relevance", 0.0)
    act = opp.get("actionability", 0.0)
    sev = opp.get("severity", 0.0)
    freq = opp.get("frequency", 0.0)
    eff = opp.get("implementation_effort", 0.0)
    rationale = opp.get("rationale", "")

    tier_badge = render_tier_badge(tier)
    quick_win = eff <= 0.35 and act >= 0.70
    qw_badge = """<span style="background: #fdf2f8; color: #db2777; font-size: 0.72rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-left: 6px;">QUICK WIN</span>""" if quick_win else ""

    card_html = f"""
    <div style="
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    ">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div>
                <span style="font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-right: 8px;">#{rank} {title}</span>
                {tier_badge}
                {qw_badge}
            </div>
            <div style="text-align: right;">
                <span style="font-size: 1.4rem; font-weight: 800; color: #047857;">{score:.2f}</span>
                <span style="font-size: 0.8rem; color: #64748b;"> / 1.00</span>
            </div>
        </div>
        <div style="font-size: 0.85rem; color: #475569; margin-bottom: 12px; line-height: 1.4;">
            {rationale}
        </div>
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; background: #f8fafc; padding: 10px 14px; border-radius: 6px;">
            <div>
                <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">BIZ RETENTION</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b;">{biz:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">ACTIONABILITY</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b;">{act:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">SEVERITY</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b;">{sev:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">DAMPED FREQ</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b;">{freq:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">FEASIBILITY (1-E)</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b;">{(1.0 - eff):.2f}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

