import time

import gradio as gr
import pandas as pd

from src.database import (
    MAX_CUSTOMERS,
    format_kyc_context,
    format_transaction_logs,
    get_customer,
    get_customers,
    init_db,
    update_customer_remarks,
    validate_user,
)
from src.risk_engine import refresh_all_risk_scores

try:
    from src.orchestration import run_aml_pipeline
except Exception:
    run_aml_pipeline = None

init_db()

SESSION_TIMEOUT_SECONDS = 30 * 60


def clear_session_payload():
    return {"logged_in": False, "username": "", "expires_at": 0}


def make_session_payload(username: str, now: float | None = None):
    username = (username or "").strip()
    if not username:
        return clear_session_payload()
    current_time = time.time() if now is None else now
    return {
        "logged_in": True,
        "username": username,
        "expires_at": current_time + SESSION_TIMEOUT_SECONDS,
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
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --ivory: #F7F3ED;
    --ivory-soft: #FBF9F5;
    --ivory-deep: #EDE4D8;
    --lavender: var(--ivory);
    --lavender-soft: var(--ivory-soft);
    --lavender-deep: var(--ivory-deep);
    --pakistan-green: #143109;
    --pakistan-green-mid: #1c4512;
    --pakistan-green-light: #2a5c1e;
    --sage: #AAAE7F;
    --sage-light: #c5c9a4;
    --sage-muted: rgba(170, 174, 127, 0.45);
    --royal-purple: #7E3F8F;
    --eminence: #7E3F8F;
    --white: #ffffff;
    --text-on-dark:  #FFFFF0;
    --text-on-light: var(--pakistan-green);
    --text-secondary: #4a5c42;
    --text-muted: #7a8a72;
    --bg-base: var(--ivory);
    --bg-elevated: rgba(255, 255, 255, 0.82);
    --border-subtle: rgba(170, 174, 127, 0.35);
    --border-strong: rgba(126, 63, 143, 0.28);
    --accent: var(--royal-purple);
    --accent-hover: var(--eminence);
    --accent-glow: rgba(126, 63, 143, 0.32);
    --purple-glow: rgba(126, 63, 143, 0.25);
    --radius-sm: 12px;
    --radius-md: 18px;
    --radius-lg: 26px;
    --shadow-sm: 0 2px 12px rgba(20, 49, 9, 0.06);
    --shadow-md: 0 8px 32px rgba(20, 49, 9, 0.08);
    --shadow-lg: 0 20px 56px rgba(20, 49, 9, 0.12);
    --shadow-glow: 0 8px 28px var(--accent-glow);
    --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, .gradio-container {
    min-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    font-family: 'Outfit', system-ui, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

.gradio-container {
    background:
        radial-gradient(ellipse 70% 55% at 10% 0%, rgba(129, 85, 155, 0.08), transparent),
        radial-gradient(ellipse 60% 50% at 90% 10%, rgba(170, 174, 127, 0.15), transparent),
        linear-gradient(165deg, var(--lavender-soft) 0%, var(--lavender) 50%, var(--lavender-deep) 100%) !important;
    color: var(--text-on-light) !important;
}

.gradio-container:has(.login-shell) {
    background:
        radial-gradient(ellipse 80% 70% at 15% 20%, rgba(129, 85, 155, 0.22), transparent),
        radial-gradient(ellipse 60% 55% at 85% 75%, rgba(170, 174, 127, 0.12), transparent),
        radial-gradient(ellipse 50% 40% at 50% 50%, rgba(216, 216, 246, 0.06), transparent),
        linear-gradient(155deg, var(--pakistan-green) 0%, #0d2408 55%, #081a05 100%) !important;
}

.gradio-container:has(.investigation-fullpage) {
    background:
        radial-gradient(ellipse 80% 55% at 50% -5%, rgba(126, 63, 143, 0.08), transparent),
        radial-gradient(ellipse 45% 40% at 95% 60%, rgba(170, 174, 127, 0.10), transparent),
        linear-gradient(180deg, var(--ivory-soft) 0%, var(--ivory) 52%, var(--ivory-deep) 100%) !important;
    color: var(--text-on-light) !important;
    max-width: 100% !important;
    padding: 0 !important;
}

footer, .built-with { display: none !important; }

/* ── Layout ── */
.page-shell {
    max-width: 1340px !important;
    margin: 0 auto !important;
    padding: 1.75rem 2rem 2.5rem !important;
}

.login-shell {
    min-height: 100vh !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 2.5rem !important;
    max-width: 100% !important;
}

.investigation-fullpage {
    width: 100% !important;
    max-width: 100% !important;
    min-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
}

.investigation-fullpage > .gr-column { min-height: 100vh !important; }

.investigation-body {
    flex: 1;
    padding: 0 2rem 2.5rem;
    max-width: 1420px;
    margin: 0 auto;
}

/* ── Topbar ── */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.75rem;
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(24px) saturate(1.5);
    -webkit-backdrop-filter: blur(24px) saturate(1.5);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    margin-bottom: 1.75rem;
    box-shadow: var(--shadow-sm);
}

.investigation-fullpage .topbar,
.topbar-dark {
    border-radius: 0 !important;
    margin-bottom: 0 !important;
    background: rgba(255, 255, 255, 0.8) !important;
    border: none !important;
    border-bottom: 1px solid rgba(126, 63, 143, 0.18) !important;
    box-shadow: 0 8px 30px rgba(126, 63, 143, 0.08) !important;
    color: var(--text-on-light) !important;
}

.brand-wrap {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    font-weight: 600;
    font-size: 1.02rem;
    letter-spacing: -0.01em;
}

.brand-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    background: linear-gradient(145deg, var(--royal-purple), var(--eminence));
    color: var(--white);
    font-size: 1.15rem;
    box-shadow: var(--shadow-glow);
}

.brand-subtitle {
    display: block;
    font-size: 0.65rem;
    font-weight: 500;
    color: var(--sage);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 2px;
}

.topbar-dark .brand-subtitle { color: var(--sage-light); }

.nav-actions { display: flex; align-items: center; gap: 0.75rem; }

.nav-pill {
    border: 0;
    border-radius: 999px;
    padding: 0.5rem 1.1rem;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition);
    font-family: inherit;
    letter-spacing: 0.02em;
}

