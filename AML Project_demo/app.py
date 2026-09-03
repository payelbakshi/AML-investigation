# -*- coding: utf-8 -*-
import time
from datetime import datetime, timezone

import gradio as gr
import pandas as pd

from src.database import (
    MAX_CUSTOMERS,
    format_kyc_context,
    format_past_investigations,
    format_transaction_logs,
    get_annotated_transactions,
    get_customer,
    get_customers,
    get_kyc_profile,
    get_transactions,
    init_db,
    update_customer_remarks,
    validate_user,
)
from src.risk_engine import _parse_txn_datetime, refresh_all_risk_scores

try:
    from src.orchestration import run_aml_pipeline
except Exception:
    run_aml_pipeline = None

init_db()

SESSION_TIMEOUT_SECONDS = 30 * 60


def clear_session_payload():
    return {
        "logged_in": False,
        "username": "",
        "expires_at": 0,
        "current_view": "login",
        "customer_id": "",
    }


def make_session_payload(
    username: str,
    current_view: str = "customers",
    customer_id: str = "",
    now: float | None = None,
):
    username = (username or "").strip()
    if not username:
        return clear_session_payload()
    current_time = time.time() if now is None else now
    return {
        "logged_in": True,
        "username": username,
        "expires_at": current_time + SESSION_TIMEOUT_SECONDS,
        "current_view": current_view,
        "customer_id": customer_id or "",
    }


def is_session_valid(session_payload):
    if not isinstance(session_payload, dict):
        return False
    if not session_payload.get("logged_in"):
        return False

    username = str(session_payload.get("username") or "").strip()
    expires_at = float(session_payload.get("expires_at") or 0)
    return bool(username) and expires_at > time.time()


THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --ivory-base: #F8F6F0;
    --ivory-surface: #FFFFFF;
    --ivory-card: rgba(255, 255, 255, 0.90);
    --ivory-tint: #F3EFE6;
    --pakistan-green: #143109;
    --pakistan-green-dark: #0B1C05;
    --pakistan-green-mid: #1A3E0C;
    --pakistan-green-light: #2D6117;
    --royal-purple: #7E3F8F;
    --royal-purple-dark: #582466;
    --royal-purple-glow: rgba(126, 63, 143, 0.35);
    --sage: #8E9369;
    --sage-light: #C2C6A3;
    --sage-subtle: rgba(142, 147, 105, 0.18);
    --gold: #C69214;
    --gold-subtle: rgba(198, 146, 20, 0.15);
    --danger-red: #B3261E;
    --danger-subtle: rgba(179, 38, 30, 0.12);
    --warning-amber: #D97706;
    --warning-subtle: rgba(217, 119, 6, 0.12);
    --success-green: #15803D;
    --success-subtle: rgba(21, 128, 61, 0.12);
    --text-primary: #12210B;
    --text-secondary: #3D4A38;
    --text-muted: #6B7966;
    --border-subtle: rgba(142, 147, 105, 0.30);
    --border-strong: rgba(126, 63, 143, 0.25);
    --radius-sm: 10px;
    --radius-md: 16px;
    --radius-lg: 24px;
    --radius-xl: 32px;
    --shadow-soft: 0 4px 20px rgba(20, 49, 9, 0.05);
    --shadow-card: 0 10px 32px rgba(20, 49, 9, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04);
    --shadow-elevated: 0 18px 48px rgba(20, 49, 9, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.8) inset;
    --shadow-glow: 0 8px 30px var(--royal-purple-glow);
    --transition: 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, .gradio-container {
    min-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji", sans-serif !important;
    -webkit-font-smoothing: antialiased;
    color: var(--text-primary) !important;
}

.brand-icon, .stat-icon, .splash-icon, .info-banner-icon, .info-icon-badge, .sync-icon {
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji", -apple-system, sans-serif !important;
    line-height: 1 !important;
    font-style: normal !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.gradio-container {
    background:
        radial-gradient(ellipse 90% 60% at 5% 0%, rgba(126, 63, 143, 0.07), transparent),
        radial-gradient(ellipse 80% 50% at 95% 10%, rgba(142, 147, 105, 0.14), transparent),
        radial-gradient(ellipse 70% 60% at 50% 95%, rgba(20, 49, 9, 0.04), transparent),
        linear-gradient(175deg, #FAF8F3 0%, var(--ivory-base) 45%, #F0EAE0 100%) !important;
}

.gradio-container:has(.login-shell) {
    background:
        radial-gradient(ellipse 80% 70% at 20% 20%, rgba(126, 63, 143, 0.30), transparent),
        radial-gradient(ellipse 65% 55% at 80% 80%, rgba(142, 147, 105, 0.18), transparent),
        linear-gradient(155deg, #091704 0%, #143109 50%, #061003 100%) !important;
}

footer, .built-with { display: none !important; }

/* ── Session Restore Loading Splash ── */
/* Covers the page while demo.load() fires, preventing login flash */
#aml-splash {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.25rem;
    background: linear-gradient(155deg, #091704 0%, #143109 50%, #061003 100%);
    transition: opacity 0.35s ease, visibility 0.35s ease;
}

#aml-splash.hidden {
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
}

#aml-splash .splash-icon {
    font-size: 3rem;
    animation: splashPulse 1.4s ease-in-out infinite;
}

#aml-splash .splash-text {
    font-family: 'Outfit', system-ui, sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: rgba(255,255,255,0.85);
    letter-spacing: 0.04em;
}

#aml-splash .splash-bar {
    width: 160px;
    height: 3px;
    background: rgba(255,255,255,0.12);
    border-radius: 99px;
    overflow: hidden;
}

#aml-splash .splash-bar-inner {
    height: 100%;
    width: 40%;
    background: linear-gradient(90deg, rgba(126,63,143,0.8), rgba(194,198,163,0.9));
    border-radius: 99px;
    animation: splashSlide 1.2s ease-in-out infinite;
}

@keyframes splashPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.75; }
}

@keyframes splashSlide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
}


/* ── Hidden System Triggers (Robust & Always DOM-Active) ── */
.hidden-trigger {
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    pointer-events: auto !important;
}

/* ── Topbar (Global Luxury Header) ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    padding: 1rem 2rem;
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(28px) saturate(1.6);
    -webkit-backdrop-filter: blur(28px) saturate(1.6);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    margin-bottom: 1.75rem;
    box-shadow: var(--shadow-card);
}

.investigation-fullpage .topbar,
.topbar-dark {
    border-radius: 0 !important;
    margin-bottom: 0 !important;
    background: rgba(255, 255, 255, 0.94) !important;
    border: none !important;
    border-bottom: 1px solid rgba(126, 63, 143, 0.20) !important;
    box-shadow: 0 10px 36px rgba(20, 49, 9, 0.08) !important;
}

.brand-wrap {
    display: flex;
    align-items: center;
    gap: 1rem;
    font-weight: 700;
    font-size: 1.12rem;
    letter-spacing: -0.02em;
    color: var(--pakistan-green);
}

.brand-icon {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: grid;
    place-items: center;
    background: linear-gradient(145deg, var(--pakistan-green), #0B1C05);
    color: var(--white);
    font-size: 1.25rem;
    box-shadow: 0 6px 18px rgba(20, 49, 9, 0.35), inset 0 1px 0 rgba(255,255,255,0.25);
    border: 1px solid rgba(255, 255, 255, 0.15);
}

.brand-subtitle {
    display: block;
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--sage);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-top: 2px;
}

.nav-actions {
    display: flex;
    align-items: center;
    gap: 0.85rem;
}

/* ── Requirement 2: Dark Back Navigation Button with Rich Hover ── */
.nav-pill-back,
.topbar-dark .nav-pill-back {
    background: #143109 !important;
    color: #FFFFFF !important;
    border: 1px solid #2D6117 !important;
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    font-weight: 600;
    font-size: 0.82rem;
    padding: 0.55rem 1.25rem;
    border-radius: 999px;
    cursor: pointer;
    transition: all var(--transition);
    box-shadow: 0 4px 14px rgba(20, 49, 9, 0.30);
    letter-spacing: 0.02em;
}

.nav-pill-back:hover,
.topbar-dark .nav-pill-back:hover {
    background: #081604 !important;
    border-color: #143109 !important;
    color: #FFFFFF !important;
    transform: translateX(-3px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.50);
}

/* ── User Avatar & Dropdown Menu ── */
.user-menu { position: relative; }

