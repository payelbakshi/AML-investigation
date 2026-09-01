from src.database import (
    MAX_CUSTOMERS,
    get_connection,
    save_kyc_profile,
)

CUSTOMER_SEED = [
    {
        "customer_id": "CUS-1001",
        "name": "Priya Sharma",
        "branch": "Downtown Branch",
        "remarks": "High volume wire transfers flagged",
        "kyc": {
            "occupation": "Freelance Consultant",
            "declared_monthly_income": 4500,
            "account_age_months": 14,
            "account_purpose": "Business Operations",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-01 09:15", "Incoming wire from client A", 12500, "Wire Transfer", "Client A"),
            ("2026-03-01 14:40", "Outgoing transfer to vendor", -9800, "Wire Transfer", "Vendor X"),
            ("2026-03-02 11:05", "International remittance", -6200, "SWIFT", "Offshore Entity"),
        ],
    },
    {
        "customer_id": "CUS-1002",
        "name": "Rahul Mehta",
        "branch": "North City Branch",
        "remarks": "Pending KYC document update",
        "kyc": {
            "occupation": "Retail Manager",
            "declared_monthly_income": 3200,
            "account_age_months": 28,
            "account_purpose": "Salary & Savings",
            "nationality": "IN",
            "past_investigations": ["Cleared similar alert - March 2025"],
        },
        "transactions": [
            ("2026-03-03 10:00", "Salary credit", 3100, "Credit", "Employer"),
            ("2026-03-05 18:20", "Utility payment", -420, "Debit", "Utility Co"),
            ("2026-03-08 12:10", "Grocery purchase", -180, "POS", "Supermarket"),
        ],
    },
    {
        "customer_id": "CUS-1003",
        "name": "Neha Nair",
        "branch": "Coastal Branch",
        "remarks": "Low risk - standard account activity",
        "kyc": {
            "occupation": "Teacher",
            "declared_monthly_income": 2800,
            "account_age_months": 36,
            "account_purpose": "Personal Savings",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-02 08:30", "Salary credit", 2750, "Credit", "School Board"),
            ("2026-03-10 16:45", "Rent payment", -900, "Debit", "Landlord"),
        ],
    },
    {
        "customer_id": "CUS-1004",
        "name": "Amit Verma",
        "branch": "Downtown Branch",
        "remarks": "Under active investigation for structuring",
        "kyc": {
            "occupation": "Student",
            "declared_monthly_income": 1200,
            "account_age_months": 2,
            "account_purpose": "Education Expenses",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-01 10:05", "Cash deposit branch counter", 9500, "Cash Deposit", "Self"),
            ("2026-03-01 15:20", "Cash deposit branch counter", 9800, "Cash Deposit", "Self"),
            ("2026-03-02 09:40", "Cash deposit branch counter", 9400, "Cash Deposit", "Self"),
            ("2026-03-02 17:55", "Outgoing transfer offshore", -19000, "SWIFT", "Offshore Entity"),
        ],
    },
    {
        "customer_id": "CUS-1005",
        "name": "Sonia Kapoor",
        "branch": "West End Branch",
        "remarks": "Large cash deposit pattern",
        "kyc": {
            "occupation": "Jewelry Store Owner",
            "declared_monthly_income": 6000,
            "account_age_months": 18,
            "account_purpose": "Business Cash Management",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-04 11:00", "Cash deposit from sales", 8200, "Cash Deposit", "Store Counter"),
            ("2026-03-06 11:30", "Cash deposit from sales", 7900, "Cash Deposit", "Store Counter"),
            ("2026-03-07 12:00", "Supplier payment", -11000, "Debit", "Wholesaler"),
        ],
    },
    {
        "customer_id": "CUS-1006",
        "name": "Vikram Singh",
        "branch": "North City Branch",
        "remarks": "Multiple international remittances",
        "kyc": {
            "occupation": "Import/Export Trader",
            "declared_monthly_income": 9000,
            "account_age_months": 42,
            "account_purpose": "Trade Settlement",
            "nationality": "IN",
            "past_investigations": ["Reviewed Q4 2025 - no STR filed"],
        },
        "transactions": [
            ("2026-03-01 13:00", "International incoming payment", 22000, "SWIFT", "Dubai Trading LLC"),
            ("2026-03-02 09:15", "International outgoing payment", -18000, "SWIFT", "Singapore Supplier"),
            ("2026-03-03 16:30", "International incoming payment", 15000, "SWIFT", "Hong Kong Buyer"),
        ],
    },
    {
        "customer_id": "CUS-1007",
        "name": "Meera Iyer",
        "branch": "Central Branch",
        "remarks": "Routine activity; no alert",
        "kyc": {
            "occupation": "Software Engineer",
            "declared_monthly_income": 5200,
            "account_age_months": 24,
            "account_purpose": "Salary & Investments",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-05 09:00", "Salary credit", 5100, "Credit", "Tech Corp"),
            ("2026-03-12 20:10", "Mutual fund SIP", -500, "Debit", "AMC"),
        ],
    },
    {
        "customer_id": "CUS-1008",
        "name": "Aditya Rao",
        "branch": "Downtown Branch",
        "remarks": "Rapid inward-outward transfers",
        "kyc": {
            "occupation": "Real Estate Agent",
            "declared_monthly_income": 7000,
            "account_age_months": 9,
            "account_purpose": "Commission Handling",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-01 08:00", "Commission credit", 18000, "Credit", "Property Buyer"),
            ("2026-03-01 10:30", "Transfer to associate account", -17500, "Wire Transfer", "Associate Firm"),
            ("2026-03-01 19:45", "Cash withdrawal", -1200, "Cash Withdrawal", "ATM"),
        ],
    },
    {
        "customer_id": "CUS-1009",
        "name": "Pooja Nandan",
        "branch": "Coastal Branch",
        "remarks": "Stable transaction behavior",
        "kyc": {
            "occupation": "Nurse",
            "declared_monthly_income": 3500,
            "account_age_months": 30,
            "account_purpose": "Household Expenses",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-06 07:45", "Salary credit", 3450, "Credit", "Hospital"),
            ("2026-03-14 13:20", "EMI debit", -620, "Debit", "Loan Provider"),
        ],
    },
    {
        "customer_id": "CUS-1010",
        "name": "Rohan Das",
        "branch": "West End Branch",
        "remarks": "Account linked to speculative funds",
        "kyc": {
            "occupation": "Day Trader",
            "declared_monthly_income": 4000,
            "account_age_months": 6,
            "account_purpose": "Trading",
            "nationality": "IN",
            "past_investigations": ["Escalated Jan 2026 - under review"],
        },
        "transactions": [
            ("2026-03-01 09:30", "Incoming transfer", 25000, "Wire Transfer", "Unknown Individual 1"),
            ("2026-03-01 11:00", "Incoming transfer", 18000, "Wire Transfer", "Unknown Individual 2"),
            ("2026-03-01 15:00", "Outgoing transfer", -42000, "Wire Transfer", "Crypto Exchange"),
        ],
    },
    {
        "customer_id": "CUS-1011",
        "name": "Kavita Desai",
        "branch": "Central Branch",
        "remarks": "Frequent small incoming transfers",
        "kyc": {
            "occupation": "Student",
            "declared_monthly_income": 1500,
            "account_age_months": 4,
            "account_purpose": "Living Expenses",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-01 12:00", "Peer transfer", 2500, "Credit", "Individual A"),
            ("2026-03-01 14:00", "Peer transfer", 2800, "Credit", "Individual B"),
            ("2026-03-01 16:00", "Peer transfer", 2600, "Credit", "Individual C"),
            ("2026-03-01 18:00", "Peer transfer", 2700, "Credit", "Individual D"),
            ("2026-03-01 20:00", "Peer transfer", 2900, "Credit", "Individual E"),
            ("2026-03-02 09:00", "Large outgoing transfer", -15000, "Wire Transfer", "Shell Company"),
        ],
    },
    {
        "customer_id": "CUS-1012",
        "name": "Arjun Pillai",
        "branch": "Downtown Branch",
        "remarks": "Seasonal business inflows",
        "kyc": {
            "occupation": "Agricultural Trader",
            "declared_monthly_income": 5500,
            "account_age_months": 48,
            "account_purpose": "Crop Sales",
            "nationality": "IN",
            "past_investigations": [],
        },
        "transactions": [
            ("2026-03-10 10:00", "Crop sale proceeds", 14000, "Credit", "Mandi Buyer"),
            ("2026-03-11 11:00", "Equipment lease", -3200, "Debit", "Equipment Co"),
        ],
    },
]


def seed_database() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    existing = cursor.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    for customer in CUSTOMER_SEED[:MAX_CUSTOMERS]:
        cursor.execute(
            """
            INSERT INTO customers (customer_id, name, branch, risk_score, remarks, risk_updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                customer["customer_id"],
                customer["name"],
                customer["branch"],
                0,
                customer["remarks"],
            ),
        )

        kyc_payload = {"customer_id": customer["customer_id"], **customer["kyc"]}
        save_kyc_profile(customer["customer_id"], kyc_payload)

        for txn_datetime, description, amount, txn_type, counterparty in customer["transactions"]:
            cursor.execute(
                """
                INSERT INTO transactions (customer_id, txn_datetime, description, amount, txn_type, counterparty)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    customer["customer_id"],
                    txn_datetime,
                    description,
                    amount,
                    txn_type,
                    counterparty,
                ),
            )

    conn.commit()
    conn.close()

    from src.risk_engine import refresh_all_risk_scores

    refresh_all_risk_scores()
