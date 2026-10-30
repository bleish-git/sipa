"""PDF elenchi, prospetti annuali e schede assenze mercatino."""
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Flowable, KeepTogether

PALETTE = {'Attivo': '#388E3C', 'Sospeso': '#FF8F00', 'Cessato': '#C62828'}


def _pdf(rows, headers, title, detail, prefix, widths=None, landscape_page=True):
    page = landscape(A4) if landscape_page else A4
    target = Path.home() / 'SIPA_Stampe' / f'{prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}.pdf'
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    regular = ParagraphStyle('merc_cell', parent=styles['BodyText'], fontSize=7, leading=9)
    bold = ParagraphStyle('merc_bold', parent=regular, fontName='Helvetica-Bold')
    def cell(v, bolded=False, colored=None):
        style = ParagraphStyle('colored_'+str(colored), parent=bold, textColor=colors.HexColor(colored)) if colored else (bold if bolded else regular)
        return Paragraph(escape(str(v or '')), style)
    result = [[cell(x, True) for x in headers]]
    result.extend(rows)
    if len(result) == 1:
        result.append([cell('Nessuna registrazione')] + ['']*(len(headers)-1))
    usable = page[0] - 28*mm
    table = Table(result, colWidths=widths or [usable/len(headers)]*len(headers), repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#E9EFF5')),
        ('GRID',(0,0),(-1,-1),.25,colors.HexColor('#CBD5E1')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F8FAFC')]),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]))
    doc = SimpleDocTemplate(str(target), pagesize=page, leftMargin=14*mm, rightMargin=14*mm, topMargin=15*mm, bottomMargin=13*mm)
    def footer(canvas, document):
        canvas.saveState(); canvas.setFont('Helvetica', 8)
        canvas.drawRightString(page[0]-14*mm, 7*mm, f'Pagina {document.page}')
        canvas.restoreState()
    doc.build([Paragraph(escape(title), styles['Title']), Spacer(1,3*mm),
               Paragraph('Stampato il '+datetime.now().strftime('%d/%m/%Y %H:%M'),styles['Normal']),
               Paragraph(escape(detail), styles['Normal']),Spacer(1,5*mm),table],
              onFirstPage=footer,onLaterPages=footer)
    return target


def stampa_elenco(records, ricerca, luoghi, stato):
    s=getSampleStyleSheet()
    bold=ParagraphStyle('r_nome', parent=s['BodyText'], fontName='Helvetica-Bold', fontSize=8)
    small=ParagraphStyle('r_cella', parent=s['BodyText'], fontSize=8)
    def para(v, st=small):return Paragraph(escape(str(v or '')),st)
    rows=[]
    for d in records:
        color = colors.HexColor(PALETTE.get(d['stato'],'#334155'))
        st=ParagraphStyle('r_status_'+d['stato'], parent=bold,textColor=color)
        rows.append([para(d['denominazione'],bold),para(d['numero_posto']),para(d['luogo']),para(d['stato'],st)])
    return _pdf(rows,['Denominazione','Posto','Luogo mercatino','Stato'],'SIPA — Elenco mercatino',
                f'Ricerca: {ricerca or "nessuna"} | Luoghi: {", ".join(sorted(luoghi)) if luoghi is not None else "tutti"} | Stato: {stato} | Risultati: {len(records)}',
                'mercatino_elenco', [110*mm,30*mm,77*mm,52*mm])


class _VerticalDate(Flowable):
    """Intestazione ruotata a 90° per tabelle annuali molto larghe."""
    def __init__(self, label, height=34, width=10, font_size=4):
        super().__init__()
        self.label = label
        self.width = width
        self.height = height
        self.font_size = font_size

    def draw(self):
        self.canv.saveState()
        self.canv.translate(self.width / 2 + self.font_size * .35, 2)
        self.canv.rotate(90)
        self.canv.setFont('Helvetica-Bold', self.font_size)
        self.canv.drawString(0, 0, self.label)
        self.canv.restoreState()


def stampa_assenze(ditte, date_colonne, assenti, anno, singola=False):
    """Certificazione individuale oppure matrice annuale delle ditte attive."""
    now = datetime.now()
    target = Path.home() / 'SIPA_Stampe' / f'mercatino_assenze_{anno}_{now:%Y%m%d_%H%M%S_%f}.pdf'
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    bold = ParagraphStyle('cert_bold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=16)
    normal = ParagraphStyle('cert_text', parent=styles['Normal'], fontSize=11, leading=17)
    tiny = ParagraphStyle('matrix_tiny', parent=styles['Normal'], fontSize=7, leading=9)
    tiny_bold = ParagraphStyle('matrix_bold', parent=tiny, fontName='Helvetica-Bold')

    if singola:
        # Testo in forma di attestazione, non tabella.
        doc = SimpleDocTemplate(str(target), pagesize=A4, leftMargin=24*mm,
                                rightMargin=24*mm, topMargin=21*mm, bottomMargin=18*mm)
        story = [Paragraph('SIPA — PROSPETTO ASSENZE DELLA DITTA', styles['Title']), Spacer(1, 11*mm)]
        d = ditte[0] if ditte else None
        if d:
            for label, value in [('Denominazione', d['denominazione']),
                                 ('Numero posto', d['numero_posto']),
                                 ('Luogo mercatino', d['luogo']),
                                 ('Stato attuale', d['stato']), ('Anno di riferimento', anno)]:
                story.append(Paragraph(f'<b>{escape(label)}: {escape(str(value))}</b>', bold))
            story.extend([Spacer(1, 12*mm), Paragraph('Risultano registrate le seguenti assenze:', normal), Spacer(1, 4*mm)])
            days = sorted(day for day in date_colonne if (d['id'], day) in assenti)
            if days:
                for idx, day in enumerate(days, 1):
                    story.append(Paragraph(f'{idx}.  {day:%d/%m/%Y}', normal))
            else:
                story.append(Paragraph('Nessuna assenza registrata per l’anno indicato.', normal))
            story.extend([Spacer(1, 10*mm),
                          Paragraph(f'<b>Totale assenze nell’anno {anno}: {len(days)}</b>', bold)])
        else:
            story.append(Paragraph('Ditta non disponibile.', normal))
        story.extend([Spacer(1, 14*mm), Paragraph('Prospetto generato dal registro informatico SIPA.', styles['Normal']),
                      Paragraph('Data di stampa: ' + now.strftime('%d/%m/%Y %H:%M'), styles['Normal'])])
        doc.build(story)
        return target

    # Preferire A4 orizzontale; passare ad A3 se le date sarebbero troppo strette.
    # In nessun caso generare fogli più grandi di A3.
    count = len(date_colonne)
    margin = 5*mm
    fixed_widths = [43*mm, 10*mm, 28*mm, 11*mm]  # ditta, posto, luogo, totale
    def space_for_dates(page):
        return page[0] - 2*margin - sum(fixed_widths)
    paper = landscape(A4)
    # Sotto 3,1 mm per data si passa ad A3, mantenendo il PDF stampabile.
    if count and space_for_dates(paper) / count < 3.1*mm:
        paper = landscape(A3)
    date_width = space_for_dates(paper) / max(count, 1)
    # Se ci sono moltissime date, non eccedere l'A3: comprimere ulteriormente.
    date_font = max(2.0, min(4.2, date_width / 2.9))
    value_font = max(2.0, min(4.5, date_width / 2.7))
    doc = SimpleDocTemplate(str(target), pagesize=paper, leftMargin=margin,
                            rightMargin=margin, topMargin=9*mm, bottomMargin=9*mm)
    compact = ParagraphStyle('matrix_a4_compact', parent=styles['Normal'],
                             fontSize=5.5, leading=6.5)
    compact_bold = ParagraphStyle('matrix_a4_compact_bold', parent=compact,
                                  fontName='Helvetica-Bold')
    title_style = ParagraphStyle('matrix_a4_title', parent=styles['Heading3'],
                                 fontSize=10, leading=12)
    subtitle_style = ParagraphStyle('matrix_a4_subtitle', parent=styles['Normal'],
                                    fontSize=7, leading=9)
    story = [Paragraph(f'SIPA — PROSPETTO COMPLESSIVO ASSENZE — ANNO {anno}', title_style),
             Paragraph('Stampato il ' + now.strftime('%d/%m/%Y %H:%M') +
                       ' — Ditte attive; X = assenza registrata', subtitle_style),
             Spacer(1, 3*mm)]
    # Due righe d'intestazione: mesi raggruppati e giorno (DD) ruotato a 90°.
    # Le colonne ditta/posto/luogo/totale occupano entrambe le righe.
    month_headers = [Paragraph(x, compact_bold) for x in ('Ditta', 'Posto', 'Luogo')]
    month_headers += [''] * count
    month_headers += [Paragraph('Tot.', compact_bold)]
    day_headers = ['', '', ''] + [
        _VerticalDate(x.strftime('%d'), height=17, width=date_width, font_size=date_font)
        for x in date_colonne
    ] + ['']
    rows = [month_headers, day_headers]
    month_spans = []
    start = 0
    while start < count:
        end = start + 1
        while end < count and (date_colonne[end].year, date_colonne[end].month) == (date_colonne[start].year, date_colonne[start].month):
            end += 1
        left, right = 3 + start, 3 + end - 1
        month_headers[left] = date_colonne[start].strftime('%m/%Y')
        if right > left:
            month_spans.append(('SPAN', (left, 0), (right, 0)))
        start = end
    for d in ditte:
        days = {(d['id'], day) for day in date_colonne}
        total = sum(item in assenti for item in days)
        rows.append([Paragraph(escape(str(d['denominazione'])), compact_bold),
                     Paragraph(escape(str(d['numero_posto'])), compact),
                     Paragraph(escape(str(d['luogo'])), compact)] +
                    [('X' if (d['id'], day) in assenti else '') for day in date_colonne] + [str(total)])
    if not ditte:
        rows.append([Paragraph('Nessuna ditta attiva', compact)] + [''] * (len(month_headers)-1))
    widths = fixed_widths[:3] + [date_width] * count + fixed_widths[3:]
    table = Table(rows, colWidths=widths, repeatRows=2, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,1), colors.HexColor('#E9EFF5')),
        ('GRID',(0,0),(-1,-1),.25,colors.HexColor('#CBD5E1')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(3,0),(-1,-1),'CENTER'),
        ('VALIGN',(3,0),(-2,0),'MIDDLE'),
        ('ROWBACKGROUNDS',(0,2),(-1,-1),[colors.white, colors.HexColor('#F8FAFC')]),
        ('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),
        ('LEFTPADDING',(3,0),(-2,-1),0),('RIGHTPADDING',(3,0),(-2,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),1.4),('BOTTOMPADDING',(0,0),(-1,-1),1.4),
        ('FONTNAME',(3,2),(-1,-1),'Helvetica-Bold'),
        ('FONTSIZE',(3,2),(-2,-1),value_font),
        ('FONTSIZE',(3,0),(-2,0), min(5.5, max(3.0,date_width/2))),
        ('FONTSIZE',(-1,2),(-1,-1),5.5),
        ('SPAN',(0,0),(0,1)),('SPAN',(1,0),(1,1)),
        ('SPAN',(2,0),(2,1)),('SPAN',(-1,0),(-1,1)),
        *month_spans,
    ]))
    story.append(table)
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 6)
        canvas.drawRightString(paper[0]-margin, 3*mm, f'Pagina {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return target


def stampa_assenze_giorno(ditte, giorno):
    """Attestazione delle assenze registrate in una data, per luogo mercatino."""
    from collections import defaultdict
    day_label = giorno.strftime('%d/%m/%Y')
    now = datetime.now()
    target = Path.home() / 'SIPA_Stampe' / f'mercatino_assenze_giorno_{giorno:%Y%m%d}_{now:%Y%m%d_%H%M%S_%f}.pdf'
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle('day_cert_title', parent=styles['Title'], fontSize=14, leading=18)
    group_style = ParagraphStyle('day_cert_group', parent=styles['Heading2'], fontSize=11, leading=15, spaceBefore=12)
    text_style = ParagraphStyle('day_cert_text', parent=styles['Normal'], fontSize=9, leading=14)
    strong_style = ParagraphStyle('day_cert_strong', parent=text_style, fontName='Helvetica-Bold')
    by_location = defaultdict(list)
    for d in ditte:
        by_location[d['luogo']].append(d)
    story = [Paragraph('SIPA — ATTESTAZIONE ASSENZE MERCATINO', title), Spacer(1, 5*mm),
             Paragraph(f'<b>Data di rilevazione: {day_label}</b>', strong_style), Spacer(1, 4*mm),
             Paragraph('Il registro informatico SIPA riporta, per la data indicata, le seguenti assenze, suddivise per luogo di mercatino:', text_style)]
    if not by_location:
        story.extend([Spacer(1, 5*mm), Paragraph('Nessuna assenza registrata nella data selezionata.', text_style)])
    for luogo, records in sorted(by_location.items(), key=lambda x: x[0].casefold()):
        story.append(Paragraph('Luogo: ' + escape(luogo), group_style))
        for i, d in enumerate(sorted(records, key=lambda x: (str(x['numero_posto']), x['denominazione'])), 1):
            story.append(Paragraph(f"{i}. <b>{escape(d['denominazione'])}</b> — Posto {escape(str(d['numero_posto']))} — Stato: {escape(d['stato'])}", text_style))
        story.append(Paragraph(f'<b>Totale assenze del luogo: {len(records)}</b>', strong_style))
    story.extend([Spacer(1, 8*mm), Paragraph(f'<b>Totale complessivo assenze: {len(ditte)}</b>', strong_style),
                  Spacer(1, 8*mm), Paragraph('Prospetto generato dal registro informatico SIPA. Le risultanze si riferiscono alle registrazioni presenti al momento della stampa.', text_style),
                  Paragraph('Stampato il ' + now.strftime('%d/%m/%Y %H:%M'), text_style)])
    doc = SimpleDocTemplate(str(target), pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm)
    def footer(canvas, document):
        canvas.saveState(); canvas.setFont('Helvetica', 8)
        canvas.drawRightString(A4[0]-20*mm, 9*mm, f'Pagina {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return target