.nav-pill-back {
    background: rgba(170, 174, 127, 0.15);
    color: var(--pakistan-green);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
}

.nav-pill-back:hover {
    background: rgba(170, 174, 127, 0.28);
    transform: translateX(-2px);
}

.topbar-dark .nav-pill-back {
    background: rgba(170, 174, 127, 0.12);
    color: var(--lavender);
    border: 1px solid rgba(170, 174, 127, 0.25);
}

.topbar-dark .nav-pill-back:hover {
    background: rgba(129, 85, 155, 0.25);
    border-color: rgba(129, 85, 155, 0.4);
}

/* ── User menu ── */
.user-menu { position: relative; }

.user-menu-trigger {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0.9rem 0.35rem 0.35rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    background: rgba(255, 255, 255, 0.7);
    color: var(--pakistan-green);
    user-select: none;
    transition: all var(--transition);
    border: 1px solid rgba(126, 63, 143, 0.18);
    appearance: none;
}

.user-menu-trigger:hover,
.user-menu-trigger:focus-visible,
.user-menu:hover .user-menu-trigger,
.user-menu:focus-within .user-menu-trigger {
    background: rgba(126, 63, 143, 0.1);
    box-shadow: var(--shadow-glow);
    outline: none;
}

.topbar-dark .user-menu-trigger {
    background: rgba(126, 63, 143, 0.18);
    color: var(--lavender);
    border-color: rgba(126, 63, 143, 0.35);
}

.topbar-dark .user-menu-trigger:hover,
.topbar-dark .user-menu-trigger:focus-visible,
.topbar-dark .user-menu:hover .user-menu-trigger,
.topbar-dark .user-menu:focus-within .user-menu-trigger {
    background: rgba(126, 63, 143, 0.32);
}

.user-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: linear-gradient(145deg, var(--royal-purple), var(--eminence));
    color: var(--white);
    display: grid;
    place-items: center;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.03em;
}