.user-menu-trigger {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.4rem 1rem 0.4rem 0.45rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    background: rgba(20, 49, 9, 0.06);
    color: var(--pakistan-green);
    border: 1px solid rgba(20, 49, 9, 0.18);
    transition: all var(--transition);
}

.user-menu-trigger:hover {
    background: rgba(126, 63, 143, 0.12);
    border-color: rgba(126, 63, 143, 0.35);
    box-shadow: 0 4px 16px rgba(126, 63, 143, 0.18);
}

.user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(145deg, var(--royal-purple), var(--royal-purple-dark));
    color: var(--white);
    display: grid;
    place-items: center;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    box-shadow: 0 2px 8px rgba(126, 63, 143, 0.35);
}

.user-menu-dropdown {
    display: none;
    position: absolute;
    right: 0;
    top: calc(100% + 0.55rem);
    min-width: 175px;
    background: #FFFFFF;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-elevated);
    overflow: hidden;
    z-index: 9999;
}

.user-menu:hover .user-menu-dropdown,
.user-menu:focus-within .user-menu-dropdown,
.user-menu.open .user-menu-dropdown {
    display: block;
    animation: dropIn 0.18s ease;
}

@keyframes dropIn {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
}

.user-menu-logout {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    width: 100%;
    border: 0;
    background: transparent;
    padding: 0.85rem 1.15rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--danger-red);
    cursor: pointer;
    text-align: left;
    transition: background var(--transition);
}

.user-menu-logout:hover {
    background: rgba(179, 38, 30, 0.08);
}

/* ── Layout Wrappers ── */
.page-shell {
    max-width: 1400px !important;
    margin: 0 auto !important;
    padding: 1.5rem 2rem 3rem !important;
}

.investigation-fullpage {
    width: 100% !important;
    max-width: 100% !important;
    min-height: 100vh !important;
}

.investigation-body {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 2rem 3rem;
}

/* ── Requirement 1 & 3: Streamlined Case Banner with Last Sync Time ── */
.case-banner {
    display: flex;
    flex-direction: column;
    gap: 0.95rem;
    background: linear-gradient(135deg, #0F2807 0%, #153809 60%, #0A1B04 100%) !important;
    border: 1px solid rgba(194, 198, 163, 0.35) !important;
    border-radius: var(--radius-md);
    padding: 1.25rem 1.75rem;
    margin-top: 1.35rem !important;
    margin-bottom: 1.35rem !important;
    box-shadow: 0 12px 36px rgba(15, 40, 7, 0.35), inset 0 1px 0 rgba(255,255,255,0.15);
}

.case-banner-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1.25rem;
    width: 100%;
}

.case-info {
    display: flex;
    align-items: center;
    gap: 1.15rem;
}

.case-avatar {
    width: 52px;
    height: 52px;
    border-radius: 16px;
    background: linear-gradient(145deg, rgba(126, 63, 143, 0.50), rgba(126, 63, 143, 0.25));
    border: 1px solid rgba(194, 198, 163, 0.40);
    display: grid;
    place-items: center;
    font-size: 1.35rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.25);
}

.case-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    color: var(--sage-light);
    font-weight: 600;
    letter-spacing: 0.06em;
}

.case-name {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.45rem;
    font-weight: 700;
    color: #FFFFFF;
    margin-top: 1px;
    letter-spacing: -0.01em;
}

.case-meta-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.case-sync-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(194, 198, 163, 0.30);
    color: #FFFFFF;
    font-size: 0.74rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.02em;
}

.risk-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.55rem 1.15rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.risk-badge.low {
    background: rgba(21, 128, 61, 0.25);
    color: #86EFAC;
    border: 1px solid rgba(134, 239, 172, 0.45);
}

.risk-badge.medium {
    background: rgba(217, 119, 6, 0.28);
    color: #FDE68A;
    border: 1px solid rgba(253, 230, 138, 0.45);
}

.risk-badge.high {
    background: rgba(179, 38, 30, 0.35);
    color: #FECDD3;
    border: 1px solid rgba(254, 205, 211, 0.60);
    box-shadow: 0 0 16px rgba(179, 38, 30, 0.35);
}

.adjudication-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.55rem 1.15rem;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}

.adjudication-badge.low {
    background: rgba(21, 128, 61, 0.28);
    color: #BBF7D0;
    border: 1px solid rgba(134, 239, 172, 0.50);
}

.adjudication-badge.medium {
    background: rgba(217, 119, 6, 0.30);
    color: #FEF08A;
    border: 1px solid rgba(253, 230, 138, 0.50);
}

.adjudication-badge.high {
    background: rgba(179, 38, 30, 0.38);
    color: #FFE4E6;
    border: 1px solid rgba(254, 205, 211, 0.65);
    box-shadow: 0 0 14px rgba(179, 38, 30, 0.40);
}

.header-typology-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding-top: 0.85rem;
    border-top: 1px solid rgba(194, 198, 163, 0.22);
    width: 100%;
}

.header-typology-title {
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--sage-light);
    text-transform: uppercase;
}

.header-typology-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
}

.case-typology-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.32rem 0.75rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    background: rgba(255, 255, 255, 0.12);
    color: #FFFFFF;
    border: 1px solid rgba(194, 198, 163, 0.35);
    backdrop-filter: blur(10px);
}

.case-typology-tag.structuring {
    background: rgba(217, 119, 6, 0.30);
    color: #FEF3C7;
    border-color: rgba(253, 230, 138, 0.60);
}

.case-typology-tag.layering {
    background: rgba(179, 38, 30, 0.35);
    color: #FEE2E2;
    border-color: rgba(254, 202, 202, 0.60);
}

.case-typology-tag.velocity {
    background: rgba(198, 146, 20, 0.30);
    color: #FEF08A;
    border-color: rgba(254, 240, 138, 0.60);
}

.case-typology-tag.jurisdiction {
    background: rgba(126, 63, 143, 0.35);
    color: #F3E8FF;
    border-color: rgba(233, 213, 255, 0.60);
}

.case-typology-tag.income {
    background: rgba(37, 99, 235, 0.30);
    color: #DBEAFE;
    border-color: rgba(191, 219, 254, 0.60);
}

.case-typology-tag.clean {
    background: rgba(21, 128, 61, 0.25);
    color: #DCFCE7;
    border-color: rgba(187, 247, 208, 0.50);
}

.risk-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    animation: pulseGlow 2s ease-in-out infinite;
}

@keyframes pulseGlow {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.8); }
}

/* ── Requirement 6: Typology Guidance Bar with Interactive Tooltips ── */
.typology-guide-panel {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(126, 63, 143, 0.22);
    border-radius: var(--radius-md);
    padding: 1.15rem 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow-card);
}

.typology-guide-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.85rem;
}

.typology-guide-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--pakistan-green);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.typology-guide-hint {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-weight: 500;
}

.typology-chips-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.85rem;
}

@media (max-width: 1024px) {
    .typology-chips-grid { grid-template-columns: repeat(2, 1fr); }
}

.typology-chip {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(135deg, #FFFFFF, var(--ivory-tint));
    border: 1px solid rgba(126, 63, 143, 0.25);
    border-radius: var(--radius-sm);
    padding: 0.65rem 0.95rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--pakistan-green);
    cursor: help;
    transition: all var(--transition);
}

.typology-chip:hover {
    border-color: var(--royal-purple);
    background: #FFFFFF;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(126, 63, 143, 0.18);
}

.info-icon-badge {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--royal-purple);
    color: #FFFFFF;
    display: grid;
    place-items: center;
    font-size: 0.65rem;
    font-weight: 700;
    flex-shrink: 0;
    box-shadow: 0 2px 6px rgba(126, 63, 143, 0.35);
}

.typology-tooltip {
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: calc(100% + 10px);
    left: 50%;
    transform: translateX(-50%);
    width: 280px;
    background: #0D2106;
    color: #FFFFF0;
    font-size: 0.74rem;
    font-weight: 400;
    line-height: 1.5;
    padding: 0.85rem 1rem;
    border-radius: 10px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.50);
    border: 1px solid rgba(194, 198, 163, 0.40);
    z-index: 9999;
    transition: opacity 0.2s ease, transform 0.2s ease;
    pointer-events: none;
    text-align: left;
}

.typology-tooltip::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -7px;
    border-width: 7px;
    border-style: solid;
    border-color: #0D2106 transparent transparent transparent;
}

.typology-chip:hover .typology-tooltip {
    visibility: visible;
    opacity: 1;
    transform: translateX(-50%) translateY(-4px);
}

