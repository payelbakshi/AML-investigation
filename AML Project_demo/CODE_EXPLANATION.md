# AML Investigation Assistant — Detailed Code Explanation
### GenAI Capstone · BFSI Track · Problem Statement 03

---

## Project Overview

The project is a **multi-agent AML (Anti-Money Laundering) investigation system** built with:
- **Gradio** for the web interface
- **LangChain** for multi-agent orchestration
- **ChromaDB** for vector storage (RAG)
- **SQLite** for customer/transaction data
- **Google Gemini** (via OpenAI-compatible endpoint) as the LLM
- **MLflow** for experiment tracking and audit logging
- **ReportLab** for PDF report generation

---

## File-by-File Explanation

---

### `src/config.py` — Configuration & API Key Management

```python
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_KEY_HERE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if OPENAI_API_KEY.startswith("AIzaSy") and not GEMINI_API_KEY:
    GEMINI_API_KEY = OPENAI_API_KEY
    OPENAI_API_KEY = ""

CHROMA_DB_DIR = str(PROJECT_ROOT / "chroma_db")
MLFLOW_TRACKING_URI = f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}"
MLFLOW_EXPERIMENT = "AML_Agent_Evaluation"
```

**What it does:**
- Sets `PROJECT_ROOT` dynamically so all file paths work regardless of where the project is cloned.
- Loads the LLM API key — supports both **Gemini** (`AIzaSy...`) and **OpenAI** (`sk-...`), with auto-detection.
- Defines paths for ChromaDB (vector store), MLflow SQLite database, and the experiment name.

---

### `src/database.py` — SQLite Data Layer

**Tables:**
- `users` — stores login credentials (hashed passwords with SHA-256)
- `customers` — customer ID, name, branch, risk score, remarks, last score update
- `transactions` — transaction records per customer (datetime, amount, type, counterparty)

**Key Functions:**

| Function | Purpose |
|---|---|
| `init_db()` | Creates all tables; seeds the database via `seed_data.py` |
| `validate_user()` | Checks login credentials using `secrets.compare_digest()` for timing-safe comparison |
| `get_customers()` | Returns all customers sorted by risk score descending |
| `get_transactions()` | Returns all transactions for a customer (sorted newest first) |
| `get_annotated_transactions()` | **Core function** — annotates each transaction with AML alert flags |
| `format_kyc_context()` | Formats KYC JSON into a readable string for Agent 3 |
| `format_past_investigations()` | Formats past investigation history from KYC JSON for Agent 3 |

**AML Alert Logic in `get_annotated_transactions()`:**
```python
if "cash deposit" in txn_type and 9000 <= amount <= 9999:
    flags.append("STRUCTURING (Near $10k reporting limit)")

if "swift" in txn_type or "offshore" in counterparty:
    flags.append("OFFSHORE / SWIFT EXPOSURE")

if amount >= (monthly_income * 2):
    flags.append("DISPROPORTIONATE INFLOW (Exceeds monthly income)")
```
Each transaction is tagged as either `🚨 [AML ALERT: ...]` or `🟢 [ROUTINE ACTIVITY]`.

---

### `src/risk_engine.py` — Automated Risk Scoring

This module calculates a **0-100 risk score** for each customer based on their transaction history and KYC profile. It runs automatically when the dashboard loads and when the user clicks "Recalculate".

**Scoring Signals:**

| Signal | Points Added | Logic |
|---|---|---|
| Income mismatch | +25 | Total inflow > 3× declared monthly income |
| Structuring | +30 | ≥2 cash deposits between $9,000–$9,999 |
| Cash frequency | +12 | ≥3 cash deposits in history |
| Offshore exposure | +18 | Any SWIFT/offshore/international counterparty |
| Rapid fund movement | +15 | Outflows ≥ 80% of inflows |
| High velocity | +20 | ≥4 transactions within 48 hours |
| Prior investigations | +10 | Past AML flags in KYC profile |
| New account + large inflow | +12 | Account ≤3 months old + inflow >$15,000 |

The score is clamped to [0, 100] and stored in the database with a timestamp.

---

### `src/vector_store.py` — ChromaDB RAG Vector Store

```python
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

def get_embedding_function():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
```