.user-menu-dropdown {
    display: none;
    position: absolute;
    right: 0;
    top: calc(100% + 0.55rem);
    min-width: 168px;
    background: var(--white);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    z-index: 200;
    animation: dropIn 0.2s ease;
}

@keyframes dropIn {
    from { opacity: 0; transform: translateY(-8px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}

.topbar-dark .user-menu-dropdown {
    background: var(--pakistan-green-mid);
    border-color: rgba(170, 174, 127, 0.25);
}

.user-menu:hover .user-menu-dropdown,
.user-menu:focus-within .user-menu-dropdown,
.user-menu.open .user-menu-dropdown {
    display: block;
}

.user-menu-logout {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    width: 100%;
    border: 0;
    background: transparent;
    padding: 0.75rem 1.1rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--eminence);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    transition: background var(--transition);
}

.user-menu-logout:hover { background: rgba(216, 216, 246, 0.6); }
.topbar-dark .user-menu-logout { color: var(--lavender); }
.topbar-dark .user-menu-logout:hover { background: rgba(129, 85, 155, 0.2); }

/* ── Login ── */
.login-card {
    max-width: 460px !important;
    width: 100% !important;
    background: rgba(255, 255, 255, 0.92) !important;
    backdrop-filter: blur(32px) !important;
    border: 1px solid rgba(216, 216, 246, 0.6) !important;
    border-radius: var(--radius-lg) !important;
    padding: 2.75rem 2.5rem !important;
    box-shadow:
        0 40px 90px rgba(0, 0, 0, 0.4),
        0 0 0 1px rgba(255,255,255,0.15) inset,
        0 0 80px rgba(129, 85, 155, 0.08) !important;
}

.login-hero { text-align: center; margin-bottom: 2rem; }

.login-hero .brand-icon {
    width: 62px;
    height: 62px;
    border-radius: 18px;
    font-size: 1.75rem;
    margin: 0 auto 1.25rem;
}

.login-hero h2 {
    margin: 0;
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 2.15rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--pakistan-green);
    line-height: 1.15;
}

.login-hero p {
    margin: 0.65rem 0 0;
    color: var(--text-secondary);
    font-size: 0.92rem;
    line-height: 1.65;
    font-weight: 400;
}

.login-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 1.15rem;
    padding: 0.35rem 0.9rem;
    border-radius: 999px;
    background: linear-gradient(135deg, rgba(216,216,246,0.7), rgba(170,174,127,0.2));
    color: var(--eminence);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border: 1px solid rgba(129, 85, 155, 0.15);
}

/* ── Panels ── */
.glass-panel {
    background: rgba(255, 255, 255, 0.78) !important;
    backdrop-filter: blur(20px) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
    padding: 1.75rem !important;
    box-shadow: var(--shadow-md) !important;
}

.investigation-panel {
    background: rgba(255, 255, 255, 0.72) !important;
    backdrop-filter: blur(24px) !important;
    border: 1px solid rgba(126, 63, 143, 0.15) !important;
    border-radius: var(--radius-md) !important;
    padding: 1.75rem !important;
    box-shadow: 0 12px 40px rgba(126, 63, 143, 0.08), inset 0 1px 0 rgba(255,255,255,0.8) !important;
    transition: border-color var(--transition), box-shadow var(--transition);
}

.investigation-panel:hover {
    border-color: rgba(126, 63, 143, 0.4) !important;
    box-shadow: 0 16px 48px rgba(126, 63, 143, 0.12), 0 0 0 1px rgba(126, 63, 143, 0.08) !important;
}

/* ── Stats ── */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.15rem;
    margin-bottom: 1.75rem;
}

@media (max-width: 900px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }

.stat-card {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 1.25rem 1.35rem;
    box-shadow: var(--shadow-sm);
    transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
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
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
    border-color: rgba(129, 85, 155, 0.25);
}

.stat-card:hover::before { opacity: 1; }

.stat-label {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: 0.4rem;
}

.stat-value {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1;
    color: var(--pakistan-green);
}

