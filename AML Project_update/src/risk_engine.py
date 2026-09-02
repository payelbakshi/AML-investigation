"""
Dynamic AML Risk Scoring Engine
================================
Replaces fixed binary flags with proportional, severity-scaled scoring.

Signal categories and their max contributions:
  • Income Disproportion       : 0 – 25 pts  (scales with income multiple)
  • Structuring / Smurfing     : 0 – 35 pts  (needs repeated near-threshold deposits)
  • Cash Deposit Frequency     : 0 – 12 pts
  • Offshore / High-Risk CTP   : 0 – 20 pts
  • Fund Velocity / Pass-Through: 0 – 25 pts  (combines speed + round-trip ratio)
  • Transaction Velocity       : 0 – 18 pts  (scales with # of txns in short window)
  • Prior Investigation History: 0 – 12 pts
  • New Account + High Inflow  : 0 – 12 pts
  • Multi-source Aggregation   : 0 – 15 pts  (many different payers → one outflow)
                                  ─────────
  Base                                10 pts
  Max theoretical total             ~184 pts  → clamped to 100
"""
from datetime import datetime, timezone

from src.database import (
    get_customers,
    get_kyc_profile,
    get_transactions,
    update_customer_risk,
)

# ── Counterparty keywords indicating elevated risk ──────────────────────────
_HIGH_RISK_CTP_KEYWORDS = {
    "offshore", "shell", "anonymous", "unknown", "crypto", "exchange",
    "bitcoin", "cayman", "panama", "bvi", "seychelles", "mauritius",
    "dubai trading", "hong kong", "singapore", "uae", "bahrain",
}

_SWIFT_TXN_TYPES = {"swift", "international wire", "foreign remittance"}


