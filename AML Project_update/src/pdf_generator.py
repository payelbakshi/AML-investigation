from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.config import PROJECT_ROOT

REPORTS_DIR = PROJECT_ROOT / "data" / "reports"


def generate_str_pdf(
    customer_id: str,
    customer_name: str,
    decision: str,
    patterns: str,
    typologies: str,
    risk_analysis: str,
    str_report_text: str,
) -> str:
    """Generates a regulator-ready PDF Suspicious Transaction Report using ReportLab."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"STR_{customer_id}_{timestamp_str}.pdf"
    pdf_path = REPORTS_DIR / filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#143109"),
        alignment=1,  # Center
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#7E3F8F"),
        alignment=1,  # Center
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#143109"),
    )

    meta_val_style = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#222222"),
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#143109"),
        spaceBefore=10,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#2b2b2b"),
        spaceAfter=4,
    )

    story = []

    # Header
    story.append(Paragraph("FINANCIAL INTELLIGENCE COMPLIANCE DIVISION", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("SUSPICIOUS TRANSACTION REPORT (STR)", title_style))
    story.append(Paragraph("CONFIDENTIAL · REGULATORY SUBMISSION DRAFT", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#143109"), spaceAfter=10))

    # Metadata Table
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta_data = [
        [
            Paragraph("<b>Subject Customer ID:</b>", meta_label_style),
            Paragraph(customer_id, meta_val_style),
            Paragraph("<b>Report Generated:</b>", meta_label_style),
            Paragraph(now_utc, meta_val_style),
        ],
        [
            Paragraph("<b>Subject Name:</b>", meta_label_style),
            Paragraph(customer_name, meta_val_style),
            Paragraph("<b>Adjudication:</b>", meta_label_style),
            Paragraph(decision, meta_val_style),
        ],
        [
            Paragraph("<b>Regulatory Framework:</b>", meta_label_style),
            Paragraph("FIU-IND / FATF PMLA Guidelines", meta_val_style),
            Paragraph("<b>Filing Priority:</b>", meta_label_style),
            Paragraph("High Priority Escalate", meta_val_style),
        ],
    ]

    t = Table(meta_data, colWidths=[1.6 * inch, 2.0 * inch, 1.5 * inch, 2.2 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F3ED")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#AAAE7F")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0DDD5")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 10))

    # Formatted Sections from str_report_text or risk_analysis
    raw_text = str_report_text if str_report_text and "N/A" not in str_report_text else f"SYSTEM ADJUDICATION SUMMARY:\n{decision}\n\nRISK ANALYSIS:\n{risk_analysis}\n\nTYPOLOGIES:\n{typologies}\n\nPATTERNS:\n{patterns}"

    # Split into lines and format
    lines = raw_text.split("\n")
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            story.append(Spacer(1, 3))
            continue
        if line_strip.startswith("===") or line_strip.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#7E3F8F"), spaceBefore=4, spaceAfter=4))
            continue
        if any(line_strip.startswith(f"{i}.") for i in range(1, 15)) or (line_strip.isupper() and len(line_strip) < 60):
            story.append(Paragraph(line_strip, section_heading))
        else:
            safe_text = line_strip.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_text, body_style))

    # Footer Disclaimer
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#AAAAAA"), spaceBefore=6, spaceAfter=6))
    footer_text = (
        "<b>LEGAL & REGULATORY NOTICE:</b> This Suspicious Transaction Report contains confidential compliance analysis. "
        "Unauthorized dissemination is strictly prohibited under applicable Anti-Money Laundering legislation."
    )
    story.append(Paragraph(footer_text, ParagraphStyle("Footer", parent=styles["Normal"], fontSize=6.5, leading=8, textColor=colors.HexColor("#666666"))))

    doc.build(story)
    return str(pdf_path)