.stat-card.accent .stat-value { color: var(--royal-purple); }
.stat-card.danger .stat-value { color: var(--eminence); }
.stat-card.warning .stat-value { color: #8a7d4a; }
.stat-card.success .stat-value { color: var(--pakistan-green-light); }

.stat-icon {
    float: right;
    width: 38px;
    height: 38px;
    border-radius: 11px;
    display: grid;
    place-items: center;
    font-size: 1rem;
}

.stat-card.accent .stat-icon { background: rgba(129, 85, 155, 0.12); }
.stat-card.danger .stat-icon { background: rgba(126, 63, 143, 0.12); }
.stat-card.warning .stat-icon { background: rgba(170, 174, 127, 0.2); }
.stat-card.success .stat-icon { background: rgba(20, 49, 9, 0.08); }

/* ── Banners ── */
.info-banner {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    color: var(--pakistan-green);
    background: linear-gradient(135deg, rgba(255,255,255,0.7), rgba(216,216,246,0.4));
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 1rem 1.25rem;
    font-size: 0.86rem;
    line-height: 1.6;
    margin-bottom: 1.5rem;
}

.info-banner-icon {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    border-radius: 8px;
    background: linear-gradient(135deg, var(--lavender), rgba(129,85,155,0.15));
    display: grid;
    place-items: center;
    font-size: 0.75rem;
    border: 1px solid rgba(129, 85, 155, 0.12);
}

.error-banner {
    color: var(--eminence);
    background: rgba(216, 216, 246, 0.5);
    border: 1px solid rgba(126, 63, 143, 0.25);
    border-radius: var(--radius-sm);
    padding: 0.8rem 1.1rem;
    font-size: 0.86rem;
    text-align: center;
    font-weight: 500;
}

/* ── Section headers ── */
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.25rem;
}

.section-title {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0;
    color: var(--pakistan-green);
}

.section-badge {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    background: rgba(129, 85, 155, 0.1);
    color: var(--eminence);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border: 1px solid rgba(129, 85, 155, 0.15);
}

.panel-step {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--lavender);
    margin-bottom: 1.15rem;
    letter-spacing: 0.01em;
}

.panel-step-num {
    width: 28px;
    height: 28px;
    border-radius: 9px;
    background: linear-gradient(145deg, var(--royal-purple), var(--eminence));
    color: var(--white);
    display: grid;
    place-items: center;
    font-family: 'Outfit', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
}

/* ── Investigation ── */
.investigation-hero {
    text-align: center;
    padding: 2rem 0 1.75rem;
}

.investigation-hero h1 {
    margin: 0;
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, var(--white) 0%, var(--lavender) 60%, var(--sage-light) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.investigation-hero p {
    margin: 0.6rem 0 0;
    color: var(--sage);
    font-size: 0.9rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-weight: 500;
}

.case-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
    background: linear-gradient(135deg, rgba(20,49,9,0.8), rgba(30,60,20,0.6));
    border: 1px solid rgba(170, 174, 127, 0.25);
    border-radius: var(--radius-md);
    padding: 1.15rem 1.5rem;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(16px);
}

.case-info { display: flex; align-items: center; gap: 1rem; }

.case-avatar {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: linear-gradient(145deg, rgba(129,85,155,0.35), rgba(126,63,143,0.25));
    border: 1px solid rgba(170, 174, 127, 0.3);
    display: grid;
    place-items: center;
    font-size: 1.25rem;
}

.case-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--sage-light);
    font-weight: 500;
    letter-spacing: 0.04em;
}

.case-name {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--white);
    margin-top: 3px;
}

.risk-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.risk-badge.low {
    background: rgba(170, 174, 127, 0.2);
    color: var(--sage-light);
    border: 1px solid rgba(170, 174, 127, 0.35);
}

.risk-badge.medium {
    background: rgba(129, 85, 155, 0.2);
    color: var(--lavender);
    border: 1px solid rgba(129, 85, 155, 0.35);
}

.risk-badge.high {
    background: rgba(126, 63, 143, 0.25);
    color: #e8c4f0;
    border: 1px solid rgba(126, 63, 143, 0.45);
}

.risk-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
    animation: pulse 2.5s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.55; transform: scale(0.85); }
}

