from datetime import datetime, timezone

from src.database import (
    get_customers,
    get_kyc_profile,
    get_transactions,
    update_customer_risk,
)


def _parse_txn_datetime(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def calculate_risk_score(customer_id: str) -> tuple[int, str]:
    transactions = get_transactions(customer_id)
    kyc = get_kyc_profile(customer_id)

    score = 10
    signals: list[str] = []

    if not transactions:
        return 15, "No recent transaction activity detected."

    total_in = sum(txn["amount"] for txn in transactions if txn["amount"] > 0)
    total_out = abs(sum(txn["amount"] for txn in transactions if txn["amount"] < 0))
    cash_deposits = [
        txn for txn in transactions if txn["txn_type"].lower() == "cash deposit"
    ]
    international = [
        txn
        for txn in transactions
        if "international" in txn["description"].lower()
        or "offshore" in txn["counterparty"].lower()
        or "swift" in txn["txn_type"].lower()
    ]

    monthly_income = float(kyc.get("declared_monthly_income", 0) or 0)
    if monthly_income and total_in > monthly_income * 3:
        score += 25
        signals.append("Inbound volume exceeds declared income profile.")

    near_threshold = [
        txn
        for txn in cash_deposits
        if 9000 <= txn["amount"] <= 9999
    ]
    if len(near_threshold) >= 2:
        score += 30
        signals.append("Repeated cash deposits near reporting threshold (structuring signal).")

    if len(cash_deposits) >= 3:
        score += 12
        signals.append("Elevated cash deposit frequency.")

    if international:
        score += 18
        signals.append("International or offshore counterparty exposure.")

    if total_out > 0 and total_in > 0 and total_out >= total_in * 0.8:
        score += 15
        signals.append("Rapid movement of recently received funds.")

    parsed_times = [_parse_txn_datetime(txn["txn_datetime"]) for txn in transactions]
    parsed_times = [value for value in parsed_times if value is not None]
    if len(parsed_times) >= 2:
        window_hours = (max(parsed_times) - min(parsed_times)).total_seconds() / 3600
        if window_hours <= 48 and len(transactions) >= 4:
            score += 20
            signals.append("High-velocity activity within 48 hours.")

    investigations = kyc.get("past_investigations", [])
    if investigations:
        score += 10
        signals.append("Prior investigation history on file.")

    account_age = int(kyc.get("account_age_months", 0) or 0)
    if account_age <= 3 and total_in > 15000:
        score += 12
        signals.append("New account with disproportionate inflows.")

    score = max(0, min(100, score))
    if not signals:
        signals.append("Routine activity aligned with KYC profile.")

    summary = " | ".join(signals)
    return score, summary


def refresh_all_risk_scores() -> list[dict]:
    updated_customers = []
    for customer in get_customers():
        risk_score, summary = calculate_risk_score(customer["customer_id"])
        remarks = customer.get("remarks") or summary
        update_customer_risk(customer["customer_id"], risk_score)
        updated_customers.append(
            {
                **customer,
                "risk_score": risk_score,
                "risk_updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
    return updated_customers
