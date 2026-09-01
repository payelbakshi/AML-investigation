from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.config import OPENAI_API_KEY
from src.vector_store import get_retriever

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=OPENAI_API_KEY)

def pattern_detection_agent(transaction_data: str) -> str:
    """Agent 1: Analyzes transaction sequences to identify suspicious structural patterns."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert AML Pattern Detection Analyst. Analyze transaction sequences across accounts and highlight suspicious behavior."),
        ("user", "Transaction History Data:\n{data}")
    ])
    chain = prompt | llm
    return chain.invoke({"data": transaction_data}).content

def typology_matcher_agent(pattern_summary: str) -> str:
    """Agent 2: Queries vector DB (RAG) to map detected patterns to FATF/FIU-IND typologies."""
    retriever = get_retriever()
    docs = retriever.invoke(pattern_summary)
    context = "\n\n".join([d.page_content for d in docs])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Regulatory Typology & Precedent Matcher. Match observed patterns to official regulatory guidelines.\n\nRegulatory Guidance:\n{context}"),
        ("user", "Pattern Summary:\n{patterns}")
    ])
    chain = prompt | llm
    return chain.invoke({"context": context, "patterns": pattern_summary}).content

def contextual_risk_scorer_agent(kyc_profile: str, pattern_summary: str, ocr_data: str = "") -> str:
    """Agent 3: Evaluates customer KYC context against suspicious activity to score risk."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Contextual Risk Scoring Agent. Compare detected pattern severity against customer KYC profile (occupation, expected income) and document OCR notes. Return a score out of 100 with clear true-positive vs false-positive trade-off explanations."),
        ("user", "KYC Profile:\n{kyc}\n\nDocument OCR Extract:\n{ocr}\n\nDetected Patterns:\n{patterns}")
    ])
    chain = prompt | llm
    return chain.invoke({"kyc": kyc_profile, "ocr": ocr_data, "patterns": pattern_summary}).content

def report_generator_agent(risk_analysis: str, patterns: str, typologies: str) -> str:
    """Agent 4: Drafts a formal Suspicious Transaction Report (STR)."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an STR Drafting Agent. Create a structured, regulator-ready Suspicious Transaction Report (STR) incorporating patterns, typologies, and risk evidence."),
        ("user", "Risk Analysis:\n{risk}\n\nPatterns:\n{patterns}\n\nTypology Match:\n{typology}")
    ])
    chain = prompt | llm
    return chain.invoke({"risk": risk_analysis, "patterns": patterns, "typology": typologies}).content