/* ── Buttons ── */
.action-btn, .primary-btn {
    border: 0 !important;
    border-radius: var(--radius-sm) !important;
    color: var(--white) !important;
    background: linear-gradient(145deg, var(--royal-purple), var(--eminence)) !important;
    font-weight: 600 !important;
    font-family: 'Outfit', sans-serif !important;
    padding: 0.7rem 1.5rem !important;
    box-shadow: var(--shadow-glow) !important;
    transition: all var(--transition) !important;
    letter-spacing: 0.03em !important;
}

.action-btn:hover, .primary-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 32px var(--accent-glow) !important;
    filter: brightness(1.06) !important;
}

.secondary-btn {
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
    background: rgba(255, 255, 255, 0.85) !important;
    color: var(--pakistan-green) !important;
    font-weight: 600 !important;
    font-family: 'Outfit', sans-serif !important;
    transition: all var(--transition) !important;
    letter-spacing: 0.02em !important;
}

.secondary-btn:hover {
    background: var(--lavender-soft) !important;
    border-color: rgba(129, 85, 155, 0.3) !important;
    color: var(--eminence) !important;
}

.pagination-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.15rem;
    margin-top: 1rem;
}

.page-chip {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-secondary);
    padding: 0.4rem 1rem;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 999px;
    border: 1px solid var(--border-subtle);
    letter-spacing: 0.02em;
}

/* ── Dataframe ── */
.gr-dataframe {
    border-radius: var(--radius-sm) !important;
    overflow: hidden !important;
    border: 1px solid var(--border-subtle) !important;
    box-shadow: var(--shadow-sm) !important;
    background: rgba(255, 255, 255, 0.5) !important;
}

.gr-dataframe table { font-size: 0.84rem !important; }

.gr-dataframe thead th {
    background: linear-gradient(180deg, rgba(255,255,255,0.95), var(--lavender-soft)) !important;
    font-weight: 600 !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--pakistan-green) !important;
    padding: 0.85rem 1.1rem !important;
    border-bottom: 1px solid var(--border-subtle) !important;
}

.gr-dataframe tbody td {
    padding: 0.75rem 1.1rem !important;
    border-bottom: 1px solid rgba(170, 174, 127, 0.15) !important;
    transition: background var(--transition) !important;
    color: var(--pakistan-green) !important;
}

.gr-dataframe tbody tr:hover td {
    background: rgba(216, 216, 246, 0.35) !important;
    cursor: pointer !important;
}

.gr-dataframe tbody tr:last-child td { border-bottom: none !important; }

/* ── Investigation inputs ── */
.investigation-fullpage label {
    color: var(--sage) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

.investigation-fullpage textarea,
.investigation-fullpage input[type="text"] {
    background: rgba(255, 255, 255, 0.8) !important;
    border: 1px solid rgba(126, 63, 143, 0.2) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--pakistan-green) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
}

.investigation-fullpage .accordion {
    background: rgba(255, 255, 255, 0.62) !important;
    border: 1px solid rgba(126, 63, 143, 0.15) !important;
    border-radius: var(--radius-sm) !important;
}

.investigation-fullpage .label-wrap span {
    color: var(--pakistan-green) !important;
    font-weight: 500 !important;
}

.remarks-panel-inner {
    margin-top: 1.15rem;
    padding: 1.25rem;
    background: linear-gradient(135deg, rgba(216,216,246,0.35), rgba(255,255,255,0.6));
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
}

.status-toast {
    font-size: 0.84rem;
    color: var(--royal-purple);
    font-weight: 600;
    padding: 0.5rem 0;
    letter-spacing: 0.02em;
}
"""


PAGE_SIZE = 10
TABLE_HEADERS = [
    "Customer ID",
    "Name",
    "Branch",
    "Risk Score",
    "Remarks",
    "AML Investigation",
]
REMARKS_COL = 4
AML_COL = 5


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
            <div class="stat-label">Total Customers</div>
            <div class="stat-value">{total}</div>
        </div>
        <div class="stat-card danger">
            <div class="stat-icon">💎</div>
            <div class="stat-label">High Risk</div>
            <div class="stat-value">{high}</div>
        </div>
        <div class="stat-card warning">
            <div class="stat-icon">🔮</div>
            <div class="stat-label">Medium Risk</div>
            <div class="stat-value">{medium}</div>
        </div>
        <div class="stat-card success">
            <div class="stat-icon">🌿</div>
            <div class="stat-label">Avg Risk Score</div>
            <div class="stat-value">{avg}</div>
        </div>
    </div>
    """


