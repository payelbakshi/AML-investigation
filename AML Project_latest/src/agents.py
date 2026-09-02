from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.config import OPENAI_API_KEY, GEMINI_API_KEY
from src.vector_store import get_retriever


def _create_llm():
    """Initializes LLM backend: uses Gemini (via OpenAI-compatible endpoint) or OpenAI based on available key."""
    if GEMINI_API_KEY:
        primary_llm = ChatOpenAI(
            model="gemini-3.6-flash",
            temperature=0,
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_retries=3,
        )
        fallback_llm = ChatOpenAI(
            model="gemini-3.6-flash-lite",
            temperature=0,
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_retries=3,
        )
        return primary_llm.with_fallbacks([fallback_llm])
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=OPENAI_API_KEY,
        max_retries=3,
    )


llm = _create_llm()


def pattern_detection_agent(transaction_data: str) -> str:
    """Agent 1: Analyzes transaction sequences across accounts to identify suspicious behavioral and structural patterns."""
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a Senior AML Pattern Detection Analyst at a global financial institution. "
            "Examine multi-transaction sequences, cash deposits, velocity windows (e.g. within 24-48 hours), "
            "outbound transfers, and counterparty entities.\n\n"
            "Your output must follow this format:\n"
            "1. SUSPICIOUS PATTERN SUMMARY: (Concise overview of what triggers the AML alert)\n"
            "2. SPECIFIC TRANSACTION EVIDENCE: (Bulleted list of high-risk transactions with amounts, dates, and why they were flagged)\n"
            "3. STRUCTURAL CHARACTERISTICS: (e.g. Structuring near $10k, rapid fund drain, offshore exposure, velocity frequency)\n"
            "4. ROUTINE VS ANOMALOUS RATIO: (Clear separation of routine baseline transactions vs suspicious anomalies)"
        ),
        ("user", "Transaction History Ledger:\n{data}")
    ])
    chain = prompt | llm
    return chain.invoke({"data": transaction_data}).content


def typology_matcher_agent(pattern_summary: str) -> str:
    """Agent 2: Queries vector DB (RAG) to map detected patterns to FATF and FIU-IND regulatory typologies."""
    retriever = get_retriever()
    docs = retriever.invoke(pattern_summary)
    context = "\n\n".join([d.page_content for d in docs])

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a Regulatory Typology & Legal Precedent Matcher specialized in FATF and FIU-IND compliance frameworks.\n"
            "Map the observed transaction patterns strictly against official regulatory typologies: "
            "1) Structuring (Smurfing), 2) Layering & Pass-Throughs, 3) Rapid Movement (Velocity), 4) High-Risk Jurisdiction Exposure, 5) Trade/Income Inconsistency.\n\n"
            "Official Regulatory Guidance from Vector Database:\n{context}\n\n"
            "Your output must include:\n"
            "- PRIMARY MATCHED TYPOLOGY: (Name the exact typology, do not just say 'suspicious')\n"
            "- REGULATORY BASIS: (Citing FATF Recommendation / FIU-IND guidance note)\n"
            "- BEHAVIORAL INDICATORS MATCHED: (Specific alignment between observed evidence and typology criteria)\n"
            "- SECONDARY OR COMPOUND RISKS: (Any secondary typology overlap)"
        ),
        ("user", "Detected Pattern Summary:\n{patterns}")
    ])
    chain = prompt | llm
    return chain.invoke({"context": context, "patterns": pattern_summary}).content


