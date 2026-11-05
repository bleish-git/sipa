"""Esporta le assenze confermate in un documento Word basato sul modello dell'ufficio."""
from datetime import date
from pathlib import Path
import re
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from output_settings import export_path

TEMPLATE=Path(__file__).resolve().parent/'assets'/'Comunicazione_assenze_modello.docx'
WEEK=['lunedì','martedì','mercoledì','giovedì','venerdì','sabato','domenica']


def _bordi_tabella_neri(table):
    """Bordi neri, continui, sottili (0,5 pt), interni ed esterni."""
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn('w:tblBorders'))
    if borders is None:
        borders = OxmlElement('w:tblBorders')
        tbl_pr.append(borders)
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        element = borders.find(qn('w:' + edge))
        if element is None:
            element = OxmlElement('w:' + edge)
            borders.append(element)
        element.set(qn('w:val'), 'single')
        element.set(qn('w:sz'), '4')  # 4 ottavi di punto = 0,5 pt
        element.set(qn('w:color'), '000000')



def _chiave_posto(entry):
    """Ordine numerico naturale dei posti; valori non numerici in fondo."""
    posto = str(entry.get('posto') or '').strip()
    if not posto:
        return (2, (), '')
    parti = re.split(r'(\d+)', posto.casefold())
    if posto.isdecimal():
        return (0, (int(posto),), '')
    return (1, tuple((0, int(p)) if p.isdigit() else (1, p) for p in parti), posto.casefold())


def stampa_comunicazione_assenze(rows, giorno):
    if not isinstance(giorno,date):
        raise ValueError('Data della rilevazione non valida.')
    if not TEMPLATE.is_file():
        raise FileNotFoundError('Modello Word assente: '+str(TEMPLATE))
    document=Document(TEMPLATE)
    body=document.element.body
    # Il documento originale contiene intestazione, destinatario, oggetto,
    # tabelle per due luoghi e formula conclusiva. Conserviamo tutta la testata,
    # rigenerando soltanto la parte variabile dopo OGGETTO.
    paragraphs=document.paragraphs
    subject=next((p for p in paragraphs if p.text.strip().startswith('OGGETTO:')),None)
    closing=next((p for p in paragraphs if 'Con Osservanza' in p.text),None)
    if subject is None or closing is None:
        raise ValueError('Il modello Word non contiene OGGETTO e chiusura attesi.')
    places=', '.join(str(r['luogo']).strip() for r in rows)
    description=(f'OGGETTO: COMUNICAZIONE ASSENZE DEL MERCATINO '
                 f'DI {WEEK[giorno.weekday()].upper()} {giorno:%d/%m/%Y}'
                 + (f' — {places.upper()}' if places else ''))
    # Conserviamo la formattazione del primo segmento del paragrafo OGGETTO.
    if subject.runs:
        subject.runs[0].text=description
        for run in subject.runs[1:]:run.text=''
    else:
        subject.add_run(description)
    # Rimuove la vecchia lista di nomi (dati del modello), i vecchi titoli dei
    # luoghi e le due tabelle originali, senza toccare l'intestazione o la firma.
    current=subject._p.getnext()
    while current is not None and current is not closing._p:
        after=current.getnext()
        body.remove(current)
        current=after
    # Una riga vuota separa l'oggetto dalle tabelle (o dal messaggio di assenza dati).
    anchor=closing._p
    riga_vuota=document.add_paragraph('')
    anchor.addprevious(riga_vuota._p)
    if not rows:
        p=document.add_paragraph('Non risultano rilevazioni confermate per la data e il luogo selezionati.')
        anchor.addprevious(p._p)
    for item in rows:
        name=str(item['luogo']).upper()
        head=document.add_paragraph()
        heading_run=head.add_run(name)
        heading_run.bold=True
        heading_run.font.size=Pt(11)
        anchor.addprevious(head._p)
        entries=sorted(item.get('assenti') or [], key=_chiave_posto)
        if entries:
            table=document.add_table(rows=1, cols=2)
            # Il modello convertito da .doc non garantisce uno stile Table Grid.
            table.rows[0].cells[0].text='DITTA ASSENTE'
            table.rows[0].cells[1].text='POSTO N.'
            for cell in table.rows[0].cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:run.bold=True
            for entry in entries:
                cells=table.add_row().cells
                cells[0].text=str(entry['denominazione'])
                cells[1].text=str(entry['posto'])
            # Tutte le celle, compresa l'intestazione, sono in corpo 11 pt.
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size=Pt(11)
            _bordi_tabella_neri(table)
            table.columns[0].width=Cm(12)
            table.columns[1].width=Cm(3)
            anchor.addprevious(table._tbl)
        else:
            p=document.add_paragraph('Nessuna assenza risultante dalla rilevazione confermata.')
            anchor.addprevious(p._p)
        spacer=document.add_paragraph('')
        anchor.addprevious(spacer._p)
    target=export_path('comunicazione_assenze_'+giorno.strftime('%Y%m%d'),'docx')
    document.save(str(target))
    return target