def build_investigation_header_html(customer_id: str, name: str, risk_score: str) -> str:
    label, css_class = risk_tier(risk_score)
    return f"""
    <div class="case-banner">
        <div class="case-info">
            <div class="case-avatar">👤</div>
            <div>
                <div class="case-id">{customer_id}</div>
                <div class="case-name">{name}</div>
            </div>
        </div>
        <div class="risk-badge {css_class}">
            <span class="risk-dot"></span>
            Risk {risk_score} · {label}
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
        icon = "🌿" if label == "Low" else "🔮" if label == "Medium" else "💎"
        rows.append([
            customer["customer_id"],
            customer["name"],
            customer["branch"],
            f"{icon} {score} ({label})",
            customer["remarks"] or "—",
            "🔍 Investigate",
        ])
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
        return table, page, format_page_chip(indicator), "Select a customer remarks cell to edit."

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
    back_label = "← Back"
    back_btn = ""
    if show_back:
        back_btn = (
            f'<button class="nav-pill nav-pill-back" '
            f'onclick="document.getElementById(\'{back_trigger_id}\').click()">{back_label}</button>'
        )
    display_name = username or "User"
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
                        onclick="const menu = this.closest('.user-menu'); const isOpen = menu.classList.toggle('open'); this.setAttribute('aria-expanded', String(isOpen));">
                    <div class="user-avatar">{initials}</div>
                    <span>{display_name}</span>
                </button>
                <div class="user-menu-dropdown">
                    <button type="button" class="user-menu-logout" onclick="const menu = this.closest('.user-menu'); menu.classList.remove('open'); const trigger = menu.querySelector('.user-menu-trigger'); trigger && trigger.setAttribute('aria-expanded', 'false'); document.getElementById('logout-trigger').click();">
                        <span aria-hidden="true">🚪</span>
                        <span>Sign Out</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
    """


def load_investigation(customer_id: str):
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
            empty,
            empty,
            empty,
            empty,
            empty,
        )

    refresh_all_risk_scores()
    customer = get_customer(customer_id)
    txn_logs = format_transaction_logs(customer_id)
    kyc_context = format_kyc_context(customer_id)

    return (
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=True),
        customer_id,
        customer["name"],
        str(customer["risk_score"]),
        customer.get("risk_updated_at", ""),
        txn_logs,
        kyc_context,
        "",
        "",
        "",
        "",
        "",
    )


def run_investigation(customer_id, txn_logs, kyc_context, id_file):
    if not customer_id:
        return (
            "No customer selected.",
            "",
            "",
            "",
            "",
        )

    if run_aml_pipeline is None:
        return (
            "Pipeline unavailable. Configure OpenAI API key to run agents.",
            "Pattern detection requires API configuration.",
            "Typology matcher requires API configuration.",
            "Risk scorer requires API configuration.",
            "STR generator requires API configuration.",
        )

    try:
        decision, patterns, typologies, risk_analysis, str_report = run_aml_pipeline(
            txn_logs,
            kyc_context,
            id_file,
        )
    except Exception as error:
        error_text = str(error).lower()
        error_type = type(error).__name__
        is_quota_error = (
            error_type == "OpenAIRateLimitError"
            or "insufficient_quota" in error_text
            or "no credits remaining" in error_text
        )
        if not is_quota_error:
            raise
        message = (
            "OpenAI API quota exhausted. Add credits or use an account with available "
            "billing quota, then retry the investigation."
        )
        return "Pipeline unavailable", message, message, message, message

    return decision, patterns, typologies, risk_analysis, str_report


def login_action(username_value, password_value):
    if validate_user(username_value, password_value):
        session_payload = make_session_payload(username_value)
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
            gr.update(value="✓ Risk scores refreshed at login."),
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
        gr.update(value='<div class="error-banner">Invalid credentials. Please try again.</div>', visible=True),
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
    )