def contextual_risk_scorer_agent(
    kyc_profile: str,
    past_investigations: str,
    pattern_summary: str,
    ocr_data: str = "",
    compliance_query: str = ""
) -> str:
    """Agent 3: Evaluates customer KYC context, past investigation history, document OCR, and targeted compliance inquiries against patterns to produce graded scoring."""
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a Contextual AML Risk Scorer & Compliance Adjudicator.\n"
            "Your role is to synthesize the customer's KYC profile, past investigation history, identity verification notes, observed transaction patterns, and specific compliance questions to determine if the activity is legitimate or illicit.\n\n"
            "You must explicitly address:\n"
            "1. KYC PLAUSIBILITY: Does the declared occupation, monthly income, and account age plausibly explain this transaction volume?\n"
            "2. HISTORICAL PRECEDENT ANALYSIS: Check past investigations. Does a previous clearance precedent apply, or has the pattern evolved (e.g. higher amounts, new offshore counterparties, volume velocity)?\n"
            "3. FALSE-POSITIVE VS TRUE-POSITIVE DISTINGUISHING FACTORS: Provide explicit, objective arguments for why this is or is not a false positive.\n"
            "4. TARGETED COMPLIANCE INQUIRY RESPONSE: If a specific investigator inquiry is provided below (e.g. Layering query, FIU-IND advisory check, or Precedent evolution check), explicitly answer it with granular evidence-backed reasoning.\n"
            "5. QUANTIFIED RISK SCORE & CONFIDENCE: Risk Score (0-100) and Confidence Level (High/Medium/Low).\n"
            "6. GRADED RECOMMENDATION: Provide exactly one of these 3 graded decisions:\n"
            "   - 'DECISION: CLOSE_AS_FALSE_POSITIVE' (Score < 35, routine activity aligned with KYC)\n"
            "   - 'DECISION: ESCALATE_FOR_HUMAN_REVIEW' (Score 35-69, ambiguous discrepancy or new pattern)\n"
            "   - 'DECISION: DRAFT_STR_FOR_REGULATOR' (Score >= 70, confirmed suspicious typologies requiring regulatory filing)"
        ),
        (
            "user",
            "Customer KYC Profile:\n{kyc}\n\n"
            "Past Investigation History:\n{past_inv}\n\n"
            "Identity Document / OCR Status:\n{ocr}\n\n"
            "Targeted Compliance Inquiry / Focus Question:\n{query}\n\n"
            "Detected Patterns & Evidence:\n{patterns}"
        )
    ])
    chain = prompt | llm
    return chain.invoke({
        "kyc": kyc_profile,
        "past_inv": past_investigations or "No prior investigations on file.",
        "ocr": ocr_data or "Standard digital KYC verification verified.",
        "query": compliance_query or "Standard comprehensive AML risk, typology correlation, and historical precedent evaluation.",
        "patterns": pattern_summary,
    }).content


def report_generator_agent(
    risk_analysis: str,
    patterns: str,
    typologies: str,
    customer_id: str = "",
    customer_name: str = ""
) -> str:
    """Agent 4: Drafts a structured, regulator-ready Suspicious Transaction Report (STR)."""
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert Regulatory Compliance Officer drafting an official, regulator-ready Suspicious Transaction Report (STR) "
            "for submission to FIU-IND / FinCEN / FATF-aligned authorities.\n\n"
            "Structure the report with the following mandatory sections:\n"
            "================================================================================\n"
            "SUSPICIOUS TRANSACTION REPORT (STR)\n"
            "================================================================================\n"
            "1. REPORT METADATA\n"
            "   - Subject ID: {cust_id} | Subject Name: {cust_name}\n"
            "   - Filing Classification: High Priority Suspicious Activity Filing\n"
            "   - Core Typology: Extracted from Typology Match\n\n"
            "2. EXECUTIVE SUMMARY\n"
            "   - Concise 2-3 sentence overview of why this report is filed and core alert triggers.\n\n"
            "3. SUBJECT & KYC CONTEXT\n"
            "   - Analysis of customer occupation, declared income vs actual volume discrepancy.\n\n"
            "4. CHRONOLOGY OF SUSPICIOUS TRANSACTIONS\n"
            "   - Tabular or chronological breakdown of specific flagged transactions.\n\n"
            "5. TYPOLOGY & REGULATORY GUIDELINES ANALYSIS\n"
            "   - Explicit mapping to FATF / FIU-IND guidelines.\n\n"
            "6. FALSE-POSITIVE VS TRUE-POSITIVE EVALUATION\n"
            "   - Technical justification for why this case cannot be closed as a false positive.\n\n"
            "7. COMPLIANCE OFFICER CONCLUSION & RECOMMENDED ACTIONS\n"
            "   - Final adjudication, recommended account freeze/monitoring, and law enforcement escalation."
        ),
        (
            "user",
            "Customer ID: {cust_id}\n"
            "Customer Name: {cust_name}\n\n"
            "Risk Analysis & Graded Decision:\n{risk}\n\n"
            "Pattern Detection Evidence:\n{patterns}\n\n"
            "Typology Match:\n{typology}"
        )
    ])
    chain = prompt | llm
    return chain.invoke({
        "cust_id": customer_id or "N/A",
        "cust_name": customer_name or "N/A",
        "risk": risk_analysis,
        "patterns": patterns,
        "typology": typologies
    }).content