"""Esporta in PDF le stesse righe dell'elenco filtrato di SIPA."""
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether


def stampa_pdf(records, ricerca='', filtro='Tutte', destinazione=None):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    target = Path(destinazione).expanduser() if destinazione else Path.home() / 'SIPA_Stampe' / f'attivita_economiche_{stamp}.pdf'
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('cellula', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.5, leading=10)
    bold_cell = ParagraphStyle('nome_attivita', parent=small, fontName='Helvetica-Bold')
    state_colors = {
        'Attiva': '#388E3C',
        'Da iniziare': '#EF6C00',
        'Sospesa': '#FF8F00',
        'Cessata': '#C62828',
    }
    heading = ParagraphStyle('testata', parent=styles['Title'], fontSize=16, leading=20, alignment=TA_CENTER)
    doc = SimpleDocTemplate(str(target), pagesize=landscape(A4), rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=16*mm, bottomMargin=14*mm)
    def cell(value):
        return Paragraph(escape(str(value or '')), small)
    rows = [[cell(v) for v in ('Nome', 'Tipologia', 'Titolare', 'Inizio', 'Sosp. dal', 'Sosp. al', 'Cessazione', 'Stato')]]
    for r in records:
        nome = Paragraph(escape(str(r.get('nome') or '')), bold_cell)
        stato = str(r.get('stato') or '')
        stato_style = ParagraphStyle('stato_' + stato, parent=small,
                                     textColor=colors.HexColor(state_colors.get(stato, '#374151')),
                                     fontName='Helvetica-Bold')
        values = [r.get(k, '') for k in ('tipologia', 'titolare', 'data_inizio',
                    'data_sospensione_inizio', 'data_sospensione_fine', 'data_cessazione')]
        rows.append([nome] + [cell(v) for v in values] + [Paragraph(escape(stato), stato_style)])
    if len(rows) == 1:
        rows.append([cell('Nessuna attività corrispondente ai filtri')] + [''] * 7)
    table = Table(rows, colWidths=[55*mm, 31*mm, 39*mm, 22*mm, 22*mm, 22*mm, 25*mm, 24*mm], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E9EFF5')),
                               ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#CFD8E3')),
                               ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7F9FB')]),
                               ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                               ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    data_stampa = datetime.now().strftime('%d/%m/%Y %H:%M')
    detail = f'Filtro stato: {filtro} | Ricerca (OR): {ricerca or "nessuna"} | Risultati: {len(records)}'
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(landscape(A4)[0]-14*mm, 8*mm, f'Pagina {document.page}')
        canvas.restoreState()
    doc.build([Paragraph('SIPA — Elenco attività economiche', heading), Spacer(1, 4*mm),
               Paragraph('Data di stampa: ' + escape(data_stampa), styles['Normal']), Spacer(1, 2*mm),
               Paragraph(escape(detail), styles['Normal']), Spacer(1, 5*mm), table],
              onFirstPage=footer, onLaterPages=footer)
    return target
