import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Supports both Gemini API Keys (starts with AIzaSy...) and OpenAI API Keys (starts with sk-...)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Ljz-fDLTgIIgBR_pFYFWJNj4G8oWfo4jnoOSKbUWXfmQ") or os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Auto-detect if a Gemini key was placed in OPENAI_API_KEY
if OPENAI_API_KEY.startswith("AIzaSy") and not GEMINI_API_KEY:
    GEMINI_API_KEY = OPENAI_API_KEY
    OPENAI_API_KEY = ""

# Auto-detect if an OpenAI key was placed in GEMINI_API_KEY
if GEMINI_API_KEY.startswith("sk-") and not OPENAI_API_KEY:
    OPENAI_API_KEY = GEMINI_API_KEY
    GEMINI_API_KEY = ""

CHROMA_DB_DIR = str(PROJECT_ROOT / "chroma_db")
MLFLOW_TRACKING_URI = f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}"
MLFLOW_EXPERIMENT = "AML_Agent_Evaluation"
