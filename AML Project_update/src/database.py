import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone

from src.config import PROJECT_ROOT

DB_PATH = str(PROJECT_ROOT / "aml_auth.db")
KYC_DIR = PROJECT_ROOT / "data" / "kyc"
MAX_CUSTOMERS = 25
VALID_USERNAME = "Payel"
VALID_PASSWORD = "00000"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    KYC_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )

    customer_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(customers)").fetchall()
    }
    if customer_columns and "risk_updated_at" not in customer_columns:
        cursor.execute("DROP TABLE IF EXISTS transactions")
        cursor.execute("DROP TABLE IF EXISTS customers")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            branch TEXT NOT NULL,
            risk_score INTEGER NOT NULL DEFAULT 0,
            remarks TEXT NOT NULL DEFAULT '',
            risk_updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            txn_datetime TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            txn_type TEXT NOT NULL,
            counterparty TEXT DEFAULT '',
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
        """
    )

    password_hash = _hash_password(VALID_PASSWORD)
    cursor.execute("DELETE FROM users WHERE username != ?", (VALID_USERNAME,))
    cursor.execute(
        "INSERT OR REPLACE INTO users (username, password_hash) VALUES (?, ?)",
        (VALID_USERNAME, password_hash),
    )

    conn.commit()
    conn.close()

    from src.seed_data import seed_database

    seed_database()


def validate_user(username: str, password: str) -> bool:
    if not username or not password:
        return False

    conn = get_connection()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    conn.close()

    if row is None:
        return False

    expected_hash = row["password_hash"]
    provided_hash = _hash_password(password)
    return secrets.compare_digest(expected_hash, provided_hash)


def get_customers(limit: int = MAX_CUSTOMERS) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT customer_id, name, branch, risk_score, remarks, risk_updated_at
        FROM customers
        ORDER BY risk_score DESC, customer_id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_customer(customer_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT customer_id, name, branch, risk_score, remarks, risk_updated_at
        FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_customer_risk(customer_id: str, risk_score: int, remarks: str | None = None) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    conn = get_connection()
    if remarks is None:
        conn.execute(
            "UPDATE customers SET risk_score = ?, risk_updated_at = ? WHERE customer_id = ?",
            (risk_score, now, customer_id),
        )
    else:
        conn.execute(
            """
            UPDATE customers
            SET risk_score = ?, remarks = ?, risk_updated_at = ?
            WHERE customer_id = ?
            """,
            (risk_score, remarks, now, customer_id),
        )
    conn.commit()
    conn.close()


def update_customer_remarks(customer_id: str, remarks: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE customers SET remarks = ? WHERE customer_id = ?",
        (remarks, customer_id),
    )
    conn.commit()
    conn.close()


def get_transactions(customer_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT txn_datetime, description, amount, txn_type, counterparty
        FROM transactions
        WHERE customer_id = ?
        ORDER BY txn_datetime DESC
        """,
        (customer_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_annotated_transactions(customer_id: str) -> dict:
    transactions = get_transactions(customer_id)
    kyc = get_kyc_profile(customer_id)
    monthly_income = float(kyc.get("declared_monthly_income", 0) or 0)

    annotated = []
    alert_count = 0
    total_alert_amount = 0.0

    for txn in reversed(transactions):
        amount = txn["amount"]
        abs_amount = abs(amount)
        txn_type = txn["txn_type"].lower()
        desc = txn["description"].lower()
        counterparty = txn.get("counterparty", "") or ""
        counterparty_lower = counterparty.lower()

        flags = []
        is_alert = False

        if "cash deposit" in txn_type and 9000 <= abs_amount <= 9999:
            flags.append("STRUCTURING (Near $10k reporting limit)")
            is_alert = True
        elif "cash deposit" in txn_type and abs_amount >= 10000:
            flags.append("LARGE CASH DEPOSIT (CTR Threshold exceeded)")
            is_alert = True

        if "swift" in txn_type or "international" in desc or "offshore" in counterparty_lower:
            flags.append("OFFSHORE / SWIFT EXPOSURE")
            is_alert = True

        if amount > 0 and monthly_income > 0 and amount >= (monthly_income * 2):
            flags.append("DISPROPORTIONATE INFLOW (Exceeds monthly income)")
            is_alert = True

        if is_alert:
            alert_count += 1
            total_alert_amount += abs_amount
            tag = "🚨 [AML ALERT: " + " | ".join(flags) + "]"
        else:
            tag = "🟢 [ROUTINE ACTIVITY]"

        sign = "-" if amount < 0 else "+"
        formatted_line = (
            f"{tag}\n"
            f"  📅 {txn['txn_datetime']} | {sign}${abs_amount:,.2f} {txn['txn_type']} | {txn['description']} (Counterparty: {counterparty or 'N/A'})\n"
        )
        annotated.append({
            "is_alert": is_alert,
            "datetime": txn["txn_datetime"],
            "amount": amount,
            "formatted_amount": f"{sign}${abs_amount:,.2f}",
            "txn_type": txn["txn_type"],
            "description": txn["description"],
            "counterparty": counterparty or "N/A",
            "tag": tag,
            "flags": flags,
            "formatted_line": formatted_line
        })

    full_log_lines = [item["formatted_line"] for item in annotated]
    flagged_log_lines = [item["formatted_line"] for item in annotated if item["is_alert"]]

    summary_text = (
        f"⚡ {alert_count} Alert-Triggering Transaction(s) identified totaling ${total_alert_amount:,.2f} "
        f"| {len(transactions) - alert_count} Routine Transaction(s)"
    ) if alert_count > 0 else "✓ All transactions align with normal expected customer activity."

    return {
        "annotated_list": annotated,
        "alert_count": alert_count,
        "total_alert_amount": total_alert_amount,
        "summary_text": summary_text,
        "full_log": "\n".join(full_log_lines) if full_log_lines else "No transaction history available.",
        "flagged_log": "\n".join(flagged_log_lines) if flagged_log_lines else "No high-risk transactions flagged.",
    }


def format_transaction_logs(customer_id: str, alert_only: bool = False) -> str:
    data = get_annotated_transactions(customer_id)
    return data["flagged_log"] if alert_only else data["full_log"]


def get_kyc_profile(customer_id: str) -> dict:
    kyc_path = KYC_DIR / f"{customer_id}.json"
    if not kyc_path.exists():
        return {}
    with open(kyc_path, encoding="utf-8") as file:
        return json.load(file)


def format_kyc_context(customer_id: str) -> str:
    kyc = get_kyc_profile(customer_id)
    if not kyc:
        return "KYC profile not available."

    customer = get_customer(customer_id)
    risk_score = customer["risk_score"] if customer else 0
    if risk_score >= 70:
        adjudication = "🔴 DRAFT STR (High Risk / Confirmed Typology)"
    elif risk_score >= 35:
        adjudication = "🟡 ESCALATE FOR HUMAN REVIEW (Ambiguous / Elevated Risk)"
    else:
        adjudication = "🟢 CLOSE AS FALSE POSITIVE (Routine / KYC-Aligned)"

    return (
        f"• Subject ID & Name: {customer_id} | {customer.get('name', 'N/A') if customer else 'N/A'}\n"
        f"• Occupation / Stated Business: {kyc.get('occupation', 'Unknown')}\n"
        f"• Declared Monthly Income: ${kyc.get('declared_monthly_income', 0):,}\n"
        f"• Account Age: {kyc.get('account_age_months', 0)} months\n"
        f"• Account Stated Purpose: {kyc.get('account_purpose', 'N/A')}\n"
        f"• Nationality / Jurisdiction: {kyc.get('nationality', 'N/A')}\n"
        f"• Pre-Adjudication Baseline: {adjudication}"
    )


def format_past_investigations(customer_id: str) -> str:
    kyc = get_kyc_profile(customer_id)
    if not kyc:
        return "No KYC record found."

    investigations = kyc.get("past_investigations", [])
    if not investigations:
        return "No prior AML alerts or regulatory investigations on file for this customer (Clean Historical Precedent)."

    lines = ["Historical AML Case History & Precedents:"]
    for i, inv in enumerate(investigations, start=1):
        lines.append(f"  {i}. {inv}")
    return "\n".join(lines)


def save_kyc_profile(customer_id: str, kyc_data: dict) -> None:
    KYC_DIR.mkdir(parents=True, exist_ok=True)
    kyc_path = KYC_DIR / f"{customer_id}.json"
    with open(kyc_path, "w", encoding="utf-8") as file:
        json.dump(kyc_data, file, indent=2)
