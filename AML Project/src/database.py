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


def format_transaction_logs(customer_id: str) -> str:
    transactions = get_transactions(customer_id)
    if not transactions:
        return "No transaction history available."

    lines = []
    for txn in reversed(transactions):
        amount = txn["amount"]
        sign = "-" if amount < 0 else "+"
        lines.append(
            f"{txn['txn_datetime']}: {sign}${abs(amount):,.2f} {txn['txn_type']} "
            f"— {txn['description']} ({txn['counterparty'] or 'N/A'})"
        )
    return "\n".join(lines)


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

    investigations = kyc.get("past_investigations", [])
    investigation_text = (
        "; ".join(investigations) if investigations else "No prior investigations on record."
    )

    return (
        f"Customer: {kyc.get('occupation', 'Unknown')} | "
        f"Declared Monthly Income: ${kyc.get('declared_monthly_income', 0):,} | "
        f"Account Age: {kyc.get('account_age_months', 0)} months | "
        f"Purpose: {kyc.get('account_purpose', 'N/A')} | "
        f"Nationality: {kyc.get('nationality', 'N/A')}\n"
        f"Past Investigations: {investigation_text}"
    )


def save_kyc_profile(customer_id: str, kyc_data: dict) -> None:
    KYC_DIR.mkdir(parents=True, exist_ok=True)
    kyc_path = KYC_DIR / f"{customer_id}.json"
    with open(kyc_path, "w", encoding="utf-8") as file:
        json.dump(kyc_data, file, indent=2)
