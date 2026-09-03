from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from src.config import CHROMA_DB_DIR

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

# Uses a free, lightweight model that runs locally on your CPU
def get_embedding_function():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def initialize_vector_store():
    """Sets up Chroma vector database with mock and real-world FIU-IND/FATF regulatory guidelines."""
    embeddings = get_embedding_function()

    docs = [
        Document(
            page_content=(
                "Typology 1: Structuring (Smurfing). Breaking down large cash deposits or wire transfers into multiple smaller transactions "
                "beneath statutory threshold limits ($10,000 USD / INR 10 Lakhs) within a short timeframe (e.g. 24-72 hours) to avoid CTR/STR reporting triggers. "
                "Key indicators include repeated round amounts between $9,000-$9,999 across multiple branches or digital channels."
            ),
            metadata={"typology": "Structuring", "source": "FATF Recommendation 20 & FIU-IND Guidance Note"}
        ),
        Document(
            page_content=(
                "Typology 2: Layering & Complex Pass-Through. Moving illicit funds rapidly across multiple international, inter-bank, or shell company accounts "
                "to obfuscate audit trails and decouple illicit proceeds from source. "
                "Indicators include multiple unrelated inbound credits consolidated and swiftly transferred out as a single lump-sum offshore wire."
            ),
            metadata={"typology": "Layering", "source": "FIU-IND Advisory on Pass-Through Accounts"}
        ),
        Document(
            page_content=(
                "Typology 3: Rapid Movement (Velocity). Immediate withdrawal, transfer, or liquidation of funds within 24 to 48 hours following sudden "
                "high-value deposits into an otherwise dormant or low-activity personal account. Low retention ratio (<10% residual balance)."
            ),
            metadata={"typology": "Rapid Movement", "source": "FIU-IND Red Flag Indicators"}
        ),
        Document(
            page_content=(
                "Typology 4: High-Risk Jurisdiction & Offshore Exposure. Outbound transfers or receipts involving counterparties in offshore financial centers, "
                "tax havens, or FATF Grey/Black-list jurisdictions without verified underlying commercial contracts or economic rationale."
            ),
            metadata={"typology": "High-Risk Jurisdiction Exposure", "source": "FATF High-Risk & Other Monitored Jurisdictions"}
        ),
        Document(
            page_content=(
                "Typology 5: Trade-Based Discrepancy & Inconsistent Business Inflows. Inflows significantly exceeding customer's declared occupation, "
                "income bracket, or stated business model (e.g. student or junior employee receiving commercial vendor remittances). Discrepancy between KYC profile and transaction velocity."
            ),
            metadata={"typology": "Income & KYC Inconsistency", "source": "FIU-IND KYC Compliance Guidelines"}
        )
    ]

    vector_db = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR
    )
    return vector_db

def get_retriever():
    embeddings = get_embedding_function()
    vector_db = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)
    return vector_db.as_retriever(search_kwargs={"k": 3})