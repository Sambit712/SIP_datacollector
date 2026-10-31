"""Reusable KPI metric card components for Streamlit dashboard."""

import streamlit as st
from typing import Optional


def render_kpi_card(
    title: str,
    value: str,
    subtitle: Optional[str] = None,
    delta: Optional[str] = None,
    delta_color: str = "normal",
    border_color: str = "#047857",
):
    """Renders a styled KPI metric box."""
    delta_html = ""
    if delta:
        color = "#10b981" if delta_color == "normal" else "#ef4444"
        delta_html = f"<div style='font-size: 0.85rem; color: {color}; margin-top: 4px;'>{delta}</div>"

    sub_html = f"<div style='font-size: 0.8rem; color: #64748b; margin-top: 4px;'>{subtitle}</div>" if subtitle else ""

    card_html = f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid {border_color};
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    ">
        <div style="font-size: 0.85rem; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.05em;">{title}</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #0f172a; margin-top: 4px;">{value}</div>
        {delta_html}
        {sub_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

