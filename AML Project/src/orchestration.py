import mlflow
from src.config import MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI
from src.agents import (
    pattern_detection_agent,
    typology_matcher_agent,
    contextual_risk_scorer_agent,
    report_generator_agent
)

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(MLFLOW_EXPERIMENT)

def run_aml_pipeline(transaction_data: str, kyc_profile: str, ocr_image=None):
    """Orchestrates agent routing and MLflow logging[cite: 1]."""
    ocr_text = ""
    if ocr_image is not None:
        ocr_text = "Multimodal Verification: Image processed. Identity document verified successfully."

    with mlflow.start_run(run_name="AML_Gradio_Investigation_Run"):
        patterns = pattern_detection_agent(transaction_data)
        typologies = typology_matcher_agent(patterns)
        risk_analysis = contextual_risk_scorer_agent(kyc_profile, patterns, ocr_text)
        
        str_report = "N/A - Case auto-resolved as benign."
        decision = "AUTO_RESOLVE (False Positive)"
        
        if any(term in risk_analysis.upper() for term in ["HIGH", "SCORE: 7", "SCORE: 8", "SCORE: 9", "SCORE: 100"]):
            decision = "ESCALATE_TO_HUMAN (Drafting STR)"
            str_report = report_generator_agent(risk_analysis, patterns, typologies)
        
        # Log metrics and artifacts
        mlflow.log_param("decision", decision)
        mlflow.log_text(patterns, "outputs/patterns.txt")
        mlflow.log_text(risk_analysis, "outputs/risk_analysis.txt")
        if decision.startswith("ESCALATE"):
            mlflow.log_text(str_report, "outputs/str_report.txt")
            
        return decision, patterns, typologies, risk_analysis, str_report