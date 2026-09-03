import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

CHROMA_DB_DIR = str(PROJECT_ROOT / "chroma_db")
MLFLOW_TRACKING_URI = f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}"
MLFLOW_EXPERIMENT = "AML_Agent_Evaluation"
