import io
import json
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.evidence.models import EvidenceFinding, EntityType
from app.engine.investigation_orchestrator import ActiveInvestigation

class ReportGenerator:
    """Generates standardized, defensible intelligence dossiers on demand (HTML, PDF, JSON)."""

    def generate_json_report(self, investigation: ActiveInvestigation, findings: List[EvidenceFinding], graph_data: Dict[str, Any]) -> str:
        report_data = {
            "metadata": {
                "platform": "PRAVISION — Universal OSINT Platform",
                "generated_at": datetime.utcnow().isoformat(),
                "investigation_id": investigation.id,
                "classification_mode": investigation.mode,
                "target_input": investigation.root_input,
                "target_type": investigation.root_type.value,
            },
            "summary": {
                "total_findings": len(findings),
                "verified_relationships": investigation.verified_relationships,
                "status": investigation.status
            },
            "findings": [f.dict() for f in findings],
            "graph": graph_data,
            "connector_audit": {k: v.dict() for k, v in investigation.connector_statuses.items()},
            "disclaimer": "This intelligence dossier was synthesized from authorized public sources and mathematical verification. Findings reflect corroborated public metadata."
        }
        return json.dumps(report_data, indent=2, default=str)

    def generate_html_report(self, investigation: ActiveInvestigation, findings: List[EvidenceFinding], graph_data: Dict[str, Any]) -> str:
        findings_rows = ""
        for f in findings:
            badge_color = "#22C55E" if f.confidence.value in ("high", "independently_corroborated") else "#38BDF8" if f.confidence.value == "moderate" else "#F59E0B"
            findings_rows += f"""
            <tr style="border-bottom: 1px solid #26364B;">
                <td style="padding: 10px; color: #38BDF8; font-weight: 600;">{f.entity_type.value.upper()}</td>
                <td style="padding: 10px; color: #F8FAFC; word-break: break-all;">{f.entity_value}</td>
                <td style="padding: 10px; color: #94A3B8;">{f.source_name}</td>
                <td style="padding: 10px; color: {badge_color}; text-transform: uppercase; font-size: 11px; font-weight: bold;">{f.confidence.value}</td>
                <td style="padding: 10px; color: #CBD5E1; font-size: 13px;">{f.evidence_description}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PRAVISION Intelligence Dossier — {investigation.root_input}</title>
    <style>
        body {{ background-color: #080D16; color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 40px; }}
        .header {{ border-bottom: 2px solid #38BDF8; padding-bottom: 20px; margin-bottom: 30px; }}
        .title {{ font-size: 26px; font-weight: 800; color: #38BDF8; margin: 0; }}
        .subtitle {{ font-size: 14px; color: #94A3B8; margin-top: 5px; }}
        .card {{ background: #121D2D; border: 1px solid #26364B; border-radius: 8px; padding: 20px; margin-bottom: 25px; }}
        .metric {{ font-size: 28px; font-weight: 700; color: #38BDF8; }}
        .metric-label {{ font-size: 12px; text-transform: uppercase; color: #94A3B8; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th {{ background: #0E1624; color: #94A3B8; font-size: 12px; text-transform: uppercase; padding: 12px 10px; border-bottom: 2px solid #26364B; }}
        .disclaimer {{ font-size: 11px; color: #64748B; margin-top: 40px; border-top: 1px solid #1E293B; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 class="title">PRAVISION — UNIFIED INTELLIGENCE DOSSIER</h1>
        <div class="subtitle">Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Target: {investigation.root_input} ({investigation.root_type.value})</div>
    </div>

    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px;">
        <div class="card" style="margin: 0;">
            <div class="metric">{len(findings)}</div>
            <div class="metric-label">Corroborated Findings</div>
        </div>
        <div class="card" style="margin: 0;">
            <div class="metric">{investigation.verified_relationships}</div>
            <div class="metric-label">Graph Relationships</div>
        </div>
        <div class="card" style="margin: 0;">
            <div class="metric">{investigation.depth}</div>
            <div class="metric-label">Max Depth</div>
        </div>
        <div class="card" style="margin: 0;">
            <div class="metric">{investigation.status.upper()}</div>
            <div class="metric-label">Investigation Status</div>
        </div>
    </div>

    <div class="card">
        <h3 style="color: #38BDF8; margin-top: 0; font-size: 16px; border-bottom: 1px solid #26364B; padding-bottom: 10px;">Executive Summary</h3>
        <p style="color: #CBD5E1; font-size: 14px; line-height: 1.6;">
            PRAVISION initiated automated multi-vector recursive discovery on target <strong>{investigation.root_input}</strong> 
            under <strong>{investigation.mode}</strong>. A total of {len(findings)} verified evidence items across independent public infrastructure,
            cryptographic records, and public registries were evaluated. Cross-source corroboration identified {investigation.verified_relationships} evidence-backed relationships.
        </p>
    </div>

    <div class="card">
        <h3 style="color: #38BDF8; margin-top: 0; font-size: 16px; border-bottom: 1px solid #26364B; padding-bottom: 10px;">Corroborated Evidence Catalogue</h3>
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Entity Value</th>
                    <th>Source Engine</th>
                    <th>Confidence</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                {findings_rows if findings_rows else "<tr><td colspan='5' style='padding: 20px; text-align: center; color: #94A3B8;'>No evidence records identified.</td></tr>"}
            </tbody>
        </table>
    </div>

    <div class="disclaimer">
        CONFIDENTIAL INTELLIGENCE DOCUMENT — PRAVISION UNIVERSAL OSINT PLATFORM.<br>
        Findings synthesized strictly from authorized open-source intelligence (OSINT), public DNS/TLS infrastructure records, and mathematical calculations.
    </div>
</body>
</html>"""
        return html

    def generate_pdf_report(self, investigation: ActiveInvestigation, findings: List[EvidenceFinding]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Heading1"],
            textColor=colors.HexColor("#0284C7"),
            fontSize=18,
            leading=22,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            name="BodyDark",
            parent=styles["Normal"],
            textColor=colors.HexColor("#334155"),
            fontSize=10,
            leading=14
        )

        elements = []
        elements.append(Paragraph("PRAVISION — Universal OSINT & Intelligence Dossier", title_style))
        elements.append(Paragraph(f"Target: {investigation.root_input} | Mode: {investigation.mode} | Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", body_style))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph(f"Executive Summary: Discovered {len(findings)} verified findings and {investigation.verified_relationships} relationships.", body_style))
        elements.append(Spacer(1, 15))

        # Table data
        table_data = [["Entity Type", "Value", "Source", "Confidence"]]
        for f in findings[:25]: # limit for clean PDF
            table_data.append([
                f.entity_type.value.upper(),
                f.entity_value[:35] + ("..." if len(f.entity_value) > 35 else ""),
                f.source_name,
                f.confidence.value.upper()
            ])

        t = Table(table_data, colWidths=[90, 220, 120, 110])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#F8FAFC")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F1F5F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('FONTSIZE', (0,1), (-1,-1), 8),
        ]))
        elements.append(t)

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

report_generator = ReportGenerator()

