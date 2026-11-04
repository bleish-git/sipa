"""Stampe Mercatino v0.60 basate sugli esiti salvati delle rilevazioni confermate."""
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,A3,landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether


def _target(prefix):
    from output_settings import export_path
    return export_path(prefix,'pdf')


def _doc(path,page=landscape(A4)):
    return SimpleDocTemplate(str(path),pagesize=page,leftMargin=12*mm,rightMargin=12*mm,topMargin=13*mm,bottomMargin=12*mm)


def _footer(canvas,doc):
    canvas.saveState();canvas.setFont('Helvetica',7)
    canvas.drawRightString(doc.pagesize[0]-12*mm,6*mm,f'Pagina {doc.page}');canvas.restoreState()


def _p(text,bold=False,size=8):
    style=ParagraphStyle('dyn',fontName='Helvetica-Bold' if bold else 'Helvetica',fontSize=size,leading=size+3)
    return Paragraph(escape(str(text or '')),style)


def stampa_elenco(records,ricerca='',luoghi=None,stato='Tutti'):
    path=_target('mercatino_elenco')
    rows=[[_p('Denominazione',True),_p('Luoghi / giornate / posti',True),_p('Stato',True)]]
    rows.extend([_p(r['denominazione'],True),_p(r['luoghi_posti']),_p(r['stato'],True)] for r in records)
    if len(rows)==1:rows.append([_p('Nessuna ditta'),'',''])
    table=Table(rows,colWidths=[75*mm,166*mm,30*mm],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E9EFF5')),
        ('GRID',(0,0),(-1,-1),.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F8FAFC')])]))
    s=getSampleStyleSheet();story=[Paragraph('SIPA — Elenco ditte Mercatino',s['Title']),
        _p('Stampato il '+datetime.now().strftime('%d/%m/%Y %H:%M')),
        _p(f'Ricerca: {ricerca or "nessuna"} — Stato: {stato} — Risultati: {len(records)}'),Spacer(1,5*mm),table]
    _doc(path).build(story,onFirstPage=_footer,onLaterPages=_footer)
    return path


def stampa_accertamento(rows,giorno):
    """Accertamenti assenze PER DATA e LUOGO; solo rilevazioni confermate."""
    path=_target('mercatino_accertamento_'+giorno.strftime('%Y%m%d'))
    s=getSampleStyleSheet()
    story=[Paragraph('SIPA — Prospetto di accertamento delle assenze',s['Title']),
           _p('Data di rilevazione: '+giorno.strftime('%d/%m/%Y'),True),
           _p('Data di stampa: '+datetime.now().strftime('%d/%m/%Y %H:%M')),Spacer(1,6*mm)]
    for r in rows:
        blocks=[Paragraph(escape(r['luogo']+' — '+r['settimanale']),s['Heading2']),
            _p('Operatore: '+r['operatore']),
            _p(f"Presenti: {r['presenti']} — Assenti: {len(r['assenti'])} — Esclusi: {r['esclusi']}")]
        if r['assenti']:
            for i,a in enumerate(r['assenti'],1):
                blocks.append(_p(f"{i}. {a['denominazione']} — Posto {a['posto']}",True))
        else:blocks.append(_p('Nessuna assenza registrata.'))
        blocks.extend([_p('Note: '+r['note']) if r['note'] else Spacer(1,2*mm),Spacer(1,7*mm)])
        story.append(KeepTogether(blocks))
    if not rows:story.append(_p('Non risultano rilevazioni confermate per la data selezionata.'))
    _doc(path,page=A4).build(story,onFirstPage=_footer,onLaterPages=_footer)
    return path


def stampa_assenze_ditta(nome,anno,rows):
    path=_target('mercatino_assenze_ditta')
    s=getSampleStyleSheet()
    story=[Paragraph('SIPA — Prospetto assenze della ditta',s['Title']),Spacer(1,6*mm),
        _p('Denominazione: '+nome,True,11),_p('Anno di riferimento: '+str(anno),True,11),
        Spacer(1,5*mm),_p('Dalle rilevazioni confermate risultano le seguenti assenze:'),Spacer(1,3*mm)]
    for i,r in enumerate(rows,1):story.append(_p(f"{i}. {r['giorno']:%d/%m/%Y} — {r['luogo']} — posto {r['posto']}"))
    if not rows:story.append(_p('Nessuna assenza registrata.'))
    story.extend([Spacer(1,7*mm),_p(f'Totale assenze nell’anno {anno}: {len(rows)}',True,11),
                  Spacer(1,4*mm),_p('Stampato il '+datetime.now().strftime('%d/%m/%Y %H:%M'))])
    _doc(path,page=A4).build(story,onFirstPage=_footer,onLaterPages=_footer);return path


def stampa_assenze_generale(ditte,anno,rows):
    """Matrice a larghezza contenuta: intestazione mesi + giorno DD, massimo A3 orizzontale."""
    days=sorted({r['giorno'] for r in rows})
    width_a4=landscape(A4)[0]-20*mm
    available=width_a4-74*mm-15*mm
    page=landscape(A4) if not days or available/max(1,len(days))>=2.7*mm else landscape(A3)
    width=page[0]-20*mm
    col=(width-90*mm)/max(len(days),1)
    if col<1.6*mm:
        raise ValueError('Troppe date per un solo foglio A3 leggibile: limitare l’intervallo.')
    path=_target('mercatino_assenze_annuali')
    data=[['Ditta']+['' for _ in days]+['Tot.'],['']+[str(d.day).zfill(2) for d in days]+['']]
    merged=[];start=1
    while start<=len(days):
        end=start
        while end<len(days) and days[end].month==days[start-1].month:end+=1
        data[0][start]=days[start-1].strftime('%m/%Y')
        if end>start:merged.append(('SPAN',(start,0),(end,0)))
        start=end+1
    indexed={(r['ditta_id'],r['giorno']) for r in rows}
    for d in ditte:
        marks=[('X' if (d['id'],day) in indexed else '') for day in days]
        data.append([d['denominazione']]+marks+[str(sum(bool(x) for x in marks))])
    table=Table(data,colWidths=[74*mm]+([col]*len(days))+[16*mm],repeatRows=2)
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.15,colors.grey),
        ('BACKGROUND',(0,0),(-1,1),colors.HexColor('#E9EFF5')),('FONTSIZE',(0,0),(-1,-1),4),
        ('LEADING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),1),
        ('BOTTOMPADDING',(0,0),(-1,-1),1),('ALIGN',(1,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,2),(0,-1),'Helvetica-Bold')]+merged))
    s=getSampleStyleSheet()
    story=[Paragraph('SIPA — Prospetto annuale assenze '+str(anno),s['Title']),
           _p('Stampato il '+datetime.now().strftime('%d/%m/%Y %H:%M')),
           Spacer(1,4*mm),table]
    _doc(path,page=page).build(story,onFirstPage=_footer,onLaterPages=_footer);return path
