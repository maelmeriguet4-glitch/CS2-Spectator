import json
import sys

from reportlab.lib.colors import HexColor, red
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer


def create_pdf(json_path, output_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = styles['Title']
    h1_style = styles['Heading1']
    h1_style.backColor = HexColor("#DDEEFF")
    h2_style = styles['Heading2']
    h2_style.textColor = HexColor("#224488")
    body_style = styles['Normal']
    code_style = ParagraphStyle('Code', parent=styles['Code'], backColor=HexColor("#F0F0F0"), borderPadding=4)
    crit_style = ParagraphStyle('Crit', parent=h2_style, textColor=red)

    story = []

    # Title
    story.append(Paragraph(f"Rapport d'Audit de Code : {data.get('projet')}", title_style))
    story.append(Paragraph(f"Date : {data.get('date')}", styles['Normal']))
    story.append(Spacer(1, 20))

    # Executive Summary
    story.append(Paragraph("Résumé Exécutif", h1_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(data['resume']['verdict'], body_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Priorités d'action :", styles['Heading3']))
    for p in data['resume']['priorites']:
        story.append(Paragraph(f"• {p}", body_style))
    story.append(Spacer(1, 20))

    # Scope
    story.append(Paragraph("Périmètre et Méthode", h1_style))
    story.append(Spacer(1, 10))
    perimetre = data['perimetre']
    story.append(Paragraph(perimetre.get('description', ''), body_style))
    story.append(Paragraph(f"<b>Langages :</b> {', '.join(perimetre.get('langages', []))}", body_style))
    story.append(Paragraph(f"<b>Outils utilisés :</b> {', '.join(perimetre.get('outils', []))}", body_style))
    if 'limites' in perimetre:
        story.append(Paragraph(f"<b>Limites :</b> {', '.join(perimetre.get('limites', []))}", body_style))
    story.append(PageBreak())

    # Errors
    story.append(Paragraph("Détail des Erreurs", h1_style))
    story.append(Spacer(1, 10))
    
    for err in data['erreurs']:
        title = f"[{err['id']}] {err['titre']} ({err['gravite'].upper()})"
        if err['gravite'] == 'critique':
            story.append(Paragraph(title, crit_style))
        else:
            story.append(Paragraph(title, h2_style))
            
        story.append(Paragraph(f"<b>Catégorie:</b> {err.get('categorie')} | <b>Fichier:</b> {err.get('fichier')} | <b>Lignes:</b> {err.get('lignes', 'N/A')}", body_style))
        story.append(Spacer(1, 5))
        story.append(Paragraph(f"<b>Description :</b> {err.get('description')}", body_style))
        
        if 'preuve' in err:
            story.append(Spacer(1, 5))
            story.append(Preformatted(str(err.get('preuve')), code_style))
            
        story.append(Spacer(1, 5))
        story.append(Paragraph(f"<b>Correction :</b> {err.get('correction')}", body_style))
        story.append(Paragraph(f"<b>Effort :</b> {err.get('effort')} | <b>Confiance :</b> {err.get('confiance')}", body_style))
        story.append(Spacer(1, 15))

    story.append(PageBreak())

    # Plan de correction
    story.append(Paragraph("Plan de Correction", h1_style))
    story.append(Spacer(1, 10))
    
    for phase in data['plan']:
        story.append(Paragraph(phase['phase'], h2_style))
        story.append(Paragraph(f"<b>Objectif :</b> {phase['objectif']}", body_style))
        story.append(Paragraph(f"<b>Erreurs à traiter :</b> {', '.join(phase['erreurs'])}", body_style))
        if 'notes' in phase:
            story.append(Paragraph(f"<b>Notes :</b> {phase['notes']}", body_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    print(f"Rapport généré dans {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_report.py <json> <pdf>")
        sys.exit(1)
    create_pdf(sys.argv[1], sys.argv[2])
