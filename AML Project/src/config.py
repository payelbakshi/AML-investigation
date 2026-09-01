import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "#")
CHROMA_DB_DIR = str(PROJECT_ROOT / "chroma_db")
MLFLOW_TRACKING_URI = f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}"
MLFLOW_EXPERIMENT = "AML_Agent_Evaluation"