def _parse_txn_datetime(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _is_high_risk_counterparty(txn: dict) -> bool:
    """Returns True if the transaction counterparty or description suggests high-risk exposure."""
    ctp = (txn.get("counterparty") or "").lower()
    desc = (txn.get("description") or "").lower()
    txn_type = (txn.get("txn_type") or "").lower()
    combined = f"{ctp} {desc} {txn_type}"
    if any(kw in combined for kw in _HIGH_RISK_CTP_KEYWORDS):
        return True
    if any(kw in txn_type for kw in _SWIFT_TXN_TYPES):
        return True
    return False


def calculate_risk_score(customer_id: str) -> tuple[int, str]:
    """
    Calculates a dynamic, proportional AML risk score (0–100) for a customer.

    Returns:
        (score: int, explanation: str)
    """
    transactions = get_transactions(customer_id)
    kyc = get_kyc_profile(customer_id)

    score = 10  # base score
    signals: list[str] = []

    if not transactions:
        return 10, "No recent transaction activity — baseline score."

    monthly_income = float(kyc.get("declared_monthly_income", 0) or 0)
    account_age = int(kyc.get("account_age_months", 0) or 0)
    investigations = kyc.get("past_investigations", [])

    total_in = sum(txn["amount"] for txn in transactions if txn["amount"] > 0)
    total_out = abs(sum(txn["amount"] for txn in transactions if txn["amount"] < 0))
    txn_count = len(transactions)

    cash_deposits = [
        txn for txn in transactions
        if "cash deposit" in txn.get("txn_type", "").lower()
    ]

    # ── 1. INCOME DISPROPORTION: Scale by income multiple (max +25) ──────────
    if monthly_income > 0 and total_in > 0:
        income_ratio = total_in / monthly_income
        if income_ratio >= 10:
            income_pts = 25
            signals.append(
                f"Inbound volume is {income_ratio:.1f}× declared monthly income (extreme disproportion)."
            )
        elif income_ratio >= 5:
            income_pts = 18
            signals.append(
                f"Inbound volume is {income_ratio:.1f}× declared monthly income (severe disproportion)."
            )
        elif income_ratio >= 3:
            income_pts = 10
            signals.append(
                f"Inbound volume is {income_ratio:.1f}× declared monthly income (notable disproportion)."
            )
        else:
            income_pts = 0  # ≤3× is explainable (salary + bonus, etc.)

        # Low-income customers: an absolute floor on suspicious inflow amount
        # (e.g. a student receiving $500 more than income is not alarming)
        if income_pts > 0 and total_in < 5000:
            income_pts = max(0, income_pts - 8)  # partial relief for very small amounts
            signals[-1] += " [Reduced: absolute inflow amount is small.]"

        score += income_pts

    # ── 2. STRUCTURING (SMURFING): Near-threshold cash deposits (max +35) ────
    near_threshold = [
        txn for txn in cash_deposits if 9000 <= abs(txn["amount"]) <= 9999
    ]
    if len(near_threshold) >= 3:
        score += 35
        signals.append(
            f"Repeated structuring pattern: {len(near_threshold)} cash deposits near $10k threshold."
        )
    elif len(near_threshold) == 2:
        score += 25
        signals.append(
            "Two near-threshold cash deposits detected — potential structuring / smurfing."
        )
    elif len(near_threshold) == 1:
        score += 8
        signals.append("Single near-threshold cash deposit — monitor for recurrence.")

    # ── 3. CASH DEPOSIT FREQUENCY (max +12) ──────────────────────────────────
    if len(cash_deposits) >= 5:
        score += 12
        signals.append(f"Very high cash deposit frequency: {len(cash_deposits)} deposits.")
    elif len(cash_deposits) >= 3:
        score += 7
        signals.append(f"Elevated cash deposit frequency: {len(cash_deposits)} deposits.")

    # ── 4. OFFSHORE / HIGH-RISK COUNTERPARTY (max +20) ───────────────────────
    high_risk_txns = [txn for txn in transactions if _is_high_risk_counterparty(txn)]
    if high_risk_txns:
        ctp_pts = min(20, 12 + (len(high_risk_txns) - 1) * 4)
        score += ctp_pts
        ctps = list({(txn.get("counterparty") or "Unknown") for txn in high_risk_txns})
        signals.append(
            f"High-risk counterparty/offshore exposure: {', '.join(ctps[:3])}."
        )

    # ── 5. FUND VELOCITY / PASS-THROUGH RATIO (max +25) ──────────────────────
    if total_in > 0 and total_out > 0:
        pass_through_ratio = total_out / total_in
        if pass_through_ratio >= 0.95:
            score += 25
            signals.append(
                f"Near-complete pass-through: {pass_through_ratio:.0%} of inflows immediately transferred out."
            )
        elif pass_through_ratio >= 0.80:
            score += 18
            signals.append(
                f"High pass-through ratio: {pass_through_ratio:.0%} of inflows transferred out rapidly."
            )
        elif pass_through_ratio >= 0.60:
            score += 8
            signals.append(
                f"Moderate pass-through ratio: {pass_through_ratio:.0%} of inflows transferred out."
            )

    # ── 6. TRANSACTION VELOCITY WITHIN SHORT WINDOW (max +18) ────────────────
    parsed_times = [_parse_txn_datetime(t["txn_datetime"]) for t in transactions]
    parsed_times = [dt for dt in parsed_times if dt is not None]
    if len(parsed_times) >= 2:
        window_hours = (max(parsed_times) - min(parsed_times)).total_seconds() / 3600
        if window_hours <= 48 and txn_count >= 3:
            velocity_pts = min(18, 6 + (txn_count - 3) * 3)
            score += velocity_pts
            signals.append(
                f"{txn_count} transactions in {window_hours:.0f} hours — elevated velocity."
            )

    # ── 7. MULTI-SOURCE AGGREGATION → SINGLE OUTFLOW (layering signal, max +15)
    inbound_txns = [t for t in transactions if t["amount"] > 0]
    outbound_txns = [t for t in transactions if t["amount"] < 0]
    if len(inbound_txns) >= 4 and len(outbound_txns) == 1:
        # Multiple sources, single drain — classic layering pass-through
        unique_payers = len({(t.get("counterparty") or "") for t in inbound_txns})
        if unique_payers >= 3:
            score += 15
            signals.append(
                f"Multi-source aggregation: {unique_payers} distinct inflow sources → single outbound transfer (layering indicator)."
            )

    # ── 8. PRIOR INVESTIGATION HISTORY (max +12) ─────────────────────────────
    if investigations:
        # Differentiate: cleared vs unresolved
        unresolved = [i for i in investigations if "cleared" not in i.lower() and "no str" not in i.lower()]
        if unresolved:
            score += 12
            signals.append(f"Prior investigation on file (unresolved): {unresolved[0]}")
        else:
            score += 5
            signals.append("Prior investigation on file (previously cleared).")

    # ── 9. NEW ACCOUNT + DISPROPORTIONATE INFLOW (max +12) ───────────────────
    if account_age <= 3 and total_in > 15000:
        score += 12
        signals.append(
            f"New account ({account_age} months) with ${total_in:,.0f} inflow — disproportionate for account age."
        )
    elif account_age <= 6 and total_in > 25000:
        score += 8
        signals.append(
            f"Young account ({account_age} months) with very high inflow (${total_in:,.0f})."
        )

    # ── Final clamp ───────────────────────────────────────────────────────────
    score = max(0, min(100, score))

    if not signals:
        signals.append("Routine activity — all signals within normal KYC-aligned range.")

    summary = " | ".join(signals)
    return score, summary


def refresh_all_risk_scores() -> list[dict]:
    updated_customers = []
    for customer in get_customers():
        risk_score, summary = calculate_risk_score(customer["customer_id"])
        update_customer_risk(customer["customer_id"], risk_score)
        updated_customers.append(
            {
                **customer,
                "risk_score": risk_score,
                "risk_updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
    return updated_customers