**What it does:**
- Uses **HuggingFace `all-MiniLM-L6-v2`** model for local, free sentence embeddings.
- Initializes a **ChromaDB vector store** seeded with 5 regulatory documents covering:
  1. **Structuring (Smurfing)** — FATF Recommendation 20
  2. **Layering & Pass-Throughs** — FIU-IND Advisory on Pass-Through Accounts
  3. **Rapid Movement (Velocity)** — FIU-IND Red Flag Indicators
  4. **High-Risk Jurisdiction Exposure** — FATF High-Risk Jurisdictions list
  5. **Trade/Income Inconsistency** — FIU-IND KYC Compliance Guidelines

**How RAG works:**
1. Agent 1 produces a pattern summary text.
2. Agent 2 calls `get_retriever()` — this is a ChromaDB similarity search retriever.
3. The retriever finds the 2 most semantically similar regulatory documents.
4. These documents are injected into Agent 2's prompt as `{context}`.

---

### `src/agents.py` — 4 Specialized LangChain Agents

**LLM Setup:**
```python
def _create_llm():
    if GEMINI_API_KEY:
        primary = ChatOpenAI(
            model="gemini-3.6-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=GEMINI_API_KEY
        )
        fallback = ChatOpenAI(model="gemini-3.6-flash-lite", ...)
        return primary.with_fallbacks([fallback])
    return ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
```
Uses Google Gemini via the **OpenAI-compatible endpoint** — no separate SDK needed. Falls back to `gemini-3.6-flash-lite` automatically if the primary model is overloaded.

---

#### Agent 1: `pattern_detection_agent(transaction_data)`
- **Role**: Senior AML Pattern Detection Analyst
- **Input**: Raw transaction history text
- **Output Format**:
  1. SUSPICIOUS PATTERN SUMMARY
  2. SPECIFIC TRANSACTION EVIDENCE (bulleted list)
  3. STRUCTURAL CHARACTERISTICS (e.g., "near $10k structuring")
  4. ROUTINE VS ANOMALOUS RATIO

---

#### Agent 2: `typology_matcher_agent(pattern_summary)`
- **Role**: Regulatory Typology & Legal Precedent Matcher
- **Input**: Agent 1's output + ChromaDB regulatory documents (RAG)
- **Output Format**:
  - PRIMARY MATCHED TYPOLOGY (exact name from FATF/FIU-IND)
  - REGULATORY BASIS (FATF Recommendation / FIU-IND guidance note citation)
  - BEHAVIORAL INDICATORS MATCHED
  - SECONDARY OR COMPOUND RISKS

---

#### Agent 3: `contextual_risk_scorer_agent(kyc, past_inv, patterns, ocr)`
- **Role**: Contextual AML Risk Scorer & Compliance Adjudicator
- **Input**: KYC profile, past investigations, Agent 1 patterns, optional OCR text
- **Output Format**:
  1. KYC PLAUSIBILITY (income vs transaction volume)
  2. HISTORICAL PRECEDENT ANALYSIS (does prior clearance still apply?)
  3. FALSE-POSITIVE VS TRUE-POSITIVE DISTINGUISHING FACTORS (this is the core business requirement)
  4. QUANTIFIED RISK SCORE & CONFIDENCE (0-100 + High/Medium/Low)
  5. GRADED RECOMMENDATION (exactly one of 3 decisions)

---

#### Agent 4: `report_generator_agent(risk, patterns, typologies, cust_id, cust_name)`
- **Role**: Expert Regulatory Compliance Officer
- **Input**: All previous agent outputs
- **Output**: A 7-section STR (Suspicious Transaction Report):
  1. REPORT METADATA
  2. EXECUTIVE SUMMARY
  3. SUBJECT & KYC CONTEXT
  4. CHRONOLOGY OF SUSPICIOUS TRANSACTIONS
  5. TYPOLOGY & REGULATORY GUIDELINES ANALYSIS
  6. FALSE-POSITIVE VS TRUE-POSITIVE EVALUATION
  7. COMPLIANCE OFFICER CONCLUSION & RECOMMENDED ACTIONS

---

### `src/orchestration.py` — Pipeline Coordinator