/* ── Requirement 4: Step Headers Font Color Matched to Step Number Purple ── */
.panel-step {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    color: #7E3F8F !important;
    margin-bottom: 1.25rem;
    letter-spacing: -0.01em;
}

.panel-step-num {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: linear-gradient(145deg, #7E3F8F, #582466) !important;
    color: #FFFFFF !important;
    display: grid;
    place-items: center;
    font-family: 'Outfit', sans-serif;
    font-size: 0.82rem;
    font-weight: 800;
    box-shadow: 0 4px 12px rgba(126, 63, 143, 0.35);
}

/* ── Requirement 5: AML Alert Breakdown & Summary Banner ── */
.alert-summary-banner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: linear-gradient(135deg, rgba(126, 63, 143, 0.12), rgba(194, 198, 163, 0.22));
    border: 1px solid rgba(126, 63, 143, 0.35);
    border-radius: var(--radius-sm);
    padding: 0.85rem 1.15rem;
    margin-bottom: 0.85rem;
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--pakistan-green);
    line-height: 1.4;
}

/* ── Investigation Panels & Fields ── */
.investigation-panel {
    background: rgba(255, 255, 255, 0.88) !important;
    backdrop-filter: blur(28px) !important;
    border: 1px solid rgba(126, 63, 143, 0.22) !important;
    border-radius: var(--radius-md) !important;
    padding: 1.85rem !important;
    box-shadow: var(--shadow-card) !important;
    transition: all var(--transition);
}

.investigation-panel:hover {
    border-color: rgba(126, 63, 143, 0.40) !important;
    box-shadow: var(--shadow-elevated) !important;
}

.investigation-fullpage label {
    color: var(--pakistan-green) !important;
    font-size: 0.76rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

.investigation-fullpage textarea,
.investigation-fullpage input[type="text"] {
    background: #FFFFFF !important;
    border: 1px solid rgba(126, 63, 143, 0.25) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--pakistan-green) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.84rem !important;
    line-height: 1.55 !important;
}

.investigation-fullpage .accordion {
    background: #FFFFFF !important;
    border: 1px solid rgba(126, 63, 143, 0.20) !important;
    border-radius: var(--radius-sm) !important;
    margin-bottom: 0.85rem !important;
    box-shadow: 0 2px 8px rgba(20, 49, 9, 0.04);
}

.investigation-fullpage .label-wrap span {
    color: var(--pakistan-green) !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
}

/* ── Primary Action Buttons ── */
.action-btn, .primary-btn {
    border: 0 !important;
    border-radius: var(--radius-sm) !important;
    color: #FFFFFF !important;
    background: linear-gradient(145deg, var(--royal-purple), var(--royal-purple-dark)) !important;
    font-weight: 700 !important;
    font-family: 'Outfit', sans-serif !important;
    padding: 0.85rem 1.75rem !important;
    font-size: 0.92rem !important;
    box-shadow: 0 6px 20px rgba(126, 63, 143, 0.40) !important;
    transition: all var(--transition) !important;
    letter-spacing: 0.03em !important;
    cursor: pointer !important;
}

.action-btn:hover, .primary-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 30px rgba(126, 63, 143, 0.55) !important;
    filter: brightness(1.08) !important;
}

.secondary-btn {
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
    background: #FFFFFF !important;
    color: var(--pakistan-green) !important;
    font-weight: 600 !important;
    font-family: 'Outfit', sans-serif !important;
    padding: 0.65rem 1.25rem !important;
    transition: all var(--transition) !important;
    letter-spacing: 0.02em !important;
    cursor: pointer !important;
}

.secondary-btn:hover {
    background: var(--ivory-tint) !important;
    border-color: rgba(126, 63, 143, 0.35) !important;
    color: var(--royal-purple) !important;
    transform: translateY(-1px) !important;
}

/* ── KPI Stat Cards ── */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.25rem;
    margin-bottom: 1.75rem;
}

@media (max-width: 960px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }

.stat-card {
    background: rgba(255, 255, 255, 0.90);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 1.35rem 1.5rem;
    box-shadow: var(--shadow-card);
    transition: transform var(--transition), box-shadow var(--transition);
    position: relative;
    overflow: hidden;
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--sage), var(--royal-purple));
    opacity: 0;
    transition: opacity var(--transition);
}

.stat-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-elevated);
    border-color: rgba(126, 63, 143, 0.30);
}

.stat-card:hover::before { opacity: 1; }

.stat-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: 0.45rem;
}

.stat-value {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.25rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1;
    color: var(--pakistan-green);
}

.stat-card.accent .stat-value { color: var(--royal-purple); }
.stat-card.danger .stat-value { color: var(--danger-red); }
.stat-card.warning .stat-value { color: var(--warning-amber); }
.stat-card.success .stat-value { color: var(--success-green); }

.stat-icon {
    float: right;
    width: 42px;
    height: 42px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    font-size: 1.15rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.4);
}

.stat-card.accent .stat-icon { background: rgba(126, 63, 143, 0.12); }
.stat-card.danger .stat-icon { background: rgba(179, 38, 30, 0.12); }
.stat-card.warning .stat-icon { background: rgba(217, 119, 6, 0.12); }
.stat-card.success .stat-icon { background: rgba(21, 128, 61, 0.12); }

/* ── Banners & Status ── */
.info-banner {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    color: var(--pakistan-green);
    background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(243, 239, 230, 0.7));
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 1rem 1.35rem;
    font-size: 0.88rem;
    line-height: 1.5;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow-soft);
}

.info-banner-icon {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    border-radius: 9px;
    background: rgba(20, 49, 9, 0.08);
    display: grid;
    place-items: center;
    font-size: 0.85rem;
}

.error-banner {
    color: var(--danger-red);
    background: rgba(179, 38, 30, 0.08);
    border: 1px solid rgba(179, 38, 30, 0.25);
    border-radius: var(--radius-sm);
    padding: 0.9rem 1.25rem;
    font-size: 0.88rem;
    text-align: center;
    font-weight: 600;
}

.status-toast {
    font-size: 0.88rem;
    color: var(--royal-purple);
    font-weight: 700;
    padding: 0.5rem 0;
}

/* ── Dataframe Styling ── */
.gr-dataframe {
    border-radius: var(--radius-md) !important;
    overflow: hidden !important;
    border: 1px solid var(--border-subtle) !important;
    box-shadow: var(--shadow-card) !important;
    background: #FFFFFF !important;
}

.gr-dataframe thead th {
    background: linear-gradient(180deg, #FFFFFF, var(--ivory-tint)) !important;
    font-weight: 700 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--pakistan-green) !important;
    padding: 0.95rem 1.25rem !important;
    border-bottom: 1px solid var(--border-subtle) !important;
}

.gr-dataframe tbody td {
    padding: 0.85rem 1.25rem !important;
    border-bottom: 1px solid rgba(142, 147, 105, 0.15) !important;
    transition: background var(--transition) !important;
    color: var(--pakistan-green) !important;
    font-size: 0.86rem !important;
}

.gr-dataframe tbody tr:hover td {
    background: rgba(126, 63, 143, 0.06) !important;
    cursor: pointer !important;
}

/* ── Requirement: Centered & Small Compact Login Container ── */
.gradio-container:has(.login-shell) {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 100vh !important;
}

.gradio-container:has(.login-shell) > .main,
.gradio-container:has(.login-shell) .wrap {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    min-height: 100vh !important;
    margin: 0 auto !important;
}

.login-shell {
    min-height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 1.5rem !important;
    margin: 0 auto !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}

.login-shell > .gr-column,
.login-shell > div,
.login-card {
    max-width: 360px !important;
    width: 360px !important;
    margin: auto !important;
    background: rgba(255, 255, 255, 0.97) !important;
    backdrop-filter: blur(40px) !important;
    border: 1px solid rgba(255, 255, 255, 0.85) !important;
    border-radius: 20px !important;
    padding: 1.25rem 1.4rem 1.35rem !important;
    box-shadow: 0 25px 70px rgba(0, 0, 0, 0.60), 0 0 0 1px rgba(255,255,255,0.3) inset !important;
    box-sizing: border-box !important;
    flex-grow: 0 !important;
    flex-shrink: 0 !important;
    flex: 0 0 auto !important;
    height: auto !important;
    min-height: auto !important;
    max-height: fit-content !important;
    align-self: center !important;
}

.login-hero {
    text-align: center;
    margin-bottom: 0.65rem;
}

.login-hero .brand-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    font-size: 1.15rem;
    margin: 0 auto 0.35rem;
    background: linear-gradient(145deg, #143109, #081604);
}