def refresh_scores_with_stats(page: int):
    table, page_num, indicator = refresh_customer_table(page)
    return (
        table,
        page_num,
        format_page_chip(indicator),
        "✓ Risk scores recalculated from transactions, activity, and KYC.",
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


with gr.Blocks(title="AML Investigation Assistant") as demo:
    current_page = gr.State(0)
    edit_customer_id = gr.State("")
    logged_in_user = gr.State("")
    session_state = gr.BrowserState(default_value=clear_session_payload(), storage_key="aml_session_state")

    back_trigger = gr.Button("Back", elem_id="back-trigger", visible=False)
    logout_trigger = gr.Button("Logout", elem_id="logout-trigger", visible=False)

    login_page = gr.Column(visible=True, elem_classes="login-shell")
    customers_page = gr.Column(visible=False, elem_classes="page-shell")
    investigation_page = gr.Column(
        visible=False,
        elem_classes="investigation-fullpage investigation-theme",
    )

    with login_page:
        with gr.Column(elem_classes="glass-panel login-card"):
            gr.HTML(
                """
                <div class="login-hero">
                    <div class="brand-icon">🛡️</div>
                    <h2>AML Compliance Portal</h2>
                    <p>Streamline AML investigations, monitor customer risk, and automate regulatory compliance—all in one secure workspace</p>
                    <div class="login-badge">✦ Bank-Grade Security & Privacy</div>
                </div>
                """
            )
            login_username = gr.Textbox(label="Username", placeholder="Enter your username")
            login_password = gr.Textbox(label="Password", placeholder="Enter your password", type="password")
            login_error = gr.HTML("", visible=False)
            login_button = gr.Button("Sign In to Dashboard", elem_classes="action-btn", size="lg")

    with customers_page:
        customers_nav = gr.HTML(build_nav_html("Customer Monitoring Dashboard"))
        dashboard_stats = gr.HTML(build_stats_html())
        gr.HTML(
            '<div class="info-banner">'
            '<div class="info-banner-icon">ℹ️</div>'
            '<div>Click <b>Remarks</b> to edit analyst notes. '
            f'Click <b>🔍 Investigate</b> to launch the AML pipeline. '
            f'Showing {PAGE_SIZE} customers per page · max {MAX_CUSTOMERS} total.</div>'
            '</div>'
        )

        with gr.Column(elem_classes="glass-panel"):
            gr.HTML(
                '<div class="section-header">'
                '<div class="section-title">Customer Risk Directory</div>'
                '<div class="section-badge">Live Scores</div>'
                '</div>'
            )
            initial_table, _, initial_indicator = refresh_customer_table(0)
            customer_table = gr.Dataframe(
                headers=TABLE_HEADERS,
                value=initial_table,
                interactive=False,
                wrap=True,
                datatype=["str", "str", "str", "str", "str", "str"],
            )
            with gr.Row(elem_classes="pagination-row"):
                prev_page_btn = gr.Button("◀ Previous", elem_classes="secondary-btn", scale=1)
                page_indicator = gr.HTML(format_page_chip(initial_indicator))
                next_page_btn = gr.Button("Next ▶", elem_classes="secondary-btn", scale=1)
            with gr.Column(visible=False, elem_classes="remarks-panel-inner") as remarks_panel:
                remarks_customer_label = gr.Markdown("")
                remarks_editor = gr.Textbox(
                    label="Edit Remarks",
                    lines=3,
                    placeholder="Update remarks for selected customer...",
                )
                save_remarks_button = gr.Button("Save Remarks", elem_classes="action-btn")
            with gr.Row():
                refresh_scores_button = gr.Button("↻ Refresh Risk Scores", elem_classes="secondary-btn")
            customers_status = gr.Markdown("", elem_classes="status-toast")

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
            investigation_header = gr.HTML("")

            selected_customer_id = gr.Textbox(visible=False)
            selected_customer_name = gr.Textbox(visible=False)

            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Column(elem_classes="investigation-panel"):
                        gr.HTML(
                            '<div class="panel-step">'
                            '<span class="panel-step-num">1</span>'
                            'Case Inputs'
                            '</div>'
                        )
                        risk_score_box = gr.Textbox(label="Current Risk Score", interactive=False)
                        risk_updated_box = gr.Textbox(label="Risk Score Updated At", interactive=False)
                        transaction_logs = gr.Textbox(
                            label="Transaction History Logs",
                            lines=10,
                            interactive=False,
                        )
                        kyc_profile = gr.Textbox(
                            label="KYC Profile Context",
                            lines=5,
                            interactive=False,
                        )
                        id_upload = gr.File(
                            label="Multimodal Input: ID / Passport File (Optional)",
                            file_types=["image"],
                        )
                        run_pipeline_button = gr.Button(
                            "▶ Run AML Investigation Pipeline",
                            elem_classes="primary-btn",
                            size="lg",
                        )

                with gr.Column(scale=1):
                    with gr.Column(elem_classes="investigation-panel"):
                        gr.HTML(
                            '<div class="panel-step">'
                            '<span class="panel-step-num">2</span>'
                            'Investigation Outcomes'
                            '</div>'
                        )
                        decision_output = gr.Textbox(label="System Recommended Decision", lines=2)
                        with gr.Accordion("Pattern Detection Agent Output", open=True):
                            pattern_output = gr.Textbox(label="", lines=6, show_label=False)
                        with gr.Accordion("Typology Matcher Agent Output (RAG)", open=False):
                            typology_output = gr.Textbox(label="", lines=6, show_label=False)
                        with gr.Accordion("Contextual Risk Scorer Output", open=False):
                            risk_output = gr.Textbox(label="", lines=6, show_label=False)
                        str_output = gr.Textbox(label="Generated Suspicious Transaction Report (STR)", lines=8)

    login_button.click(
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
        remarks = str(rows[row_idx][REMARKS_COL]) if rows[row_idx][REMARKS_COL] is not None else ""
        if remarks == "—":
            remarks = ""

        if col_idx == AML_COL:
            investigation_nav_html = build_nav_html(
                "AML Investigation Workspace",
                dark=True,
                show_back=True,
                username=username,
            )
            inv_result = load_investigation(customer_id)
            risk_score = inv_result[5]
            header_html = build_investigation_header_html(customer_id, customer_name, risk_score)
            return inv_result + (
                "",
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(value=investigation_nav_html),
                gr.update(value=header_html),
            )

        if col_idx == REMARKS_COL:
            return no_investigation[:14] + (
                customer_id,
                gr.update(visible=True),
                gr.update(value=remarks),
                gr.update(value=f"**Editing remarks for** `{customer_id}` — {customer_name}"),
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
            transaction_logs,
            kyc_profile,
            decision_output,
            pattern_output,
            typology_output,
            risk_output,
            str_output,
            edit_customer_id,
            remarks_panel,
            remarks_editor,
            remarks_customer_label,
            investigation_nav,
            investigation_header,
        ],
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
        outputs=[customer_table, current_page, page_indicator, customers_status, dashboard_stats],
    )

    run_pipeline_button.click(
        run_investigation,
        inputs=[selected_customer_id, transaction_logs, kyc_profile, id_upload],
        outputs=[decision_output, pattern_output, typology_output, risk_output, str_output],
    )

    def restore_session_from_browser(session_payload):
        if is_session_valid(session_payload):
            username = str(session_payload.get("username") or "").strip()
            session_payload = make_session_payload(username)
            table, page, indicator = refresh_customer_table(0)
            nav = build_nav_html("Customer Monitoring Dashboard", username=username)
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(value="", visible=False),
                gr.update(value=table),
                0,
                format_page_chip(indicator),
                gr.update(value="✓ Active session restored."),
                gr.update(value="", visible=False),
                gr.update(value=""),
                gr.update(visible=False),
                username,
                gr.update(value=nav),
                gr.update(value=build_stats_html()),
                session_payload,
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
        css=THEME_CSS,
        theme=gr.themes.Base(
            primary_hue="green",
            secondary_hue="rose",
            neutral_hue="gray",
            font=gr.themes.GoogleFont("DM Sans"),
        ),
    )