```python
with mlflow.start_run(run_name=f"AML_Investigation_{customer_id}"):
    patterns = pattern_detection_agent(transaction_data)
    typologies = typology_matcher_agent(patterns)
    risk_analysis = contextual_risk_scorer_agent(kyc, past_inv, patterns, ocr)
    
    # 3-Tier decision logic
    if "DRAFT_STR" in risk_upper or score >= 70:
        decision = "DRAFT REGULATOR-READY STR"
    elif "ESCALATE" in risk_upper or score >= 35:
        decision = "ESCALATE FOR HUMAN REVIEW"
    else:
        decision = "CLOSE AS FALSE POSITIVE"
    
    # Conditionally invoke Agent 4 + PDF generation
    if needs_str:
        str_report = report_generator_agent(...)
        pdf_path = generate_str_pdf(...)
    
    # Log everything to MLflow
    mlflow.log_param("decision", decision)
    mlflow.log_text(patterns, "outputs/patterns.txt")
    ...
```

**What it does:**
1. Chains all 4 agents in sequence
2. Extracts the graded decision from Agent 3's text using keyword matching
3. Only calls Agent 4 (expensive STR generation) when the case warrants it — not for false positives
4. Generates a PDF if the STR is drafted
5. Logs every parameter and text artifact to MLflow for RAGAS evaluation

---

### `src/pdf_generator.py` — PDF STR Export

Uses **ReportLab** to generate a professionally formatted PDF:
- Header: "FINANCIAL INTELLIGENCE COMPLIANCE DIVISION"
- Metadata table: customer ID, name, decision, regulatory framework
- Body: parses the STR text line-by-line, applying section headings and body styles
- Footer: legal notice and confidentiality disclaimer

Saved to `data/reports/STR_{customer_id}_{timestamp}.pdf`

---

### `src/seed_data.py` — Synthetic Test Data

Generates 25 synthetic customers with:
- Mixed risk profiles (some with structuring patterns, some clean)
- Realistic transaction histories using varied amounts, types, and counterparties
- KYC JSON files stored in `data/kyc/{customer_id}.json`
- Fields: occupation, declared_monthly_income, account_age_months, account_purpose, nationality, past_investigations

---

### `app.py` — Gradio Web Application

**Structure:**
1. **CSS Styling** (~1000 lines) — custom theme with Pakistan green + Royal purple color scheme, glassmorphism login card, investigation panels
2. **Helper functions** — navigation HTML builder, customer table formatter, page chip formatter
3. **Page layout** (Gradio Blocks):
   - `login_page`: Login card with username + password
   - `customers_page`: Customer monitoring dashboard with paginated table, remarks editor, risk score recalculation
   - `investigation_page`: Two-panel investigation workspace (inputs left, outputs right)
4. **Event wiring**: All Gradio click/submit events connected to backend functions

**Session Management:**
Uses `gr.BrowserState` with a JSON payload (`aml_session_state_v2`) to persist:
- Logged-in username
- Current page (login / customers / investigation)
- Selected customer ID

This ensures the user's session survives page refreshes.

**Investigation Workspace Panels:**
- Left panel: Risk score, risk update time, transaction view filter (Flagged Only vs Full Ledger), transaction log, KYC profile, past investigations, optional ID upload, run pipeline button
- Right panel: 3-tier decision output, PDF download button, Agent 1-4 accordion outputs

---

## Data Flow Summary

```
User Login
  → validate_user() (SHA-256 hash comparison)
  → Redirect to Customer Monitoring Dashboard

Dashboard Load
  → refresh_all_risk_scores() → calculate_risk_score() per customer
  → get_paginated_table() → render sorted customer table

Click Investigate
  → get_annotated_transactions() → AML-flagged transaction log
  → format_kyc_context() → KYC string
  → format_past_investigations() → history string
  → Load all into investigation workspace

Click Run Pipeline
  → run_aml_pipeline()
    → Agent 1 (Pattern Detection)
    → Agent 2 (Typology Matcher + ChromaDB RAG)
    → Agent 3 (Risk Scorer)
    → 3-Tier Decision
    → Agent 4 (STR Generator) [if needed]
    → generate_str_pdf() [if needed]
    → mlflow.log_*() [always]
  → Return all outputs to Gradio UI
  → Show PDF download button if STR was generated
```
