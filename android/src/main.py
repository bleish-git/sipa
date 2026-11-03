"""SIPA Presenze Android: app offline, senza login e senza accesso al DB SIPA."""
import flet as ft
from scambio_presenze import crea_esiti, leggi_elenco, serialize
import archivio_locale as archivio


def main(page: ft.Page):
    page.title='SIPA Presenze'
    page.theme_mode=ft.ThemeMode.LIGHT
    page.scroll=ft.ScrollMode.AUTO
    page.padding=16
    elenco=None
    presenti=set()
    testo=ft.Text(color=ft.Colors.RED_700)
    picker=ft.FilePicker()

    def notify(msg,error=False):
        testo.value=msg
        testo.color=ft.Colors.RED_700 if error else ft.Colors.GREEN_700
        page.update()

    def show(*controls):
        page.controls.clear()
        page.add(ft.Text('SIPA Presenze',size=24,weight=ft.FontWeight.BOLD),*controls,testo)
        testo.value=''
        page.update()

    def home(e=None):
        show(ft.Text('Rilevazione offline delle presenze del Mercatino.'),
             ft.Button('Rilevamento presenze',icon=ft.Icons.CHECKLIST,on_click=start),
             ft.OutlinedButton('About / Licenze',on_click=about))

    def about(e=None):
        show(ft.Text('SIPA Presenze — versione 0.1',weight=ft.FontWeight.BOLD),
             ft.Text('Modulo mobile del progetto SIPA, sviluppato in Python con Flet.'),
             ft.Text('© 2026 bleish — Licenza MIT. Flet e le altre dipendenze conservano le proprie licenze.'),
             ft.TextButton('Repository / Sviluppo: github.com/bleish-git/sipa',
                           on_click=lambda e:page.launch_url('https://github.com/bleish-git/sipa')),
             ft.TextButton('Indietro',on_click=home))

    async def importa(e):
        nonlocal elenco,presenti
        try:
            files=await picker.pick_files(allow_multiple=False,with_data=True,
                file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=['json'])
            if not files:return
            selected=files[0]
            raw=selected.bytes if selected.bytes else open(selected.path,'rb').read()
            nuovo=leggi_elenco(raw)
            # Sostituzione della bozza precedente SOLO dopo lettura valida, con conferma.
            def sostituisci(ev):
                nonlocal elenco,presenti
                elenco=nuovo;presenti=set()
                archivio.salva(elenco,presenti)
                if old:
                    page.pop_dialog()
                riepilogo()
            try:old=archivio.leggi()
            except Exception:old=None
            if old:
                dlg=ft.AlertDialog(modal=True,title=ft.Text('Sostituire la bozza?'),
                    content=ft.Text('L’importazione eliminerà le spunte della bozza precedente sul dispositivo. Procedere?'),
                    actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),
                             ft.Button('Importa e sostituisci',on_click=sostituisci)])
                page.show_dialog(dlg)
            else:sostituisci(None)
        except Exception as exc:notify(str(exc),True)

    def riprendi(e=None):
        nonlocal elenco,presenti
        try:
            data=archivio.leggi()
            if not data:raise ValueError('Nessuna bozza da riprendere.')
            elenco=data['elenco'];presenti=set(data['presenti']);riepilogo()
        except Exception as exc:notify(str(exc),True)

    def start(e=None):
        try:old=archivio.leggi()
        except Exception as exc:
            old=None;notify('Errore bozza locale: '+str(exc),True)
        actions=[ft.Button('Importa nuovo elenco dal PC',on_click=importa)]
        if old:actions.append(ft.OutlinedButton('Riprendi bozza non esportata',on_click=riprendi))
        show(ft.Text('Scegli come iniziare:'),*actions,ft.TextButton('Indietro',on_click=home))

    def riepilogo(e=None):
        if not elenco:return home()
        show(ft.Text('Riepilogo elenco',weight=ft.FontWeight.BOLD,size=18),
             ft.Text(f"Data: {elenco['data']}"),ft.Text(f"Mercato: {elenco['giornata']}"),
             ft.Text(f"Luogo: {elenco['luogo']}"),
             ft.Text(f"Ditte da controllare: {len(elenco['ditte'])}"),
             ft.Text(f"Già spuntate: {len(presenti)}"),
             ft.Text('Elenco: '+', '.join(x['denominazione'] for x in elenco['ditte'][:20]) +
                     (' ...' if len(elenco['ditte'])>20 else '')),
             ft.Button('Apri rilevazione',on_click=presenze),
             ft.TextButton('Indietro',on_click=start))

    def presenze(e=None):
        ricerca=ft.TextField(label='Cerca ditta (almeno 3 caratteri)',prefix_icon=ft.Icons.SEARCH)
        rows=ft.Column(spacing=3)
        count=ft.Text()
        ordered=sorted(elenco['ditte'],key=lambda x:(x['ordine'],str(x['posto']),x['denominazione']))
        checkboxes={}
        for d in ordered:
            aid=d['assegnazione_id']
            cb=ft.Checkbox(label=f"{d['denominazione']} — posto {d['posto']}",value=aid in presenti)
            def toggle(ev,aid=aid):
                if ev.control.value:presenti.add(aid)
                else:presenti.discard(aid)
                archivio.salva(elenco,presenti)
                count.value=f'{len(presenti)} presenti · {len(ordered)-len(presenti)} non spuntate'
                page.update()
            cb.on_change=toggle
            checkboxes[aid]=(d['denominazione'].casefold(),cb)
        def filter_rows(ev=None):
            q=(ricerca.value or '').strip().casefold()
            rows.controls=[cb for name,cb in checkboxes.values() if len(q)<3 or q in name]
            count.value=f'{len(presenti)} presenti · {len(ordered)-len(presenti)} non spuntate'
            page.update()
        async def esporta(ev):
            try:
                result=crea_esiti(elenco,presenti)
                data=serialize(result)
                path=await picker.save_file(file_name=f"sipa_esiti_{elenco['data']}_{elenco['elenco_id'][:8]}.json",
                    file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=['json'],src_bytes=data)
                if path:
                    # Solo dopo il salvataggio dichiarato riuscito la bozza viene eliminata.
                    archivio.cancella()
                    home()
                    notify('Esiti esportati. La bozza locale è stata rimossa.')
                else:notify('Esportazione annullata: la bozza è conservata.',True)
            except Exception as exc:notify('Esportazione non riuscita: '+str(exc),True)
        def back(ev):
            archivio.salva(elenco,presenti)
            riepilogo()
        ricerca.on_change=filter_rows
        show(ft.Text(f"{elenco['giornata']} — {elenco['data']}"),
             ft.Text('Spuntare esclusivamente le ditte presenti.'),ricerca,count,
             ft.Container(content=rows,height=380),
             ft.Button('Esporta sul dispositivo',icon=ft.Icons.SAVE_ALT,on_click=esporta),
             ft.TextButton('Indietro (salva automaticamente)',on_click=back))
        filter_rows()

    home()

if __name__=='__main__':
    ft.run(main)
