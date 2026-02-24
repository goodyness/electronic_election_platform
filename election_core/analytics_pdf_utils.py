from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from django.utils import timezone
import io

def generate_election_audit_pdf(election, voters, total_votes_cast):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Election Audit Report: {election.title}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"Institution: {election.institution.name}", styles['Normal']))
    elements.append(Paragraph(f"Organizer: {election.organizer.user.get_full_name()}", styles['Normal']))
    elements.append(Paragraph(f"Status: {election.status}", styles['Normal']))
    elements.append(Paragraph(f"Plan: {election.get_plan_display()}", styles['Normal']))
    elements.append(Paragraph(f"Total Eligible Voters: {voters.count()}", styles['Normal']))
    elements.append(Paragraph(f"Total Votes Cast: {total_votes_cast}", styles['Normal']))
    elements.append(Paragraph(f"Report Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("Voter Audit Trail (Full Records)", styles['Heading2']))
    elements.append(Spacer(1, 12))

    data = [['Voter Name', 'ID/Matric', 'Accredited', 'Voted Status']]
    for voter in voters:
        data.append([
            voter.user.get_full_name(),
            voter.matric_number,
            "YES" if voter.is_accredited else "NO",
            "VOTED" if voter.has_voted else "PENDING"
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("--- End of Audit Report (Official Secure Balloting System) ---", styles['Italic']))

    doc.build(elements)
    buffer.seek(0)
    return buffer