.login-hero h2 {
    margin: 0;
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--pakistan-green);
    line-height: 1.15;
}

.login-hero p {
    margin: 0.2rem 0 0;
    color: var(--text-secondary);
    font-size: 0.78rem;
    line-height: 1.35;
}

.login-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    margin-top: 0.35rem;
    padding: 0.18rem 0.65rem;
    border-radius: 999px;
    background: rgba(126, 63, 143, 0.10);
    color: var(--royal-purple);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border: 1px solid rgba(126, 63, 143, 0.22);
}

.login-card .gr-form,
.login-card .form {
    border: none !important;
    background: transparent !important;
    gap: 0.35rem !important;
}

.login-card .gr-block,
.login-card .block {
    margin-bottom: 0.35rem !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-height: unset !important;
}

.login-card label {
    font-size: 0.70rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.2rem !important;
    color: var(--pakistan-green) !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

.login-card .container,
.login-card .wrap,
.login-card label > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

.login-card input[type="text"],
.login-card input[type="password"],
.login-card input,
.login-card textarea {
    background: #FFFFFF !important;
    border: 1px solid rgba(142, 147, 105, 0.40) !important;
    border-radius: var(--radius-sm, 8px) !important;
    padding: 0.45rem 0.75rem !important;
    font-size: 0.84rem !important;
    height: 38px !important;
    min-height: 38px !important;
    max-height: 38px !important;
    box-sizing: border-box !important;
    line-height: normal !important;
    color: var(--pakistan-green, #143109) !important;
    width: 100% !important;
    resize: none !important;
    box-shadow: none !important;
}

.login-card input:focus,
.login-card textarea:focus {
    border-color: var(--royal-purple, #7e3f8f) !important;
    box-shadow: 0 0 0 3px rgba(126, 63, 143, 0.15) !important;
    outline: none !important;
    background: #FFFFFF !important;
}

.login-card .action-btn {
    width: 100% !important;
    margin-top: 0.65rem !important;
    padding: 0.65rem !important;
    font-size: 0.86rem !important;
    height: 42px !important;
}
"""

PAGE_SIZE = 10
TABLE_HEADERS = [
    "Customer ID",
    "Name",
    "Branch",
    "Risk Score",
    "Triage Priority",
    "Remarks",
    "AML Investigation",
]
REMARKS_COL = 5
AML_COL = 6


def user_initials(username: str) -> str:
    parts = username.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return username[:2].upper() if username else "U"


def risk_tier(score) -> tuple[str, str]:
    try:
        value = int(score)
    except (TypeError, ValueError):
        return "Unknown", "medium"
    if value >= 61:
        return "High", "high"
    if value >= 31:
        return "Medium", "medium"
    return "Low", "low"


def get_adjudication_tier(score) -> tuple[str, str]:
    try:
        val = int(score)
    except (TypeError, ValueError):
        val = 0
    if val >= 70:
        return "🔴 High Priority (Review for STR)", "high"
    elif val >= 35:
        return "🟡 Review Required (Medium Priority)", "medium"
    else:
        return "🟢 Routine (Low Priority)", "low"


def get_customer_typology_tags(customer_id: str) -> list[dict]:
    """Extracts all active regulatory typology signals across customer transaction history and KYC profile."""
    if not customer_id:
        return []
    transactions = get_transactions(customer_id)
    kyc = get_kyc_profile(customer_id)
    if not transactions:
        return []

    monthly_income = float(kyc.get("declared_monthly_income", 0) or 0)
    tags = []

    # 1. Structuring (Smurfing)
    cash_deposits = [t for t in transactions if "cash deposit" in t.get("txn_type", "").lower()]
    near_threshold = [t for t in cash_deposits if 9000 <= abs(t["amount"]) <= 9999]
    if len(near_threshold) >= 1 or len(cash_deposits) >= 3:
        reason = f"{len(near_threshold)} cash deposit(s) near $10k threshold" if near_threshold else f"{len(cash_deposits)} cash deposits"
        tags.append({
            "name": "🏷️ Structuring (Smurfing)",
            "class": "structuring",
            "reason": f"FATF Rec. 20 / FIU-IND: {reason}"
        })

    # 2. Layering & Pass-Through
    inbound_count = sum(1 for t in transactions if t["amount"] > 0)
    total_in = sum(t["amount"] for t in transactions if t["amount"] > 0)
    total_out = abs(sum(t["amount"] for t in transactions if t["amount"] < 0))
    has_shell = any(
        kw in f"{t.get('counterparty', '')} {t.get('description', '')}".lower()
        for kw in ["shell", "nexus", "vortex", "starlight", "zenith", "apex horizon", "pass-through", "layering"]
        for t in transactions
    )
    if (inbound_count >= 3 and total_in > 0 and total_out >= total_in * 0.75) or has_shell:
        tags.append({
            "name": "🏷️ Layering & Pass-Through",
            "class": "layering",
            "reason": "FIU-IND Advisory: Multi-source aggregation rapidly consolidated and drained offshore/shell entity"
        })

    # 3. Rapid Movement (Velocity)
    parsed_times = [_parse_txn_datetime(t["txn_datetime"]) for t in transactions]
    parsed_times = [dt for dt in parsed_times if dt is not None]
    if len(parsed_times) >= 2:
        window_hours = (max(parsed_times) - min(parsed_times)).total_seconds() / 3600
        if window_hours <= 48 and len(transactions) >= 3:
            tags.append({
                "name": "🏷️ Rapid Movement (Velocity)",
                "class": "velocity",
                "reason": f"FIU-IND Red Flags: {len(transactions)} transactions in {window_hours:.0f}h window (<48h)"
            })

    # 4. High-Risk Jurisdiction Exposure
    has_offshore = any(
        kw in f"{t.get('counterparty', '')} {t.get('description', '')} {t.get('txn_type', '')}".lower()
        for kw in ["panama", "cayman", "bvi", "dubai", "offshore", "crypto", "binance", "swift", "foreign", "remittance"]
        for t in transactions
    )
    if has_offshore:
        tags.append({
            "name": "🏷️ High-Risk Jurisdiction Exposure",
            "class": "jurisdiction",
            "reason": "FATF High-Risk Jurisdictions: Cross-border SWIFT, offshore haven, or crypto gateway counterparty"
        })

    # 5. Trade / Income Inconsistency
    if monthly_income > 0 and total_in >= monthly_income * 3:
        tags.append({
            "name": "🏷️ Trade / Income Inconsistency",
            "class": "income",
            "reason": f"FIU-IND Guidelines: Inflows of ${total_in:,.0f} exceed monthly income (${monthly_income:,.0f}) by {total_in/monthly_income:.1f}×"
        })

    return tags


def get_dashboard_stats() -> tuple[int, int, int, int, float]:
    customers = get_customers(MAX_CUSTOMERS)
    high = sum(1 for c in customers if c["risk_score"] >= 61)
    medium = sum(1 for c in customers if 31 <= c["risk_score"] <= 60)
    low = sum(1 for c in customers if c["risk_score"] <= 30)
    avg = round(sum(c["risk_score"] for c in customers) / len(customers), 1) if customers else 0.0
    return len(customers), high, medium, low, avg


def build_stats_html() -> str:
    total, high, medium, low, avg = get_dashboard_stats()
    return f"""
    <div class="stats-grid">
        <div class="stat-card accent">
            <div class="stat-icon">👥</div>
            <div class="stat-label">Total Accounts Monitored</div>
            <div class="stat-value">{total}</div>
        </div>
        <div class="stat-card danger">
            <div class="stat-icon">🚨</div>
            <div class="stat-label">High Risk (Draft STR)</div>
            <div class="stat-value">{high}</div>
        </div>
        <div class="stat-card warning">
            <div class="stat-icon">⚠️</div>
            <div class="stat-label">Medium Risk (Escalate)</div>
            <div class="stat-value">{medium}</div>
        </div>
        <div class="stat-card success">
            <div class="stat-icon">🛡️</div>
            <div class="stat-label">Avg Portfolio Risk</div>
            <div class="stat-value">{avg}</div>
        </div>
    </div>
    """


def build_investigation_header_html(
    customer_id: str, name: str, risk_score: str, risk_updated_at: str = ""
) -> str:
    label, css_class = risk_tier(risk_score)
    sync_display = risk_updated_at if risk_updated_at else "Live (Just now)"
    adjudication_text, adj_class = get_adjudication_tier(risk_score)

    typology_tags = get_customer_typology_tags(customer_id)
    if typology_tags:
        chips_html = "".join(
            f'<span class="case-typology-tag {t["class"]}" title="{t["reason"]}">{t["name"]}</span>'
            for t in typology_tags
        )
        typology_section = f"""
        <div class="header-typology-bar">
            <span class="header-typology-title">⚠️ Active Regulatory Typologies ({len(typology_tags)}):</span>
            <div class="header-typology-chips">{chips_html}</div>
        </div>
        """
    else:
        typology_section = """
        <div class="header-typology-bar">
            <span class="header-typology-title">🛡️ Regulatory Typology Status:</span>
            <div class="header-typology-chips"><span class="case-typology-tag clean">🟢 Clean KYC Profile · No Adverse Typologies Triggered</span></div>
        </div>
        """

    return f"""
    <div class="case-banner">
        <div class="case-banner-top">
            <div class="case-info">
                <div class="case-avatar">👤</div>
                <div>
                    <div class="case-id">{customer_id}</div>
                    <div class="case-name">{name}</div>
                </div>
            </div>
            <div class="case-meta-right">
                <div class="case-sync-chip">
                    <span class="sync-icon">🕒</span>
                    <span style="color: white;">Last Risk Sync: <b>{sync_display}</b></span>
                </div>
                <div class="risk-badge {css_class}">
                    <span class="risk-dot" style="color: white;"></span>
                    Risk {risk_score} · {label}
                </div>
                <div class="adjudication-badge {adj_class}">
                    {adjudication_text}
                </div>
            </div>
        </div>
        {typology_section}
    </div>
    """


def build_typology_guide_html() -> str:
    return """
    <div class="typology-guide-panel">
        <div class="typology-guide-header">
            <div class="typology-guide-title">🛡️ Regulatory Typologies Knowledge Reference</div>
            <div class="typology-guide-hint">Hover over ℹ icons for FATF & FIU-IND regulatory definitions</div>
        </div>
        <div class="typology-chips-grid">
            <div class="typology-chip">
                <span>🏷️ Structuring (Smurfing)</span>
                <span class="info-icon-badge">ℹ</span>
                <div class="typology-tooltip">
                    <b>Structuring (Smurfing):</b> Breaking down large transactions under statutory threshold limits ($10,000 / INR 10 Lakhs) within a short window to avoid mandatory CTR/STR reporting triggers. <i>(FATF Rec. 20 / FIU-IND)</i>
                </div>
            </div>
            <div class="typology-chip">
                <span>🏷️ Layering & Pass-Through</span>
                <span class="info-icon-badge">ℹ</span>
                <div class="typology-tooltip">
                    <b>Layering & Pass-Through:</b> Rapid movement of funds across multiple international/inter-bank accounts to obfuscate audit trails and decouple proceeds from source. <i>(FIU-IND Advisory)</i>
                </div>
            </div>
            <div class="typology-chip">
                <span>🏷️ Rapid Movement (Velocity)</span>
                <span class="info-icon-badge">ℹ</span>
                <div class="typology-tooltip">
                    <b>Rapid Movement (Velocity):</b> Immediate liquidation or outbound transfer of funds within 24-48 hours of sudden high-value credits into low-activity accounts. <i>(FIU-IND Red Flags)</i>
                </div>
            </div>
            <div class="typology-chip">
                <span>🏷️ High-Risk Jurisdiction</span>
                <span class="info-icon-badge">ℹ</span>
                <div class="typology-tooltip">
                    <b>High-Risk Jurisdiction Exposure:</b> Direct or indirect cross-border fund flows involving offshore tax havens, shell companies, or FATF Grey/Black list territories without verified commercial contracts. <i>(FATF High-Risk Guidance)</i>
                </div>
            </div>
            <div class="typology-chip">
                <span>🏷️ Trade/Income Inconsistency</span>
                <span class="info-icon-badge">ℹ</span>
                <div class="typology-tooltip">
                    <b>Trade/Income Inconsistency:</b> Inflows significantly exceeding customer's declared occupation, income bracket, or stated business model. Discrepancy between KYC profile and actual transaction velocity. <i>(FIU-IND KYC Compliance Guidelines)</i>
                </div>
            </div>
        </div>
    </div>
    """


def normalize_table(table_data):
    if table_data is None:
        return []
    if isinstance(table_data, pd.DataFrame):
        return table_data.values.tolist()
    return table_data


def customers_to_table(customers: list[dict]) -> list[list]:
    rows = []
    for customer in customers:
        score = customer["risk_score"]
        label, _ = risk_tier(score)
        icon = "🌿" if label == "Low" else "⚠️" if label == "Medium" else "🚨"
        adjudication_text, _ = get_adjudication_tier(score)
        rows.append(
            [
                customer["customer_id"],
                customer["name"],
                customer["branch"],
                f"{icon} {score} ({label})",
                adjudication_text,
                customer["remarks"] or "—",
                "🔍 Investigate",
            ]
        )
    return rows


def get_total_pages() -> int:
    total_customers = len(get_customers(MAX_CUSTOMERS))
    return max(1, (total_customers + PAGE_SIZE - 1) // PAGE_SIZE)


def get_paginated_table(page: int) -> tuple[list[list], int, str]:
    customers = get_customers(MAX_CUSTOMERS)
    total_pages = max(1, (len(customers) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = customers[start : start + PAGE_SIZE]
    indicator = f"Page {page + 1} of {total_pages} ({len(customers)} customers)"
    return customers_to_table(chunk), page, indicator


def refresh_customer_table(page: int = 0) -> tuple[list[list], int, str]:
    refresh_all_risk_scores()
    return get_paginated_table(page)


def save_remark_for_customer(customer_id: str, remarks: str, page: int):
    if not customer_id:
        table, page, indicator = refresh_customer_table(page)
        return (
            table,
            page,
            format_page_chip(indicator),
            "Select a customer remarks cell to edit.",
        )

    update_customer_remarks(customer_id, remarks or "")
    table, page, indicator = refresh_customer_table(page)
    return table, page, format_page_chip(indicator), f"✓ Remarks saved for {customer_id}."


def build_nav_html(
    title: str,
    *,
    dark: bool = False,
    show_back: bool = False,
    back_trigger_id: str = "back-trigger",
    username: str = "",
) -> str:
    dark_class = " topbar-dark" if dark else ""
    back_label = "← Back to Dashboard"
    back_btn = ""
    if show_back:
        back_btn = (
            f'<button class="nav-pill nav-pill-back" '
            f'onclick="const b = document.getElementById(\'{back_trigger_id}\'); if (b) b.click();">{back_label}</button>'
        )
    display_name = username or "Compliance Officer"
    initials = user_initials(display_name)
    subtitle = "Compliance Platform" if not dark else "Investigation Workspace"
    return f"""
    <div class="topbar{dark_class}">
        <div class="brand-wrap">
            <div class="brand-icon">🛡️</div>
            <div>
                <span>{title}</span>
                <span class="brand-subtitle">{subtitle}</span>
            </div>
        </div>
        <div class="nav-actions">
            {back_btn}
            <div class="user-menu" data-name="{display_name}">
                <button type="button" class="user-menu-trigger" aria-expanded="false"
                        onclick="const menu = this.closest('.user-menu'); menu.classList.toggle('open');">
                    <div class="user-avatar">{initials}</div>
                    <span>{display_name}</span>
                </button>
                <div class="user-menu-dropdown">
                    <button type="button" class="user-menu-logout" onclick="const b = document.getElementById('logout-trigger'); if (b) b.click();">
                        <span aria-hidden="true">🚪</span>
                        <span>Sign Out</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
    """


def load_investigation(customer_id: str, username: str = ""):
    customer = get_customer(customer_id)
    if customer is None:
        empty = ""
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            empty,
            empty,
            empty,
            empty,
            empty,
            "🚨 Flagged AML Alerts Only",
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            gr.update(value=None, visible=False),
            make_session_payload(username, "customers", ""),
        )

    refresh_all_risk_scores()
    customer = get_customer(customer_id)

    annotated_data = get_annotated_transactions(customer_id)
    txn_summary_banner = f'<div class="alert-summary-banner">{annotated_data["summary_text"]}</div>'
    txn_logs = (
        annotated_data["flagged_log"]
        if annotated_data["alert_count"] > 0
        else annotated_data["full_log"]
    )
    filter_choice = (
        "🚨 Flagged AML Alerts Only"
        if annotated_data["alert_count"] > 0
        else "📑 Full Transaction Ledger"
    )
    kyc_context = format_kyc_context(customer_id)
    past_inv = format_past_investigations(customer_id)

    session_payload = make_session_payload(username, "investigation", customer_id)

    return (
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=True),
        customer_id,
        customer["name"],
        str(customer["risk_score"]),
        customer.get("risk_updated_at", ""),
        txn_summary_banner,
        filter_choice,
        txn_logs,
        kyc_context,
        past_inv,
        "",
        "",
        "",
        "",
        "",
        gr.update(value=None, visible=False),
        session_payload,
    )


def toggle_transaction_view(customer_id: str, filter_choice: str):
    if not customer_id:
        return ""
    annotated_data = get_annotated_transactions(customer_id)
    if filter_choice == "🚨 Flagged AML Alerts Only":
        return annotated_data["flagged_log"]
    return annotated_data["full_log"]


def run_investigation(
    customer_id,
    customer_name,
    txn_logs,
    kyc_context,
    past_inv,
    id_file,
    compliance_query,
    username,
):
    if not customer_id:
        return (
            "No customer selected.",
            "",
            "",
            "",
            "",
            gr.update(value=None, visible=False),
            make_session_payload(username, "investigation", customer_id),
        )

    if run_aml_pipeline is None:
        message = "Pipeline unavailable. Configure OpenAI API key (OPENAI_API_KEY) to run agents."
        return (
            "Pipeline unavailable.",
            message,
            message,
            message,
            message,
            gr.update(value=None, visible=False),
            make_session_payload(username, "investigation", customer_id),
        )

    try:
        decision, patterns, typologies, risk_analysis, str_report, pdf_path = run_aml_pipeline(
            transaction_data=txn_logs,
            kyc_profile=kyc_context,
            past_investigations=past_inv,
            ocr_image=id_file,
            compliance_query=compliance_query or "",
            customer_id=customer_id,
            customer_name=customer_name,
        )
    except Exception as error:
        error_text = str(error).lower()
        error_type = type(error).__name__
        is_quota_error = (
            error_type == "OpenAIRateLimitError"
            or "insufficient_quota" in error_text
            or "resource_exhausted" in error_text
            or "quota" in error_text
            or "no credits remaining" in error_text
        )
        is_auth_error = (
            error_type == "OpenAIAuthenticationError"
            or "unauthenticated" in error_text
            or "401" in error_text
            or "invalid authentication" in error_text
            or "access_token_type_unsupported" in error_text
            or "api key not valid" in error_text
        )
        if is_auth_error:
            message = (
                "Authentication Error (401): Invalid or unsupported API key. "
                "Please set a valid OPENAI_API_KEY (starts with sk-...) in your environment."
            )
        elif is_quota_error:
            message = (
                "API quota exhausted. Check your OpenAI account balance/quota, then retry."
            )
        else:
            message = f"Investigation Pipeline Error: {str(error)}"

        return (
            "Pipeline error",
            message,
            message,
            message,
            message,
            gr.update(value=None, visible=False),
            make_session_payload(username, "investigation", customer_id),
        )

    pdf_update = (
        gr.update(value=pdf_path, visible=True)
        if pdf_path
        else gr.update(value=None, visible=False)
    )
    session_payload = make_session_payload(username, "investigation", customer_id)
    return decision, patterns, typologies, risk_analysis, str_report, pdf_update, session_payload


def login_action(username_value, password_value):
    if validate_user(username_value, password_value):
        session_payload = make_session_payload(username_value, "customers")
        table, page, indicator = refresh_customer_table(0)
        nav = build_nav_html("Customer Monitoring Dashboard", username=username_value)
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(value="", visible=False),
            gr.update(value=table),
            0,
            format_page_chip(indicator),
            gr.update(value="✓ Welcome back! Risk scores refreshed."),
            gr.update(value="", visible=False),
            gr.update(value=""),
            gr.update(visible=False),
            username_value,
            gr.update(value=nav),
            gr.update(value=build_stats_html()),
            session_payload,
        )

    return (
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(
            value='<div class="error-banner">Invalid credentials. Please verify username and password.</div>',
            visible=True,
        ),
        gr.update(),
        0,
        format_page_chip("Page 1 of 1"),
        gr.update(value=""),
        gr.update(value="", visible=False),
        gr.update(value=""),
        gr.update(visible=False),
        "",
        gr.update(),
        gr.update(),
        clear_session_payload(),
    )


def go_back_to_customers(current_page, username):
    table, page, indicator = refresh_customer_table(current_page)
    nav = build_nav_html("Customer Monitoring Dashboard", username=username)
    session_payload = make_session_payload(username, "customers")
    return (
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(value=table),
        page,
        format_page_chip(indicator),
        gr.update(value=""),
        gr.update(value=nav),
        gr.update(value=build_stats_html()),
        session_payload,
    )


def refresh_scores_with_stats(page: int):
    table, page_num, indicator = refresh_customer_table(page)
    return (
        table,
        page_num,
        format_page_chip(indicator),
        "✓ Risk scores recalculated across customer activity & KYC profiles.",
        build_stats_html(),
    )


def format_page_chip(indicator: str) -> str:
    return f'<div class="page-chip">{indicator}</div>'


def change_page(current_page, direction):
    new_page = max(0, current_page + direction)
    table, page, indicator = get_paginated_table(new_page)
    return gr.update(value=table), page, format_page_chip(indicator)


def logout_action():
    return (
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(value="", visible=False),
        gr.update(value=""),
        gr.update(value=""),
        gr.update(value=[]),
        0,
        format_page_chip("Page 1 of 1"),
        gr.update(value=""),
        gr.update(value="", visible=False),
        gr.update(value=""),
        gr.update(visible=False),
        "",
        gr.update(value=""),
        gr.update(value=""),
        gr.update(value=""),
        clear_session_payload(),
    )


HEAD_JS = """
<script>
(function() {
    function hideSplash() {
        var splash = document.getElementById('aml-splash');
        if (splash) splash.classList.add('hidden');
    }

    var observer = new MutationObserver(function(mutations) {
        for (var i = 0; i < mutations.length; i++) {
            var el = mutations[i].target;
            if (el && el.style && el.style.display !== 'none' && el.style.display !== '') {
                hideSplash();
                observer.disconnect();
                return;
            }
        }
    });

    function startObserver() {
        var root = document.querySelector('.gradio-container') || document.body;
        observer.observe(root, { attributes: true, subtree: true, attributeFilter: ['style', 'class'] });
        setTimeout(hideSplash, 3000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserver);
    } else {
        startObserver();
    }
})();
</script>
"""

with gr.Blocks(title="AML Compliance & Investigation Workspace") as demo:
    current_page = gr.State(0)
    edit_customer_id = gr.State("")
    logged_in_user = gr.State("")
    session_state = gr.BrowserState(
        default_value=clear_session_payload(), storage_key="aml_session_state_v2"
    )

    # ── Session restore splash: prevents login page flash on refresh ──────────
    gr.HTML("""
    <div id="aml-splash">
        <div class="splash-icon">🛡️</div>
        <div class="splash-text">AML Compliance Portal</div>
        <div class="splash-bar"><div class="splash-bar-inner"></div></div>
    </div>
    """)

    # Bulletproof hidden triggers that stay active in the DOM
    back_trigger = gr.Button("Back", elem_id="back-trigger", elem_classes="hidden-trigger")
    logout_trigger = gr.Button("Logout", elem_id="logout-trigger", elem_classes="hidden-trigger")

    login_page = gr.Column(visible=False, elem_classes="login-shell")
    customers_page = gr.Column(visible=False, elem_classes="page-shell")
    investigation_page = gr.Column(
        visible=False,
        elem_classes="investigation-fullpage",
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Login Page (World-Class Glassmorphism)
    # ──────────────────────────────────────────────────────────────────────────
    with login_page:
        with gr.Column(elem_classes="login-card"):
            gr.HTML(
                """
                <div class="login-hero">
                    <div class="brand-icon">🛡️</div>
                    <h2>AML Compliance Portal</h2>
                    <p>Automated transaction monitoring, multi-agent typology correlation & regulator-ready reporting</p>
                    <div class="login-badge">✦ Bank-Grade Security & Privacy</div>
                </div>
                """
            )
            login_username = gr.Textbox(
                label="Username", lines=1, max_lines=1, placeholder="Enter username"
            )
            login_password = gr.Textbox(
                label="Security Password", type="password", lines=1, max_lines=1, placeholder="Enter password"
            )
            login_error = gr.HTML("", visible=False)
            login_button = gr.Button(
                "Sign In", elem_classes="action-btn", size="lg"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Customer Monitoring Dashboard
    # ──────────────────────────────────────────────────────────────────────────
    with customers_page:
        customers_nav = gr.HTML(build_nav_html("Customer Monitoring Dashboard"))
        dashboard_stats = gr.HTML(build_stats_html())
        gr.HTML(
            '<div class="info-banner">'
            '<div class="info-banner-icon">ℹ️</div>'
            "<div><b>Transaction Monitoring Hub:</b> Live risk scores calculated against customer KYC profiles, "
            "velocity windows, and threshold structuring. Click <b>🔍 Investigate</b> to launch the multi-agent AML workflow.</div>"
            "</div>"
        )

        with gr.Column(elem_classes="investigation-panel"):
            gr.HTML(
                '<div class="section-header">'
                '<div class="panel-step"><span class="panel-step-num">✦</span>Monitored Customer Directory</div>'
                "</div>"
            )
            initial_table, _, initial_indicator = refresh_customer_table(0)
            customer_table = gr.Dataframe(
                headers=TABLE_HEADERS,
                value=initial_table,
                interactive=False,
                wrap=True,
                datatype=["str", "str", "str", "str", "str", "str", "str"],
            )
            with gr.Row(elem_classes="pagination-row"):
                prev_page_btn = gr.Button("◀ Previous", elem_classes="secondary-btn", scale=1)
                page_indicator = gr.HTML(format_page_chip(initial_indicator))
                next_page_btn = gr.Button("Next ▶", elem_classes="secondary-btn", scale=1)
            with gr.Column(visible=False, elem_classes="remarks-panel-inner") as remarks_panel:
                remarks_customer_label = gr.Markdown("")
                remarks_editor = gr.Textbox(
                    label="Compliance Analyst Remarks",
                    lines=3,
                    placeholder="Document investigation notes for audit log...",
                )
                save_remarks_button = gr.Button("Save Remarks", elem_classes="action-btn")
            with gr.Row():
                refresh_scores_button = gr.Button(
                    "↻ Recalculate Portfolio Risk Scores", elem_classes="secondary-btn"
                )
            customers_status = gr.Markdown("", elem_classes="status-toast")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. AML Investigation Workspace Page
    # ──────────────────────────────────────────────────────────────────────────
    with investigation_page:
        investigation_nav = gr.HTML(
            build_nav_html(
                "AML Investigation Workspace",
                dark=True,
                show_back=True,
                username="",
            )
        )
        with gr.Column(elem_classes="investigation-body"):
            # Case Banner directly after navigation
            investigation_header = gr.HTML("")

            # Known Typologies Reference with Hover Tooltips
            typology_guide = gr.HTML(build_typology_guide_html())

            selected_customer_id = gr.Textbox(visible=False)
            selected_customer_name = gr.Textbox(visible=False)

            with gr.Row():
                # Step 1: Case Inputs Column
                with gr.Column(scale=1):
                    with gr.Column(elem_classes="investigation-panel"):
                        gr.HTML(
                            '<div class="panel-step">'
                            '<span class="panel-step-num">1</span>'
                            "Case Inputs & Transaction Intelligence"
                            "</div>"
                        )
                        risk_score_box = gr.Textbox(label="Current Risk Score", interactive=False)
                        risk_updated_box = gr.Textbox(
                            label="Risk Score Updated At", interactive=False
                        )
                        txn_summary_banner = gr.HTML("")
                        txn_filter_radio = gr.Radio(
                            choices=[
                                "🚨 Flagged AML Alerts Only",
                                "📑 Full Transaction Ledger",
                            ],
                            value="🚨 Flagged AML Alerts Only",
                            label="Transaction History View Filter",
                            interactive=True,
                        )
                        transaction_logs = gr.Textbox(
                            label="Transaction Chronology & Alert Flags",
                            lines=10,
                            interactive=False,
                        )
                        kyc_profile = gr.Textbox(
                            label="Customer KYC Profile Context",
                            lines=5,
                            interactive=False,
                        )
                        past_investigations_box = gr.Textbox(
                            label="Past AML Investigation History & Precedents",
                            lines=3,
                            interactive=False,
                        )
                        id_upload = gr.File(
                            label="Multimodal Document Verification: Upload ID / Passport (Optional)",
                            file_types=["image"],
                        )
                        compliance_inquiry_box = gr.Textbox(
                            label="Targeted Compliance Inquiry / Investigator Question (Optional)",
                            lines=2,
                            placeholder="e.g. 6 incoming transfers from different individuals within 48 hours, then one large outgoing transfer — is this layering, and does income profile support this?",
                        )
                        with gr.Accordion("💡 Sample Compliance Inquiries (Click to autofill)", open=False):
                            gr.HTML("<div style='font-size:0.75rem; color:#6B7966; margin-bottom:0.45rem;'>Select any benchmark query to test targeted regulatory verification & precedent checks:</div>")
                            query_btn_1 = gr.Button("Query 1: 6 Transfers Layering & Income Check", size="sm", elem_classes="secondary-btn")
                            query_btn_2 = gr.Button("Query 2: FIU-IND Advisory Cross-Check & STR", size="sm", elem_classes="secondary-btn")
                            query_btn_3 = gr.Button("Query 3: Precedent vs Pattern Evolution Check", size="sm", elem_classes="secondary-btn")
                        run_pipeline_button = gr.Button(
                            "▶ Run Multi-Agent AML Investigation",
                            elem_classes="primary-btn",
                            size="lg",
                        )

                # Step 2: Investigation Outcomes Column
                with gr.Column(scale=1):
                    with gr.Column(elem_classes="investigation-panel"):
                        gr.HTML(
                            '<div class="panel-step">'
                            '<span class="panel-step-num">2</span>'
                            "Multi-Agent Investigation Outcomes"
                            "</div>"
                        )
                        # Visual decision badge (HTML, colour-coded)
                        decision_badge = gr.HTML("", elem_classes="decision-badge-container")
                        decision_output = gr.Textbox(
                            label="System Recommended Graded Decision (3-Tier Output)",
                            lines=2,
                            interactive=False,
                        )
                        pdf_download = gr.File(
                            label="Download Regulator-Ready STR (PDF)",
                            visible=False,
                            interactive=False,
                        )
                        with gr.Accordion(
                            "Agent 1: Pattern Detection & Anomaly Analysis", open=True
                        ):
                            pattern_output = gr.Textbox(
                                label="", lines=6, show_label=False, interactive=False
                            )
                        with gr.Accordion(
                            "Agent 2: Typology Matcher & Regulatory Precedent (RAG)", open=True
                        ):
                            typology_output = gr.Textbox(
                                label="", lines=6, show_label=False, interactive=False
                            )
                        with gr.Accordion(
                            "Agent 3: Contextual Risk Scorer & False-Positive Reasoning",
                            open=True,
                        ):
                            risk_output = gr.Textbox(
                                label="", lines=6, show_label=False, interactive=False
                            )
                        str_output = gr.Textbox(
                            label="Agent 4: Generated Regulator-Ready Suspicious Transaction Report (STR)",
                            lines=12,
                            interactive=False,
                        )

    # ──────────────────────────────────────────────────────────────────────────
    # Event Wiring & Robust Session Management
    # ──────────────────────────────────────────────────────────────────────────

    # Login Button & Enter-Key Submissions
    for trigger in [login_button.click, login_username.submit, login_password.submit]:
        trigger(
            login_action,
            inputs=[login_username, login_password],
            outputs=[
                login_page,
                customers_page,
                investigation_page,
                login_error,
                customer_table,
                current_page,
                page_indicator,
                customers_status,
                remarks_panel,
                remarks_editor,
                remarks_customer_label,
                logged_in_user,
                customers_nav,
                dashboard_stats,
                session_state,
            ],
        )

    def on_cell_select(evt: gr.SelectData, table_data, username):
        no_investigation = (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            make_session_payload(username, "customers"),
            "",
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
        )

        if evt is None or evt.index is None:
            return no_investigation

        row_idx, col_idx = evt.index[0], evt.index[1]
        rows = normalize_table(table_data)
        if row_idx >= len(rows):
            return no_investigation

        customer_id = str(rows[row_idx][0])
        customer_name = str(rows[row_idx][1])
        remarks = (
            str(rows[row_idx][REMARKS_COL])
            if rows[row_idx][REMARKS_COL] is not None
            else ""
        )
        if remarks == "—":
            remarks = ""

        if col_idx == AML_COL:
            investigation_nav_html = build_nav_html(
                "AML Investigation Workspace",
                dark=True,
                show_back=True,
                username=username,
            )
            inv_result = load_investigation(customer_id, username=username)
            risk_score = inv_result[5]
            risk_updated_at = inv_result[6]
            header_html = build_investigation_header_html(
                customer_id, customer_name, risk_score, risk_updated_at
            )
            return inv_result + (
                "",
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(value=investigation_nav_html),
                gr.update(value=header_html),
            )

        if col_idx == REMARKS_COL:
            return no_investigation[:19] + (
                customer_id,
                gr.update(visible=True),
                gr.update(value=remarks),
                gr.update(
                    value=f"**Editing remarks for** `{customer_id}` — {customer_name}"
                ),
                gr.update(),
                gr.update(),
            )

        return no_investigation

    customer_table.select(
        on_cell_select,
        inputs=[customer_table, logged_in_user],
        outputs=[
            login_page,
            customers_page,
            investigation_page,
            selected_customer_id,
            selected_customer_name,
            risk_score_box,
            risk_updated_box,
            txn_summary_banner,
            txn_filter_radio,
            transaction_logs,
            kyc_profile,
            past_investigations_box,
            decision_output,
            pattern_output,
            typology_output,
            risk_output,
            str_output,
            pdf_download,
            session_state,
            edit_customer_id,
            remarks_panel,
            remarks_editor,
            remarks_customer_label,
            investigation_nav,
            investigation_header,
        ],
    )

    txn_filter_radio.change(
        toggle_transaction_view,
        inputs=[selected_customer_id, txn_filter_radio],
        outputs=[transaction_logs],
    )

    save_remarks_button.click(
        save_remark_for_customer,
        inputs=[edit_customer_id, remarks_editor, current_page],
        outputs=[customer_table, current_page, page_indicator, customers_status],
    )

    prev_page_btn.click(
        lambda page: change_page(page, -1),
        inputs=[current_page],
        outputs=[customer_table, current_page, page_indicator],
    )

    next_page_btn.click(
        lambda page: change_page(page, 1),
        inputs=[current_page],
        outputs=[customer_table, current_page, page_indicator],
    )

    refresh_scores_button.click(
        refresh_scores_with_stats,
        inputs=[current_page],
        outputs=[
            customer_table,
            current_page,
            page_indicator,
            customers_status,
            dashboard_stats,
        ],
    )

    query_btn_1.click(
        lambda: "6 incoming transfers from different individuals within 48 hours, then one large outgoing transfer — is this layering, and does income profile support this?",
        outputs=[compliance_inquiry_box],
    )
    query_btn_2.click(
        lambda: "This alert matches a typology from last quarter's FIU-IND advisory — cross-check and draft STR if applicable.",
        outputs=[compliance_inquiry_box],
    )
    query_btn_3.click(
        lambda: "Customer was cleared on a similar alert 3 months ago — does precedent apply, or has the pattern changed?",
        outputs=[compliance_inquiry_box],
    )

    run_pipeline_button.click(
        run_investigation,
        inputs=[
            selected_customer_id,
            selected_customer_name,
            transaction_logs,
            kyc_profile,
            past_investigations_box,
            id_upload,
            compliance_inquiry_box,
            logged_in_user,
        ],
        outputs=[
            decision_output,
            pattern_output,
            typology_output,
            risk_output,
            str_output,
            pdf_download,
            session_state,
        ],
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Auto-Restore Active Session on Page Refresh or Tab Re-open
    # ──────────────────────────────────────────────────────────────────────────
    def restore_session_from_browser(session_payload):
        if is_session_valid(session_payload):
            username = str(session_payload.get("username") or "").strip()
            current_view = session_payload.get("current_view", "customers")
            customer_id = session_payload.get("customer_id", "")
            updated_session = make_session_payload(username, current_view, customer_id)

            table, page, indicator = refresh_customer_table(0)
            nav = build_nav_html("Customer Monitoring Dashboard", username=username)

            if current_view == "investigation" and customer_id:
                inv_nav = build_nav_html(
                    "AML Investigation Workspace",
                    dark=True,
                    show_back=True,
                    username=username,
                )
                inv_data = load_investigation(customer_id, username=username)
                customer = get_customer(customer_id)
                customer_name = customer["name"] if customer else ""
                risk_score = inv_data[5]
                risk_updated_at = inv_data[6]
                header_html = build_investigation_header_html(
                    customer_id, customer_name, risk_score, risk_updated_at
                )
                return (
                    gr.update(visible=False),  # login_page
                    gr.update(visible=False),  # customers_page
                    gr.update(visible=True),  # investigation_page
                    gr.update(value="", visible=False),  # login_error
                    gr.update(value=table),  # customer_table
                    0,  # current_page
                    format_page_chip(indicator),  # page_indicator
                    gr.update(value="✓ Active investigation session restored."),
                    gr.update(value="", visible=False),  # remarks_panel
                    gr.update(value=""),  # remarks_editor
                    gr.update(visible=False),  # remarks_customer_label
                    username,  # logged_in_user
                    gr.update(value=nav),  # customers_nav
                    gr.update(value=build_stats_html()),  # dashboard_stats
                    updated_session,  # session_state
                    customer_id,  # selected_customer_id
                    customer_name,  # selected_customer_name
                    inv_data[5],  # risk_score_box
                    inv_data[6],  # risk_updated_box
                    inv_data[7],  # txn_summary_banner
                    inv_data[8],  # txn_filter_radio
                    inv_data[9],  # transaction_logs
                    inv_data[10],  # kyc_profile
                    inv_data[11],  # past_investigations_box
                    gr.update(value=inv_nav),  # investigation_nav
                    gr.update(value=header_html),  # investigation_header
                )

            return (
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(value="", visible=False),
                gr.update(value=table),
                0,
                format_page_chip(indicator),
                gr.update(value="✓ Active compliance session restored."),
                gr.update(value="", visible=False),
                gr.update(value=""),
                gr.update(visible=False),
                username,
                gr.update(value=nav),
                gr.update(value=build_stats_html()),
                updated_session,
                "",  # selected_customer_id
                "",  # selected_customer_name
                "",  # risk_score_box
                "",  # risk_updated_box
                "",  # txn_summary_banner
                "🚨 Flagged AML Alerts Only",  # txn_filter_radio
                "",  # transaction_logs
                "",  # kyc_profile
                "",  # past_investigations_box
                gr.update(value=""),  # investigation_nav
                gr.update(value=""),  # investigation_header
            )

        return (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value="", visible=False),
            gr.update(value=[]),
            0,
            format_page_chip("Page 1 of 1"),
            gr.update(value=""),
            gr.update(value="", visible=False),
            gr.update(value=""),
            gr.update(visible=False),
            "",
            gr.update(value=""),
            gr.update(value=""),
            clear_session_payload(),
            "",
            "",
            "",
            "",
            "",
            "🚨 Flagged AML Alerts Only",
            "",
            "",
            "",
            gr.update(value=""),
            gr.update(value=""),
        )

    demo.load(
        restore_session_from_browser,
        inputs=[session_state],
        outputs=[
            login_page,
            customers_page,
            investigation_page,
            login_error,
            customer_table,
            current_page,
            page_indicator,
            customers_status,
            remarks_panel,
            remarks_editor,
            remarks_customer_label,
            logged_in_user,
            customers_nav,
            dashboard_stats,
            session_state,
            selected_customer_id,
            selected_customer_name,
            risk_score_box,
            risk_updated_box,
            txn_summary_banner,
            txn_filter_radio,
            transaction_logs,
            kyc_profile,
            past_investigations_box,
            investigation_nav,
            investigation_header,
        ],
    )

    back_trigger.click(
        go_back_to_customers,
        inputs=[current_page, logged_in_user],
        outputs=[
            login_page,
            customers_page,
            investigation_page,
            customer_table,
            current_page,
            page_indicator,
            customers_status,
            customers_nav,
            dashboard_stats,
            session_state,
        ],
    )

    logout_trigger.click(
        logout_action,
        outputs=[
            login_page,
            customers_page,
            investigation_page,
            login_error,
            login_username,
            login_password,
            customer_table,
            current_page,
            page_indicator,
            customers_status,
            remarks_panel,
            remarks_editor,
            remarks_customer_label,
            logged_in_user,
            customers_nav,
            investigation_nav,
            dashboard_stats,
            session_state,
        ],
    )


if __name__ == "__main__":
    demo.launch(
        head=HEAD_JS,
        css=THEME_CSS,
        theme=gr.themes.Base(
            primary_hue="green",
            secondary_hue="rose",
            neutral_hue="gray",
            font=gr.themes.GoogleFont("DM Sans"),
        ),
    )

