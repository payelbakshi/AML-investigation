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
    """Sets up Chroma vector database with mock FIU-IND/FATF regulatory guidelines."""
    embeddings = get_embedding_function()

    docs = [
        Document(
            page_content="Structuring: Breaking down large transactions into smaller amounts under threshold limits to avoid regulatory reporting.",
            metadata={"typology": "Structuring", "source": "FATF Guidelines"}
        ),
        Document(
            page_content="Layering: Moving funds rapidly across multiple international or inter-bank accounts to obfuscate paper trails.",
            metadata={"typology": "Layering", "source": "FIU-IND Advisory"}
        ),
        Document(
            page_content="Rapid Movement: Immediate withdrawal or transfer of funds following sudden high-value deposits into a low-activity account.",
            metadata={"typology": "Rapid Movement", "source": "FIU-IND Advisory"}
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
    return vector_db.as_retriever(search_kwargs={"k": 2})