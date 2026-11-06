"""SIPA - Sistema Informativo Polizia Amministrativa."""
import sys
from db_settings import CONFIG

# First-run setup must happen before importing database, which creates the engine.
if __name__ == '__main__':
    if '--init-admin' in sys.argv:
        from setup_wizard import cli_setup
        cli_setup()
        raise SystemExit(0)
    if not CONFIG.exists():
        from setup_wizard import launch_gui
        launch_gui()
        raise SystemExit(0)

import json
import traceback
from datetime import datetime
from pathlib import Path
from db_settings import read_settings
import flet as ft
from database import init_database, engine, log
from schema import revision, HEAD
from operations import backup as create_backup, inspect_backup, maintenance_upgrade
from sqlalchemy.orm import Session
from security import (authenticate, bootstrap, has_permission, role_permissions, set_role_permissions, list_users, list_events, create_user,
                      update_user, reset_password, change_password)

from db_admin_guide import DB_ADMIN_GUIDE
ASSETS = Path(__file__).resolve().parent / 'assets'
SECTIONS = [
    ('Dashboard', ft.Icons.DASHBOARD_OUTLINED),
    ('Attività economiche', ft.Icons.STOREFRONT_OUTLINED),
    ('Mercatino', ft.Icons.STORE_OUTLINED),
    ('Sanzioni amministrative', ft.Icons.DESCRIPTION_OUTLINED),
    ('Accertamenti', ft.Icons.FACT_CHECK_OUTLINED),
    ('Archivio documentale', ft.Icons.FOLDER_OUTLINED),
    ('Amministrazione', ft.Icons.MANAGE_ACCOUNTS_OUTLINED),
]

def main(page: ft.Page):
    page.title = 'SIPA - Sistema Informativo Polizia Amministrativa'
    page.theme_mode = ft.ThemeMode.LIGHT
    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale('it', 'IT')],
        current_locale=ft.Locale('it', 'IT'),
    )
    page.padding = 0
    page.window.width = 1160
    page.window.height = 760
    page.window.min_width = 880
    page.window.min_height = 600
    try:
        page.window.icon = str(ASSETS / 'sipa-icon.png')
    except Exception:
        pass
    user = None
    selected_section = 0

    def campo_data(label, valore='', width=None, read_only=False):
        """Campo GG/MM/AAAA con calendario Flet e callback di aggiornamento.

        Mantiene un TextField autentico, così i salvataggi e i filtri già presenti
        continuano a utilizzare .value, .on_change e .on_blur senza adattamenti.
        """
        field = ft.TextField(
            label=label,
            value=str(valore or ''),
            width=width,
            read_only=read_only,
        )

        def apri_calendario(e=None):
            try:
                iniziale = datetime.strptime((field.value or '').strip(), '%d/%m/%Y')
            except (TypeError, ValueError):
                iniziale = datetime.now()

            def data_scelta(event):
                scelta = event.control.value
                if scelta is None:
                    return
                # Flet può restituire la mezzanotte italiana come istante UTC
                # del giorno precedente. Convertire prima al fuso locale evita
                # lo slittamento senza alterare le date scelte dall'utente.
                if isinstance(scelta, str):
                    scelta = datetime.fromisoformat(scelta.replace('Z', '+00:00'))
                if scelta.tzinfo is not None:
                    scelta = scelta.astimezone()
                field.value = scelta.strftime('%d/%m/%Y')
                field.error = None
                # Attiva gli stessi ricalcoli previsti quando l'utente digita.
                handler = field.on_change
                if handler is not None:
                    handler(event)
                page.update()

            picker = ft.DatePicker(
                value=iniziale.replace(hour=12, minute=0, second=0, microsecond=0),
                first_date=datetime(1900, 1, 1),
                last_date=datetime(2100, 12, 31),
                locale=ft.Locale('it', 'IT'),
                help_text='Seleziona data',
                field_hint_text='GG/MM/AAAA',
                field_label_text='Data',
                error_format_text='Formato non valido',
                error_invalid_text='Data fuori intervallo',
                confirm_text='Conferma',
                cancel_text='Annulla',
                on_change=data_scelta,
            )
            page.show_dialog(picker)

        if not read_only:
            field.suffix = ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                tooltip='Scegli data dal calendario',
                on_click=apri_calendario,
            )
        return field

    def logo(width=250):
        return ft.Image(src='logo-sipa.png', width=width, fit=ft.BoxFit.CONTAIN)

    def notify(message, error=False):
        page.show_dialog(ft.SnackBar(ft.Text(message), bgcolor=ft.Colors.RED_700 if error else ft.Colors.GREEN_700))

    def logout(e=None):
        nonlocal user
        if user:
            with Session(engine) as session:
                log(session, user['username'], 'logout')
                session.commit()
        user = None
        login_screen()

    def password_dialog(force=False):
        old = ft.TextField(label='Password attuale', password=True, can_reveal_password=True)
        new = ft.TextField(label='Nuova password (min. 12 caratteri)', password=True, can_reveal_password=True)
        repeat = ft.TextField(label='Conferma nuova password', password=True, can_reveal_password=True)
        message = ft.Text(color=ft.Colors.RED_700)
        dlg = ft.AlertDialog(modal=True, title=ft.Text('Cambio password'),
            content=ft.Column([old, new, repeat, message], tight=True, width=390), actions=[])
        def save(e):
            if new.value != repeat.value:
                message.value = 'Le nuove password non coincidono.'
                page.update()
                return
            try:
                change_password(user['id'], old.value or '', new.value or '')
                user['must_change_password'] = False
                page.pop_dialog()
                notify('Password aggiornata.')
                dashboard()
            except (ValueError, PermissionError) as exc:
                message.value = str(exc)
                page.update()
        dlg.actions = [ft.Button('Salva password', on_click=save)]
        if not force:
            dlg.actions.insert(0, ft.TextButton('Annulla', on_click=lambda e: page.pop_dialog()))
        page.show_dialog(dlg)

    def login_screen():
        page.clean()
        username = ft.TextField(label='Nome utente', width=350, autofocus=True)
        password = ft.TextField(label='Password', password=True, can_reveal_password=True, width=350)
        error = ft.Text(color=ft.Colors.RED_700)
        def submit(e):
            nonlocal user
            user = authenticate(username.value or '', password.value or '')
            if user is None:
                error.value = 'Accesso non consentito. Verifica credenziali o riprova tra 15 minuti.'
                password.value = ''
                page.update()
                return
            dashboard()
            if user['must_change_password']:
                password_dialog(force=True)
        password.on_submit = submit
        card = ft.Container(width=470, padding=35, border_radius=18, bgcolor=ft.Colors.WHITE,
            content=ft.Column([
                logo(285),
                ft.Text('Sistema Informativo Polizia Amministrativa', size=15, text_align=ft.TextAlign.CENTER),
                ft.Divider(), username, password, error,
                ft.Button('Accedi', icon=ft.Icons.LOGIN, width=350, on_click=submit),
                ft.Row([ft.Text('© 2026', size=12, color=ft.Colors.GREY_600), ft.TextButton('bleish', url='https://github.com/bleish-git/sipa'), ft.Text('• SIPA v0.60 • Licenza MIT', size=12, color=ft.Colors.GREY_600)], spacing=3, alignment=ft.MainAxisAlignment.CENTER),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15))
        page.add(ft.Container(content=card, alignment=ft.Alignment.CENTER, expand=True, bgcolor=ft.Colors.BLUE_GREY_50))
        page.update()

    def dashboard():
        nonlocal selected_section
        page.clean()
        if selected_section == 6 and not has_permission(user['id'], 'users.manage'):
            selected_section = 0
        content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)
        navigation = ft.Column(spacing=5)

        def choose(index):
            nonlocal selected_section
            if user['must_change_password']:
                password_dialog(force=True)
                return
            if index == 6 and not has_permission(user['id'], 'users.manage'):
                return
            needed = {0:'dashboard.view',1:'attivita.read',2:'mercatino.read',3:'verbali.read',4:'accertamenti.read',5:'documenti.read',6:'users.manage'}[index]
            if not has_permission(user['id'], needed):
                notify('Accesso non autorizzato a questo settore.', True)
                return
            selected_section = index
            # Ricostruisce la vista intera: evita aggiornamenti incrementali
            # su controlli che Flet potrebbe non avere ancora montato.
            dashboard()

        def render_navigation():
            navigation.controls.clear()
            for i, (label, icon) in enumerate(SECTIONS):
                required = {0:'dashboard.view',1:'attivita.read',2:'mercatino.read',3:'verbali.read',4:'accertamenti.read',5:'documenti.read',6:'users.manage'}[i]
                if not has_permission(user['id'], required):
                    continue
                navigation.controls.append(ft.Button(label, icon=icon, width=244,
                    bgcolor=ft.Colors.BLUE_100 if i == selected_section else None,
                    style=ft.ButtonStyle(alignment=ft.Alignment.CENTER_LEFT),
                    on_click=lambda e, index=i: choose(index)))

        def render_content():
            content.controls.clear()
            title = SECTIONS[selected_section][0]
            content.controls.extend([
                ft.Text(title, size=28, weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text('© 2026', color=ft.Colors.GREY_700), ft.TextButton('bleish', url='https://github.com/bleish-git/sipa'), ft.Text('• Licenza MIT • github.com/bleish-git/sipa', color=ft.Colors.GREY_700)], spacing=3),
                ft.Divider(),
            ])
            if selected_section == 6:
                render_admin(content)
            elif selected_section == 2:
                try:
                    render_mercatino(content)
                except Exception as exc:
                    traceback.print_exc()
                    content.controls.append(ft.Text(f'Errore Mercatino: {type(exc).__name__}: {exc}', color=ft.Colors.RED_700, selectable=True))
            elif selected_section == 1:
                try:
                    render_attivita(content)
                except Exception as exc:
                    traceback.print_exc()
                    content.controls.append(ft.Text(
                        'Errore durante il caricamento delle attività economiche: '
                        + f'{type(exc).__name__}: {exc}', color=ft.Colors.RED_700,
                        selectable=True))
            elif selected_section == 0:
                content.controls.append(ft.ResponsiveRow([
                    ft.Container(ft.Column([ft.Icon(ft.Icons.STOREFRONT_OUTLINED), ft.Text('Attività cessate', weight=ft.FontWeight.BOLD), ft.Text('Registro da implementare')]), padding=24, bgcolor=ft.Colors.BLUE_50, border_radius=12, col={'sm': 6}),
                    ft.Container(ft.Column([ft.Icon(ft.Icons.DESCRIPTION_OUTLINED), ft.Text('Verbali amministrativi', weight=ft.FontWeight.BOLD), ft.Text('Registro da implementare')]), padding=24, bgcolor=ft.Colors.GREEN_50, border_radius=12, col={'sm': 6}),
                ]))
            else:
                content.controls.append(ft.Container(padding=25, border_radius=12, bgcolor=ft.Colors.BLUE_GREY_50,
                    content=ft.Column([ft.Icon(SECTIONS[selected_section][1], size=42),
                        ft.Text(f'Modulo {title}', size=20, weight=ft.FontWeight.BOLD),
                        ft.Text('Modulo predisposto: le funzioni operative saranno sviluppate nelle prossime fasi.')], tight=True)))

        render_navigation()
        render_content()
        sidebar = ft.Container(width=270, padding=14, bgcolor=ft.Colors.BLUE_GREY_50,
            content=ft.Column([
                logo(210), ft.Divider(), navigation, ft.Container(expand=True),
                ft.Text(f"{user['username']} • {user['role']}", size=12),
                ft.OutlinedButton('Cambia password', icon=ft.Icons.LOCK_OUTLINE, on_click=lambda e: password_dialog()),
                ft.OutlinedButton('Esci', icon=ft.Icons.LOGOUT, on_click=logout),
            ], expand=True))
        page.add(ft.Row([sidebar, ft.Container(content=content, expand=True, padding=28)], expand=True, spacing=0))
        page.update()

    def render_attivita(content):
        from attivita import elenco, dettaglio, salva, TIPOLOGIE
        can_create = has_permission(user['id'], 'attivita.create')
        can_update = has_permission(user['id'], 'attivita.update')
        search = ft.TextField(
            label='Ricerca OR (almeno 3 caratteri complessivi; termini di qualsiasi lunghezza)',
            width=450, prefix_icon=ft.Icons.SEARCH,
        )
        status = ft.Dropdown(label='Stato', value='Tutte', width=180,
            options=[ft.dropdown.Option(v) for v in ('Tutte', 'Attiva', 'Da iniziare', 'Sospesa', 'Cessata')])
        results = ft.Column(spacing=4)
        counter = ft.Text(size=12, color=ft.Colors.GREY_700)
        displayed_records = []

        def refresh(e=None, initial=False):
            nonlocal displayed_records
            term = (search.value or '').strip()
            if term and len(term) < 3:
                # Ricerca ancora incompleta: non cancellare l'ultimo elenco valido.
                counter.value = 'Ricerca incompleta: inserisci almeno 3 caratteri oppure svuota il campo.'
                if not initial:
                    page.update()
                return
            try:
                data = elenco(user['id'], term, status.value or 'Tutte')
                displayed_records = data
                counter.value = f'{len(data)} attività trovate'
                results.controls = []
                for item in data:
                    label = ft.Text(item['nome'], weight=ft.FontWeight.BOLD, expand=True)
                    subtitle = ft.Text(item['titolare'] or 'Titolare non indicato', size=12, color=ft.Colors.GREY_700)
                    color = (ft.Colors.GREEN_700 if item['stato'] == 'Attiva' else
                             ft.Colors.ORANGE_700 if item['stato'] == 'Da iniziare' else
                             ft.Colors.AMBER_800 if item['stato'] == 'Sospesa' else ft.Colors.RED_700)
                    results.controls.append(ft.Container(
                        bgcolor=ft.Colors.BLUE_GREY_50, border_radius=8, padding=12,
                        on_click=lambda e, pk=item['id']: open_detail(pk),
                        ink=True,
                        content=ft.Row([
                            ft.Column([label, subtitle], expand=True, spacing=3),
                            ft.Text(item['stato'], color=color, width=100),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT),
                        ])))
                if not data:
                    results.controls.append(ft.Text('Nessuna attività corrispondente ai criteri selezionati.'))
            except (ValueError, TypeError) as exc:
                counter.value = 'Filtro non valido: ' + str(exc)
            except Exception as exc:
                traceback.print_exc()
                counter.value = 'Impossibile aggiornare l’elenco: ' + str(exc)
            if not initial:
                page.update()

        def open_detail(item_id=None):
            if item_id is None and not can_create:
                notify('Inserimento non autorizzato.', True)
                return
            try:
                item = dettaglio(user['id'], item_id) if item_id is not None else {}
            except (ValueError, PermissionError) as exc:
                notify(str(exc), True)
                return
            editable = can_update if item_id is not None else can_create
            def field(key, label, multiline=False):
                if key.startswith('data_'):
                    return campo_data(label, item.get(key, '') or '', read_only=not editable)
                return ft.TextField(label=label, value=((item.get(key, '') or '').upper() if key == 'nome' else (item.get(key, '') or '')),
                    read_only=not editable, multiline=multiline,
                    min_lines=2 if multiline else 1, max_lines=4 if multiline else 1)
            fields = {key: field(key, label, multiline) for key, label, multiline in [
                ('nome', 'Nome attività *', False),
                ('titolare', 'Titolare', False),
                ('pec', 'PEC', False),
                ('descrizione', 'Descrizione', True),
                ('note', 'Note', True),
                ('data_inizio', 'Data inizio (GG/MM/AAAA)', False),
                ('data_cessazione', 'Data cessazione (GG/MM/AAAA)', False),
                ('data_sospensione_inizio', 'Inizio sospensione (GG/MM/AAAA)', False),
                ('data_sospensione_fine', 'Fine sospensione (GG/MM/AAAA)', False),
            ]}
            fields['tipologia'] = ft.Dropdown(
                label='Tipologia', value=item.get('tipologia') or 'Non specificata',
                options=[ft.dropdown.Option(v) for v in TIPOLOGIE], disabled=not editable)
            error = ft.Text(color=ft.Colors.RED_700)
            detail_controls = list(fields.values())
            if item_id is not None:
                stato_colori = {
                    'Attiva': ft.Colors.GREEN_700,
                    'Da iniziare': ft.Colors.ORANGE_700,
                    'Sospesa': ft.Colors.AMBER_800,
                    'Cessata': ft.Colors.RED_700,
                }
                detail_controls.insert(0, ft.Text(
                    'Stato attuale: ' + item['stato'],
                    weight=ft.FontWeight.BOLD,
                    color=stato_colori.get(item['stato'], ft.Colors.GREY_700),
                ))
            detail_controls.append(error)
            dlg = ft.AlertDialog(modal=True,
                title=ft.Text('Nuova attività economica' if item_id is None else 'Dettaglio attività economica'),
                content=ft.Column(detail_controls, tight=True, width=580, height=530,
                                  scroll=ft.ScrollMode.AUTO), actions=[])
            def save(e):
                try:
                    values = {key: control.value for key, control in fields.items()}
                    salva(user['id'], user['username'], values, item_id)
                    page.pop_dialog()
                    refresh()
                    notify('Attività salvata correttamente.')
                except (ValueError, PermissionError) as exc:
                    error.value = str(exc)
                    page.update()
                except Exception as exc:
                    error.value = 'Salvataggio non riuscito: ' + str(exc)
                    page.update()
            dlg.actions = [ft.TextButton('Chiudi', on_click=lambda e: page.pop_dialog())]
            if editable:
                dlg.actions.append(ft.Button('Salva', icon=ft.Icons.SAVE, on_click=save))
            page.show_dialog(dlg)

        def stampa_elenco(e):
            try:
                if (search.value or '').strip() and len((search.value or '').strip()) < 3:
                    notify('Per stampare, inserisci almeno 3 caratteri o svuota la ricerca.', True)
                    return
                # Query ripetuta per rendere il documento coerente coi filtri attuali.
                records = elenco(user['id'], search.value or '', status.value or 'Tutte')
                from stampa_attivita import stampa_pdf
                path = stampa_pdf(records, search.value or '', status.value or 'Tutte')
                notify(f'PDF creato: {path}')
            except Exception as exc:
                notify('Errore nella creazione del PDF: ' + str(exc), True)

        search.on_change = refresh
        status.on_select = refresh
        status.on_change = refresh
        buttons = [ft.OutlinedButton('Aggiorna', icon=ft.Icons.REFRESH, on_click=refresh),
                   ft.OutlinedButton('Stampa elenco PDF', icon=ft.Icons.PRINT, on_click=stampa_elenco)]
        if can_create:
            buttons.append(ft.Button('Nuova attività', icon=ft.Icons.ADD, on_click=lambda e: open_detail()))
        content.controls.extend([
            ft.Text('Registro attività economiche', size=17, weight=ft.FontWeight.W_600),
            ft.Row([search, status], wrap=True, spacing=12),
            ft.Row(buttons, wrap=True), counter, results,
        ])
        # Carica i dati dopo aver montato i controlli nella pagina.
        # Evita errori silenziosi durante la costruzione della schermata.
        refresh(initial=True)

    def render_mercatino(content):
        """Mercatino: anagrafiche, assegnazioni, provvedimenti, presenze e stampe."""
        from datetime import date
        from mercatino import (GIORNI, STATI, TIPI, data_input, luoghi as m_luoghi,
             giornate as m_giornate, elenco as m_elenco, dettaglio as m_dettaglio,
             salva_luogo, salva_giornata, salva_ditta, salva_assegnazione,
             modifica_luogo, elimina_luogo, modifica_giornata, elimina_giornata,
             modifica_assegnazione, elimina_assegnazione,
             provvedimenti, salva_provvedimento, anteprima, salva_rilevazione,
             bozze_rilevazioni, elimina_bozza,
             accertamenti, assenze_anno)
        from stampa_mercatino import (stampa_elenco,stampa_accertamento,
                                      stampa_assenze_ditta,stampa_assenze_generale)
        from scambio_presenze import crea_elenco, leggi_esiti, serialize
        from mercatino import importa_esiti_mobile
        uid=user['id']; username=user['username']
        can_edit=has_permission(uid,'mercatino.update'); can_create=has_permission(uid,'mercatino.create')
        can_presence=has_permission(uid,'mercatino.absence');can_print=has_permission(uid,'mercatino.export')
        # Le date vengono digitate un carattere alla volta: non propagare
        # eccezioni dai callback dinamici durante l'immissione incompleta.
        def week(raw):
            try:
                return GIORNI[data_input(raw).weekday()] if (raw or '').strip() else ''
            except (ValueError, TypeError, AttributeError):
                return ''

        def valida_data_in_linea(raw, testo_errore, *, segnalazione=False):
            """Valida senza interrompere i callback Flet; ritorna la data o None."""
            try:
                parsed = data_input(raw)
            except (ValueError, TypeError, AttributeError):
                testo_errore.value = 'Data non valida: usare GG/MM/AAAA (es. 04/11/2026).'
                if segnalazione:
                    notify(testo_errore.value, True)
                return None
            testo_errore.value = ''
            return parsed
        today=date.today().strftime('%d/%m/%Y')
        search=ft.TextField(label='Cerca ditta (almeno 3 caratteri)',width=340,prefix_icon=ft.Icons.SEARCH)
        state=ft.Dropdown(label='Stato',value='Tutti',width=150,
                          options=[ft.dropdown.Option(x) for x in ('Tutti',)+STATI])
        summary=ft.Text(size=12)
        result=ft.Column(spacing=4)
        year=ft.TextField(label='Anno prospetto',value=str(date.today().year),width=115)
        selected_places=set()
        def fail(e):notify(str(e),True)
        def textinput(label,value='',width=280):return ft.TextField(label=label,value=str(value or ''),width=width)
        def dropdown(label,options,value=None,width=280):
            return ft.Dropdown(label=label,value=str(value) if value is not None else None,width=width,
                options=[ft.dropdown.Option(key=str(key),text=str(text)) for key,text in options])
        def date_field(label,initial=today):
            return campo_data(label+' (GG/MM/AAAA)',initial,width=230)
        def dialog(title,controls,on_save=None,button='Salva',width=570,height=450):
            error=ft.Text(color=ft.Colors.RED_700)
            actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog())]
            if on_save:
                def do_save(e):
                    try:on_save();page.pop_dialog();refresh();notify('Operazione completata.')
                    except Exception as exc:error.value=str(exc);page.update()
                actions.append(ft.Button(button,on_click=do_save))
            dlg=ft.AlertDialog(modal=True,title=ft.Text(title),
                content=ft.Column(list(controls)+[error],width=width,height=height,scroll=ft.ScrollMode.AUTO),
                actions=actions)
            page.show_dialog(dlg)
            return dlg
        def gestisci_luoghi(e=None):
            records=ft.Column(spacing=3)
            nome=textinput('Nome luogo *',width=430)
            desc=textinput('Descrizione',width=430)
            selected={'id':None,'confirm':False}
            notice=ft.Text(color=ft.Colors.RED_700)
            btn_delete=ft.OutlinedButton('Elimina selezionato',disabled=True)
            def reset(e=None):
                selected.update(id=None,confirm=False)
                nome.value='';desc.value='';notice.value=''
                btn_delete.disabled=True;btn_delete.text='Elimina selezionato';page.update()
            def choose(item):
                selected.update(id=item['id'],confirm=False)
                nome.value=item['nome'];desc.value=item['descrizione'] or ''
                notice.value='Modifica del luogo selezionato.'
                btn_delete.disabled=not can_edit;btn_delete.text='Elimina selezionato'
                page.update()
            def reload():
                records.controls.clear()
                for item in m_luoghi(uid):
                    records.controls.append(ft.Row([
                        ft.TextButton(item['nome'],on_click=lambda e,x=item:choose(x)),
                        ft.Text((item['descrizione'] or '')[:75],size=12,expand=True)]))
                if not records.controls:records.controls.append(ft.Text('Nessun luogo registrato.'))
            def save(e):
                try:
                    if selected['id']:
                        if not can_edit:raise PermissionError('Modifica non autorizzata.')
                        modifica_luogo(uid,username,selected['id'],nome.value,desc.value)
                    else:
                        if not can_create:raise PermissionError('Inserimento non autorizzato.')
                        salva_luogo(uid,username,nome.value,desc.value)
                    reset();reload();refresh();notice.value='Salvataggio effettuato.';page.update()
                except Exception as exc:notice.value=str(exc);page.update()
            def delete(e):
                if not selected['id'] or not can_edit:return
                if not selected['confirm']:
                    selected['confirm']=True;btn_delete.text='Conferma eliminazione';notice.value='Premere nuovamente per eliminare il luogo selezionato.';page.update();return
                try:
                    elimina_luogo(uid,username,selected['id'])
                    reset();reload();refresh();notice.value='Luogo eliminato.';page.update()
                except Exception as exc:selected['confirm']=False;btn_delete.text='Elimina selezionato';notice.value=str(exc);page.update()
            btn_delete.on_click=delete
            reload()
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Gestione luoghi di mercato'),
                content=ft.Column([ft.Text('Luoghi registrati',weight=ft.FontWeight.BOLD),records,
                    ft.Divider(),ft.Text('Inserimento / modifica',weight=ft.FontWeight.BOLD),nome,desc,notice,
                    ft.Row([ft.OutlinedButton('Nuovo',on_click=reset),
                            ft.Button('Salva',on_click=save,disabled=not(can_create or can_edit)),btn_delete],wrap=True)],
                    width=620,height=520,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Chiudi',on_click=lambda e:page.pop_dialog())])
            page.show_dialog(dlg)

        def gestisci_giornate(e=None):
            places=m_luoghi(uid)
            if not places:notify('Inserire prima un luogo di mercato.',True);return
            records=ft.Column(spacing=3)
            place=dropdown('Luogo',[(x['id'],x['nome']) for x in places],places[0]['id'],390)
            weekday=dropdown('Giorno settimanale',list(enumerate(GIORNI)),0,250)
            selected={'id':None,'confirm':False}
            notice=ft.Text(color=ft.Colors.RED_700)
            btn_delete=ft.OutlinedButton('Elimina selezionata',disabled=True)
            def reset(e=None):
                selected.update(id=None,confirm=False);place.value=str(places[0]['id']);weekday.value='0'
                btn_delete.disabled=True;btn_delete.text='Elimina selezionata';notice.value='';page.update()
            def choose(item):
                selected.update(id=item['id'],confirm=False)
                place.value=str(item['luogo_id']);weekday.value=str(item['giorno'])
                btn_delete.disabled=not can_edit;btn_delete.text='Elimina selezionata';notice.value='';page.update()
            def reload():
                records.controls.clear()
                for item in m_giornate(uid):
                    records.controls.append(ft.Row([ft.TextButton(item['descrizione'],on_click=lambda e,x=item:choose(x))]))
                if not records.controls:records.controls.append(ft.Text('Nessuna giornata configurata.'))
            def save(e):
                try:
                    if selected['id']:
                        if not can_edit:raise PermissionError('Modifica non autorizzata.')
                        modifica_giornata(uid,username,selected['id'],place.value,weekday.value)
                    else:
                        if not can_create:raise PermissionError('Inserimento non autorizzato.')
                        salva_giornata(uid,username,place.value,weekday.value)
                    reset();reload();refresh();notice.value='Salvataggio effettuato.';page.update()
                except Exception as exc:notice.value=str(exc);page.update()
            def delete(e):
                if not selected['id'] or not can_edit:return
                if not selected['confirm']:
                    selected['confirm']=True;btn_delete.text='Conferma eliminazione';notice.value='Premere nuovamente per eliminare la giornata.';page.update();return
                try:
                    elimina_giornata(uid,username,selected['id'])
                    reset();reload();refresh();notice.value='Giornata eliminata.';page.update()
                except Exception as exc:selected['confirm']=False;btn_delete.text='Elimina selezionata';notice.value=str(exc);page.update()
            btn_delete.on_click=delete;reload()
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Gestione giornate di mercato'),
                content=ft.Column([ft.Text('Giornate registrate',weight=ft.FontWeight.BOLD),records,
                    ft.Divider(),ft.Text('Inserimento / modifica',weight=ft.FontWeight.BOLD),place,weekday,notice,
                    ft.Row([ft.OutlinedButton('Nuova',on_click=reset),
                            ft.Button('Salva',on_click=save,disabled=not(can_create or can_edit)),btn_delete],wrap=True)],
                    width=580,height=520,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Chiudi',on_click=lambda e:page.pop_dialog())])
            page.show_dialog(dlg)
        def edit_ditta(pk=None):
            d=m_dettaglio(uid,pk) if pk else {}
            nome=textinput('Denominazione *',d.get('denominazione',''),480)
            stato=dropdown('Stato anagrafico',[(x,x) for x in STATI],d.get('stato','Attivo'),220)
            notes=textinput('Note',d.get('note',''),480)
            controls=[nome,stato,notes]
            if pk:
                ass=d['assegnazioni']
                controls.append(ft.Text('Assegnazioni: '+(' | '.join(
                    f"{a['luogo']} {a['giorno'].lower()} (posto {a['posto']})" for a in ass) or 'nessuna')))
                controls.append(ft.Text('Per aggiungere un posto o un provvedimento usare i pulsanti nella riga della ditta.',size=12))
            dialog('Scheda ditta' if pk else 'Nuova ditta',controls,
                lambda:salva_ditta(uid,username,nome.value,stato.value,notes.value,pk))
        def gestisci_assegnazioni(pk):
            sessions=m_giornate(uid)
            if not sessions:notify('Configurare prima una giornata di mercato.',True);return
            d=m_dettaglio(uid,pk)
            rows=ft.Column(spacing=2)
            gd=dropdown('Giornata mercato',[(x['id'],x['descrizione']) for x in sessions],sessions[0]['id'],445)
            posto=textinput('Numero posto *',width=170)
            ordine=textinput('Ordine rilevazione',0,170)
            dal=date_field('Valida dal','');al=date_field('Valida al','')
            selected={'id':None,'confirm':False}
            notice=ft.Text(color=ft.Colors.RED_700)
            btn_delete=ft.OutlinedButton('Elimina selezionata',disabled=True)
            def reset(e=None):
                selected.update(id=None,confirm=False);gd.value=str(sessions[0]['id'])
                posto.value='';ordine.value='0';dal.value='';al.value=''
                btn_delete.disabled=True;btn_delete.text='Elimina selezionata';notice.value='';page.update()
            def choose(item):
                selected.update(id=item['id'],confirm=False)
                gd.value=str(item['giornata_id']);posto.value=item['posto'];ordine.value=str(item['ordine'])
                dal.value=item['dal'].strftime('%d/%m/%Y') if item['dal'] else ''
                al.value=item['al'].strftime('%d/%m/%Y') if item['al'] else ''
                btn_delete.disabled=not can_edit;btn_delete.text='Elimina selezionata';notice.value='';page.update()
            def reload():
                rows.controls.clear()
                for item in m_dettaglio(uid,pk)['assegnazioni']:
                    label=f"{item['luogo']} {item['giorno'].lower()} (posto {item['posto']})"
                    period=(f" — {item['dal']:%d/%m/%Y}" if item['dal'] else '')+(f" / {item['al']:%d/%m/%Y}" if item['al'] else '')
                    rows.controls.append(ft.Row([ft.TextButton(label,on_click=lambda e,x=item:choose(x)),
                         ft.Text(f"Ord. {item['ordine']}{period}",size=11,expand=True)]))
                if not rows.controls:rows.controls.append(ft.Text('Nessuna assegnazione registrata.'))
            def save(e):
                try:
                    if not can_edit:raise PermissionError('Modifica non autorizzata.')
                    if selected['id']:
                        modifica_assegnazione(uid,username,selected['id'],gd.value,posto.value,ordine.value,dal.value,al.value)
                    else:
                        salva_assegnazione(uid,username,pk,gd.value,posto.value,ordine.value,dal.value,al.value)
                    reset();reload();refresh();notice.value='Assegnazione salvata.';page.update()
                except Exception as exc:notice.value=str(exc);page.update()
            def delete(e):
                if not selected['id'] or not can_edit:return
                if not selected['confirm']:
                    selected['confirm']=True;btn_delete.text='Conferma eliminazione';notice.value='Premere nuovamente per eliminare l’assegnazione.';page.update();return
                try:
                    elimina_assegnazione(uid,username,selected['id'])
                    reset();reload();refresh();notice.value='Assegnazione eliminata.';page.update()
                except Exception as exc:selected['confirm']=False;btn_delete.text='Elimina selezionata';notice.value=str(exc);page.update()
            btn_delete.on_click=delete;reload()
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Assegnazioni — '+d['denominazione']),
                content=ft.Column([ft.Text('Assegnazioni registrate',weight=ft.FontWeight.BOLD),rows,
                    ft.Divider(),ft.Text('Inserimento / modifica',weight=ft.FontWeight.BOLD),gd,
                    ft.Row([posto,ordine]),ft.Row([dal,al],wrap=True),notice,
                    ft.Row([ft.OutlinedButton('Nuova',on_click=reset),
                            ft.Button('Salva',on_click=save,disabled=not can_edit),btn_delete],wrap=True)],
                    width=650,height=560,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Chiudi',on_click=lambda e:page.pop_dialog())])
            page.show_dialog(dlg)
        def edit_provvedimento(pk):
            d=m_dettaglio(uid,pk)
            ass=d['assegnazioni']
            if not ass:notify('Nessuna assegnazione disponibile.',True);return
            checks={a['id']:ft.Checkbox(label=f"{a['luogo']} {a['giorno']} — posto {a['posto']}") for a in ass}
            tipo=dropdown('Tipo provvedimento',[(x,x) for x in TIPI],'Sospensione')
            numero=textinput('Numero atto',width=220);atto=date_field('Data atto')
            dal=date_field('Efficace dal');al=date_field('Efficace al','')
            motivo=textinput('Motivazione',width=450)
            old=provvedimenti(uid,pk)
            notes=ft.Column([ft.Text(f"{p['tipo']} n. {p['numero_atto']} — {p['dal']:%d/%m/%Y}"
                         +(f" – {p['al']:%d/%m/%Y}" if p['al'] else '')) for p in old])
            dialog('Provvedimenti — '+d['denominazione'],[
                ft.Text('Selezionare una o più assegnazioni interessate'),*checks.values(),
                tipo,numero,atto,dal,al,motivo,ft.Text('Provvedimenti già presenti:'),notes],
                lambda:salva_provvedimento(uid,username,[aid for aid,c in checks.items() if c.value],
                    tipo.value,numero.value,atto.value,dal.value,al.value,motivo.value),height=590)
        def open_presence(e=None, preset=None):
            sessions=m_giornate(uid)
            if not sessions:notify('Configurare prima luoghi e giornate.',True);return
            day=date_field('Data rilevazione',preset['giorno'].strftime('%d/%m/%Y') if preset else today)
            w=ft.Text(week(day.value),weight=ft.FontWeight.BOLD)
            gd=dropdown('Luogo e giornata',[(x['id'],x['descrizione']) for x in sessions],
                        preset['giornata_id'] if preset else sessions[0]['id'],440)
            status=ft.Text();checks={};excluded=ft.Column();listbox=ft.Column(spacing=3)
            ricerca_ditta=ft.TextField(label='Cerca ditta (min. 3 caratteri)',prefix_icon=ft.Icons.SEARCH,width=390)
            righe_ditte=[];ordine_ditte=[]
            conteggio_ricerca=ft.Text(size=12,color=ft.Colors.GREY_700)
            notes=textinput('Note rilevazione',width=520)
            reason=textinput('Motivo rettifica (se rilevazione confermata)',width=520)
            current={'ids':set(),'key':None,'state':'Nuova'}
            def filtra_ditte(ev=None):
                # La ricerca cambia solo la visualizzazione; le spunte nascoste
                # continuano a far parte della rilevazione completa.
                termine=(ricerca_ditta.value or '').strip().casefold()
                visibili=[c for nome,c in righe_ditte if len(termine)<3 or termine in nome]
                listbox.controls[:]=visibili
                conteggio_ricerca.value=(f'{len(visibili)} di {len(righe_ditte)} ditte visualizzate'
                                       if len(termine)>=3 else f'{len(righe_ditte)} ditte in elenco')
                if not righe_ditte:
                    listbox.controls.append(ft.Text('Nessuna ditta tenuta alla presenza in questa giornata.'))
                elif len(termine)>=3 and not visibili:
                    listbox.controls.append(ft.Text('Nessuna ditta corrisponde alla ricerca.'))
                page.update()
            date_warning=ft.Text(color=ft.Colors.RED_700, size=12)
            def load(ev=None):
                # Prima di aggiornare l'elenco controlla i campi. In caso di
                # data parziale mantiene intatte le caselle e le spunte.
                parsed=valida_data_in_linea(day.value,date_warning)
                w.value=week(day.value)
                if parsed is None:
                    page.update()
                    return
                try:
                    if gd.value is None:
                        raise ValueError('Selezionare una giornata di mercato.')
                    snapshot=anteprima(uid,day.value,gd.value)
                except (ValueError, TypeError) as exc:
                    date_warning.value=str(exc)
                    status.value='Verifica data e luogo prima di proseguire.'
                    page.update()
                    return
                except Exception as exc:
                    traceback.print_exc()
                    date_warning.value='Impossibile aggiornare la rilevazione: '+str(exc)
                    page.update()
                    return
                date_warning.value=''
                checks.clear();righe_ditte.clear();listbox.controls.clear();excluded.controls.clear();current['key']=None
                try:
                    current['ids']={d['assegnazione_id'] for d in snapshot['ditte']}
                    current['key']=(parsed,int(gd.value))
                    current['state']=snapshot['stato']
                    for d in sorted(snapshot['ditte'], key=lambda x:(x.get('ordine',0),str(x.get('posto','')),x['denominazione'])):
                        c=ft.Checkbox(label=f"{d['denominazione']} — posto {d['posto']}",
                                      value=d['esito']=='PRESENTE')
                        checks[d['assegnazione_id']]=c
                        righe_ditte.append((d['denominazione'].casefold(),c))
                    for d in snapshot['esclusi']:
                        excluded.controls.append(ft.Text(f"{d['denominazione']} — posto {d['posto']}: {d['stato']}",size=12))
                    notes.value=snapshot.get('note','')
                    status.value=f"{snapshot['stato']} — {len(checks)} ditte da rilevare; {len(snapshot['esclusi'])} escluse"
                    filtra_ditte()
                except Exception as exc:
                    traceback.print_exc()
                    status.value='Impossibile mostrare l’elenco: '+str(exc)
                    current['ids']=set()
                page.update()
            def avvisa_data_presenze(e=None):
                if valida_data_in_linea(day.value,date_warning,segnalazione=True) is None:
                    page.update()
            def toggle(value):
                for c in checks.values():c.value=value
                page.update()
            def save(confirm=False):
                try:
                    if not current['ids'] or current['key']!=(data_input(day.value),int(gd.value)):
                        raise ValueError('Selezionare una giornata valida con ditte assegnate.')
                    present={aid for aid,c in checks.items() if c.value}
                    a,b=salva_rilevazione(uid,username,day.value,gd.value,present,current['ids'],
                        conferma=confirm,motivo=reason.value, note=notes.value)
                    # La maschera di rilevazione viene chiusa solo dopo il salvataggio riuscito.
                    page.pop_dialog()
                    if confirm:
                        giornata=next((x for x in sessions if x['id']==int(gd.value)),None)
                        luogo=(giornata['descrizione'] if giornata else str(gd.value))
                        giorno=data_input(day.value)
                        riepilogo=ft.AlertDialog(
                            modal=True,
                            title=ft.Text('Rilevazione confermata'),
                            content=ft.Column([
                                ft.Text('Rilevazione salvata definitivamente.',
                                        color=ft.Colors.GREEN_700,weight=ft.FontWeight.BOLD),
                                ft.Text(f'Data: {giorno.strftime("%d/%m/%Y")} — {week(day.value)}'),
                                ft.Text(f'Luogo e giornata: {luogo}'),
                                ft.Divider(),
                                ft.Text(f'Ditte presenti: {a}',weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN_700),
                                ft.Text(f'Ditte assenti: {b}',weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.RED_700),
                                ft.Text(f'Totale ditte rilevate: {a+b}',
                                        weight=ft.FontWeight.BOLD),
                            ],tight=True,width=440),
                            actions=[ft.Button('OK',on_click=lambda e:page.pop_dialog())],
                        )
                        page.show_dialog(riepilogo)
                    else:
                        notify(f'Rilevazione salvata in bozza: {a} presenti, {b} assenti.')
                except Exception as exc:status.value=str(exc);page.update()
            async def esporta_elenco_mobile(ev):
                try:
                    snapshot=anteprima(uid,day.value,gd.value)
                    if snapshot['stato']=='Confermata':
                        raise ValueError('Non si può esportare una rilevazione confermata.')
                    if not snapshot['ditte']:
                        raise ValueError('Nessuna ditta da rilevare.')
                    entry=next(x for x in sessions if x['id']==int(gd.value))
                    payload=crea_elenco(data_input(day.value).isoformat(),int(gd.value),
                                        entry['luogo'],entry['descrizione'],snapshot['ditte'])
                    target=await ft.FilePicker().save_file(
                        file_name=f"sipa_lista_{payload['data']}_{payload['elenco_id'][:8]}.json",
                        file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=['json'],
                        src_bytes=serialize(payload))
                    if target:notify('Elenco esportato per SIPA Presenze Android.')
                except Exception as exc:
                    status.value='Errore esportazione: '+str(exc);page.update()
            day.on_change=load;day.on_blur=avvisa_data_presenze
            gd.on_change=load;gd.on_select=load
            ricerca_ditta.on_change=filtra_ditte
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Rilevazione presenze'),
                content=ft.Column([ft.Row([day,gd],wrap=True),w,date_warning,status,
                    ft.Row([ft.TextButton('Tutte presenti',on_click=lambda e:toggle(True)),
                            ft.TextButton('Nessuna presente',on_click=lambda e:toggle(False))]),
                    ft.Text('Spuntare le ditte PRESENTI; le altre risulteranno ASSENTI dopo conferma.'),
                    ricerca_ditta,conteggio_ricerca,listbox,ft.Text('Escluse (sospese, cessate, fuori validità):'),excluded,notes,reason],
                    width=650,height=580,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),
                    ft.OutlinedButton('Esporta elenco Android',on_click=esporta_elenco_mobile),
                    ft.OutlinedButton('Salva bozza',on_click=lambda e:save(False)),
                    ft.Button('Conferma rilevazione',on_click=lambda e:save(True))])
            page.show_dialog(dlg);load()
        def gestisci_bozze(e=None):
            """Apri, importa o elimina rilevazioni salvate ma non ancora confermate."""
            async def importa_mobile(ev):
                try:
                    picked=await ft.FilePicker().pick_files(
                        allow_multiple=False,with_data=True,
                        file_type=ft.FilePickerFileType.CUSTOM,allowed_extensions=['json'])
                    if not picked:return
                    f=picked[0]
                    raw=f.bytes if f.bytes else Path(f.path).read_bytes()
                    imported=leggi_esiti(raw)
                    elenco=imported['elenco']
                    preview=ft.Text(
                        f"{elenco['data']} — {elenco['giornata']}\n"
                        f"Ditte: {len(elenco['ditte'])}, presenti: {len(imported['presenti'])}\n"
                        'Verificare data e mercato. Verrà creata/aggiornata una BOZZA, mai confermata.')
                    error=ft.Text(color=ft.Colors.RED_700)
                    def confirm_import(ev):
                        try:
                            n=importa_esiti_mobile(uid,username,imported)
                            page.pop_dialog()
                            load()
                            notify(f'Bozza importata: {n} presenze. Aprirla e verificare prima della conferma.')
                        except Exception as exc:error.value=str(exc);page.update()
                    dlg2=ft.AlertDialog(modal=True,title=ft.Text('Importa bozza da Android'),
                        content=ft.Column([preview,error],tight=True,width=470),
                        actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),
                                 ft.Button('Importa come bozza',on_click=confirm_import)])
                    page.show_dialog(dlg2)
                except Exception as exc:info.value='Importazione: '+str(exc);page.update()
            records=ft.Column(spacing=7)
            info=ft.Text(color=ft.Colors.RED_700)
            def load():
                records.controls.clear()
                try:
                    items=bozze_rilevazioni(uid)
                    if not items:
                        records.controls.append(ft.Text('Nessuna bozza presente.'))
                    for item in items:
                        def reopen(ev, item=item):
                            page.pop_dialog()
                            open_presence(preset=item)
                        def request_delete(ev, item=item):
                            def confirm_delete(ev):
                                try:
                                    elimina_bozza(uid,username,item['id'])
                                    page.pop_dialog()
                                    load()
                                    notify('Bozza eliminata. La rilevazione potrà essere ricreata.')
                                except Exception as exc:
                                    error.value=str(exc)
                                    page.update()
                            error=ft.Text(color=ft.Colors.RED_700)
                            confirm=ft.AlertDialog(modal=True,title=ft.Text('Eliminare la bozza?'),
                                content=ft.Column([
                                    ft.Text(f"{item['giorno']:%d/%m/%Y} — {item['luogo']} ({item['giorno_settimana']})"),
                                    ft.Text('Verranno eliminati anche gli esiti provvisori. Questa operazione non riguarda le rilevazioni confermate.'),
                                    error],tight=True,width=440),
                                actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),
                                         ft.Button('Conferma eliminazione',on_click=confirm_delete)])
                            page.show_dialog(confirm)
                        label=(f"{item['giorno']:%d/%m/%Y} — {item['luogo']} ({item['giorno_settimana']})"
                               f" — {item['presenti']} presenti, {item['assenti']} assenti")
                        actions=[ft.OutlinedButton('Apri',on_click=reopen)]
                        if can_presence:
                            actions.append(ft.TextButton('Elimina',on_click=request_delete))
                        records.controls.append(ft.Column([
                            ft.Text(label,weight=ft.FontWeight.W_500),
                            ft.Text(f"Operatore: {item['operatore']}",size=11),
                            ft.Row(actions,wrap=True),ft.Divider(height=5)
                        ],spacing=2))
                    info.value=f'{len(items)} bozze trovate.'
                except Exception as exc:info.value=str(exc)
                page.update()
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Gestione bozze delle rilevazioni'),
                content=ft.Column([info,records],width=620,height=500,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Chiudi',on_click=lambda e:page.pop_dialog()),
                         ft.OutlinedButton('Importa bozza Android',on_click=importa_mobile,disabled=not can_presence),
                         ft.OutlinedButton('Aggiorna',on_click=lambda e:load())])
            page.show_dialog(dlg)
            load()

        def print_list(e=None):
            try:
                records=m_elenco(uid,search.value, selected_places or None,state.value)
                notify('PDF creato: '+str(stampa_elenco(records,search.value,selected_places,state.value)))
            except Exception as exc:fail(exc)
        def print_accertamento(e=None):
            day=date_field('Data accertamento');w=ft.Text(week(day.value))
            places=m_luoghi(uid)
            place=dropdown('Luogo',[(0,'Tutti i luoghi')]+[(p['id'],p['nome']) for p in places],0,440)
            error=ft.Text(color=ft.Colors.RED_700)
            date_warning=ft.Text(color=ft.Colors.RED_700,size=12)
            def update_day(e=None):
                w.value=week(day.value)
                valida_data_in_linea(day.value,date_warning)
                page.update()
            def warn_day(e=None):
                if valida_data_in_linea(day.value,date_warning,segnalazione=True) is None:
                    page.update()
            day.on_change=update_day
            day.on_blur=warn_day
            def export(format):
                try:
                    dt=data_input(day.value)
                    rows=accertamenti(uid,day.value,int(place.value or 0) or None)
                    if format=='pdf':
                        target=stampa_accertamento(rows,dt)
                        message='Accertamento PDF: '
                    else:
                        from stampa_assenze_word import stampa_comunicazione_assenze
                        target=stampa_comunicazione_assenze(rows,dt)
                        message='Comunicazione Word: '
                    page.pop_dialog()
                    notify(message+str(target))
                except Exception as exc:
                    error.value=str(exc);page.update()
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Assenze per data e luogo'),
                content=ft.Column([day,w,date_warning,place,error],width=550,height=250,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),
                    ft.OutlinedButton('Esporta Word',icon=ft.Icons.DESCRIPTION,
                        on_click=lambda e:export('word')),
                    ft.Button('Stampa PDF',icon=ft.Icons.PRINT,
                        on_click=lambda e:export('pdf'))])
            page.show_dialog(dlg)
        def print_annual(pk=None):
            try:
                raw_year=(year.value or '').strip()
                if len(raw_year)!=4 or not raw_year.isdigit() or not 1900 <= int(raw_year) <= 2100:
                    raise ValueError('Inserire un anno valido a quattro cifre (es. 2026).')
                value=int(raw_year)
                if pk:
                    d=m_dettaglio(uid,pk);rows=assenze_anno(uid,value,pk)
                    path=stampa_assenze_ditta(d['denominazione'],value,rows)
                else:
                    records=m_elenco(uid,search.value,selected_places or None,'Tutti')
                    all_rows=assenze_anno(uid,value)
                    ids={d['id'] for d in records}
                    path=stampa_assenze_generale(records,value,[r for r in all_rows if r['ditta_id'] in ids])
                notify('PDF creato: '+str(path))
            except Exception as exc:fail(exc)
        def select_places(e=None):
            places=m_luoghi(uid)
            checks={p['id']:ft.Checkbox(label=p['nome'],value=(not selected_places or p['id'] in selected_places)) for p in places}
            def apply():
                selected_places.clear();selected_places.update(k for k,c in checks.items() if c.value)
            dialog('Filtra luoghi',list(checks.values()) or [ft.Text('Nessun luogo')],apply,
                   button='Applica',height=310)
        def refresh(e=None):
            try:
                q=(search.value or '').strip()
                if q and len(q)<3:
                    summary.value='Ricerca incompleta: inserire almeno 3 caratteri oppure svuotare il campo.'
                    page.update();return
                records=m_elenco(uid,q,selected_places or None,state.value)
                summary.value=f'{len(records)} ditte trovate'
                result.controls.clear()
                for d in records:
                    buttons=[ft.IconButton(ft.Icons.EDIT_OUTLINED,tooltip='Scheda ditta',
                              on_click=lambda e,pk=d['id']:edit_ditta(pk))]
                    if can_edit:
                        buttons.extend([ft.IconButton(ft.Icons.ADD_LOCATION_ALT_OUTLINED,tooltip='Gestisci assegnazioni',
                                         on_click=lambda e,pk=d['id']:gestisci_assegnazioni(pk)),
                                        ft.IconButton(ft.Icons.GAVEL,tooltip='Provvedimenti',
                                         on_click=lambda e,pk=d['id']:edit_provvedimento(pk))])
                    if can_print:buttons.append(ft.IconButton(ft.Icons.EVENT_NOTE,tooltip='Assenze annuali ditta',
                                         on_click=lambda e,pk=d['id']:print_annual(pk)))
                    color={'Attivo':ft.Colors.GREEN_700,'Sospeso':ft.Colors.AMBER_800,'Cessato':ft.Colors.RED_700}[d['stato']]
                    result.controls.append(ft.Container(bgcolor=ft.Colors.BLUE_GREY_50,border_radius=8,padding=10,
                        content=ft.Row([ft.Column([ft.Text(d['denominazione'],weight=ft.FontWeight.BOLD),
                            ft.Text(d['luoghi_posti'] or 'Nessuna assegnazione',size=12)],expand=True,spacing=3),
                            ft.Text(d['stato'],color=color,width=75),*buttons])))
                if not records:result.controls.append(ft.Text('Nessuna ditta registrata o corrispondente ai filtri.'))
                page.update()
            except (ValueError, TypeError) as exc:
                summary.value='Filtro non valido: '+str(exc);page.update()
            except Exception as exc:
                traceback.print_exc()
                summary.value='Impossibile aggiornare l’elenco: '+str(exc);page.update()
        search.on_change=refresh;state.on_change=refresh;state.on_select=refresh
        buttons=[ft.OutlinedButton('Luoghi (filtro)',on_click=select_places),
                 ft.OutlinedButton('Aggiorna',icon=ft.Icons.REFRESH,on_click=refresh)]
        if can_create:
            buttons.append(ft.Button('Nuova ditta',icon=ft.Icons.ADD,on_click=lambda e:edit_ditta()))
        if can_create or can_edit:
            buttons.extend([ft.OutlinedButton('Gestisci luoghi',on_click=gestisci_luoghi),
                            ft.OutlinedButton('Gestisci giornate',on_click=gestisci_giornate)])
        if can_presence:
            buttons.append(ft.Button('Rileva presenze',icon=ft.Icons.CHECKLIST,on_click=open_presence))
        if has_permission(uid,'mercatino.read'):
            buttons.append(ft.OutlinedButton('Gestisci bozze',icon=ft.Icons.FOLDER_OPEN,on_click=gestisci_bozze))
        if can_print:buttons.extend([ft.OutlinedButton('Elenco PDF',icon=ft.Icons.PRINT,on_click=print_list),
            ft.OutlinedButton('Accertamento assenze per data / luogo',on_click=print_accertamento),
            ft.OutlinedButton('Prospetto annuale',on_click=lambda e:print_annual())])
        content.controls.extend([ft.Text('Mercatino — ditte e rilevazioni',size=18,weight=ft.FontWeight.W_600),
            ft.Row([search,state,year],wrap=True),ft.Row(buttons,wrap=True),summary,result])
        refresh()

    def render_admin(content):
        if not has_permission(user['id'], 'users.manage'):
            return
        rows = ft.Column(spacing=5)
        events = ft.Column(spacing=5)

        def user_dialog(existing=None, mode='create'):
            username = ft.TextField(label='Nome utente', value=existing['username'] if existing else '', disabled=existing is not None)
            password = ft.TextField(label='Password temporanea (min. 12 caratteri)', password=True, can_reveal_password=True)
            role = ft.Dropdown(label='Ruolo', value=existing['role'] if existing else 'operatore',
                options=[ft.dropdown.Option('admin', 'Amministratore'), ft.dropdown.Option('operatore', 'Operatore'), ft.dropdown.Option('responsabile', 'Responsabile'), ft.dropdown.Option('consultazione', 'Consultazione')])
            active = ft.Checkbox(label='Account attivo', value=existing['active'] if existing else True)
            message = ft.Text(color=ft.Colors.RED_700)
            fields = [username, password, role, active, message] if mode == 'create' else ([password, message] if mode == 'reset' else [role, active, message])
            dlg = ft.AlertDialog(modal=True, title=ft.Text({'create':'Nuovo utente','edit':'Modifica utente','reset':'Reimposta password'}[mode]),
                content=ft.Column(fields, tight=True, width=390), actions=[])
            def save(e):
                try:
                    if mode == 'create':
                        create_user(user['id'], username.value, password.value, role.value)
                    elif mode == 'edit':
                        update_user(user['id'], existing['id'], role.value, active.value)
                    else:
                        reset_password(user['id'], existing['id'], password.value)
                    page.pop_dialog()
                    refresh()
                    notify('Operazione completata.')
                except (ValueError, PermissionError) as exc:
                    message.value = str(exc)
                    page.update()
            dlg.actions = [ft.TextButton('Annulla', on_click=lambda e: page.pop_dialog()), ft.Button('Salva', on_click=save)]
            page.show_dialog(dlg)

        def refresh():
            rows.controls.clear()
            for u in list_users():
                rows.controls.append(ft.Container(padding=10, border_radius=8, bgcolor=ft.Colors.BLUE_GREY_50,
                    content=ft.Row([
                        ft.Icon(ft.Icons.PERSON_OUTLINE),
                        ft.Column([ft.Text(u['username'], weight=ft.FontWeight.BOLD),
                                   ft.Text(f"{u['role']} • {'attivo' if u['active'] else 'disattivato'}", size=12)], expand=True, spacing=2),
                        ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip='Modifica ruolo/stato', on_click=lambda e, item=u: user_dialog(item, 'edit')),
                        ft.IconButton(icon=ft.Icons.LOCK_RESET, tooltip='Reimposta password', on_click=lambda e, item=u: user_dialog(item, 'reset')),
                    ])))
            events.controls.clear()
            for ev in list_events(40):
                events.controls.append(ft.Text(f"{ev['time']}   |   {ev['actor']}   |   {ev['action']}   |   {ev['target']}", size=12, selectable=True))
            page.update()

        def permission_dialog(e=None):
            from database import PERMISSIONS
            current = role_permissions()
            selected_role = ft.Dropdown(
                label='Ruolo', value='operatore', width=270,
                options=[ft.dropdown.Option(r) for r in ('responsabile', 'operatore', 'consultazione')],
            )
            # Righe = aree funzionali; colonne = tipo di autorizzazione.
            # Le celle non applicabili rimangono vuote.
            areas = [
                ('Dashboard', 'dashboard'),
                ('Attività economiche', 'attivita'),
                ('Verbali amministrativi', 'verbali'),
                ('Accertamenti', 'accertamenti'),
                ('Documenti', 'documenti'),
                ('Utenti', 'users'),
                ('Permessi', 'permissions'),
                ('Audit', 'audit'),
                ('Backup', 'backup'),
            ]
            actions = [
                ('read', 'Consulta'), ('view', 'Visualizza'),
                ('create', 'Inserisci'), ('update', 'Modifica'),
                ('void', 'Annulla'), ('export', 'Esporta'),
                ('manage', 'Gestisci'),
            ]
            message = ft.Text(color=ft.Colors.RED_700)
            checks = {}
            # Ricrea la tabella ad ogni selezione: i controlli vengono
            # rimontati con i valori del ruolo scelto, senza stato residuo.
            table_holder = ft.Column()

            def build_table(role):
                checks.clear()
                allowed = set(current.get(role, []))
                table_rows = []
                for area_label, prefix in areas:
                    cells = [ft.DataCell(ft.Text(area_label, size=12))]
                    for action, _ in actions:
                        code = f'{prefix}.{action}'
                        if code in PERMISSIONS:
                            control = ft.Checkbox(
                                value=(code in allowed),
                                tooltip=f'{code} — {PERMISSIONS[code]}',
                            )
                            checks[code] = control
                            cells.append(ft.DataCell(control))
                        else:
                            cells.append(ft.DataCell(ft.Text('—', color=ft.Colors.GREY_400)))
                    table_rows.append(ft.DataRow(cells=cells))
                return ft.DataTable(
                    columns=[ft.DataColumn(ft.Text('Sezione'))] + [
                        ft.DataColumn(ft.Text(label, size=11)) for _, label in actions
                    ],
                    rows=table_rows,
                    column_spacing=13,
                    horizontal_margin=12,
                    data_row_min_height=44,
                    data_row_max_height=44,
                )

            def load(e=None):
                # Nelle versioni recenti di Flet la selezione del Dropdown
                # viene notificata con on_select (non soltanto on_change).
                role = getattr(getattr(e, 'control', None), 'value', None) or selected_role.value
                if role not in current:
                    return
                selected_role.value = role
                table_holder.controls = [build_table(role)]
                message.value = ''
                page.update()

            def save(e):
                try:
                    codes = [code for code, control in checks.items() if control.value]
                    set_role_permissions(user['id'], selected_role.value, codes)
                    current[selected_role.value] = codes
                    page.pop_dialog()
                    notify('Permessi aggiornati per il ruolo ' + selected_role.value + '.')
                except (ValueError, PermissionError) as exc:
                    message.value = str(exc)
                    page.update()

            selected_role.on_select = load
            selected_role.on_change = load  # Compatibilità con versioni precedenti
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text('Permessi granulari per ruolo'),
                content=ft.Column(
                    [
                        selected_role,
                        ft.Text('Seleziona un ruolo: la tabella mostra i permessi assegnati.', size=12),
                        ft.Row([table_holder], scroll=ft.ScrollMode.AUTO),
                        message,
                    ],
                    tight=True, width=850, scroll=ft.ScrollMode.AUTO,
                ),
                actions=[
                    ft.TextButton('Annulla', on_click=lambda e: page.pop_dialog()),
                    ft.Button('Salva', on_click=save),
                ],
            )
            load()
            page.show_dialog(dlg)

        def export_directory_dialog(e=None):
            """Imposta la directory comune per stampe PDF e documenti Word."""
            from output_settings import get_output_directory, set_output_directory
            directory = ft.TextField(label='Cartella predefinita per PDF e documenti',
                                     value=str(get_output_directory()), width=490)
            error = ft.Text(color=ft.Colors.RED_700)
            async def browse(e):
                try:
                    selected = await ft.FilePicker().get_directory_path(
                        dialog_title='Seleziona cartella esportazioni SIPA')
                    if selected:
                        directory.value = str(selected)
                        page.update()
                except Exception as exc:
                    error.value = 'Selezione cartella non riuscita: ' + str(exc)
                    page.update()
            def save(e):
                try:
                    target = set_output_directory(directory.value)
                    page.pop_dialog()
                    notify('Cartella esportazioni impostata: ' + str(target))
                except Exception as exc:
                    error.value = str(exc)
                    page.update()
            dlg = ft.AlertDialog(modal=True, title=ft.Text('Destinazione stampe ed esportazioni'),
                content=ft.Column([
                    ft.Text('La cartella è utilizzata per PDF e documenti Word. Impostazione locale del PC; non modifica il database.', size=12),
                    ft.Row([directory, ft.IconButton(icon=ft.Icons.FOLDER_OPEN,
                            tooltip='Sfoglia cartelle', on_click=browse)]),error],
                    tight=True,width=590),
                actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),
                         ft.Button('Salva percorso',on_click=save)])
            page.show_dialog(dlg)

        # FilePicker desktop (Flet 0.80+): UI operations only; restore must be done offline.
        def backup_dialog(e=None):
            directory = ft.TextField(label='Cartella di destinazione', value=str(Path.home() / 'BackupSIPA'), width=500)
            message = ft.Text(color=ft.Colors.RED_700)
            dlg = ft.AlertDialog(modal=True, title=ft.Text('Crea backup SIPA'),
                content=ft.Column([ft.Text('Backup del motore corrente: SQLite (.db) o PostgreSQL (.sql). Include manifest e, se presente, chiave audit; esclude file esterni.'),directory,message],tight=True,width=540),actions=[])
            def save(e):
                try:
                    path=create_backup(directory.value)
                    page.pop_dialog()
                    notify('Backup creato: '+str(path))
                except Exception as exc:
                    message.value=str(exc)
                    page.update()
            dlg.actions=[ft.TextButton('Annulla',on_click=lambda e:page.pop_dialog()),ft.Button('Genera backup',on_click=save)]
            page.show_dialog(dlg)

        async def restore_picker(e=None):
            try:
                files = await ft.FilePicker().pick_files(allow_multiple=False, dialog_title='Seleziona backup SIPA (.db o .sql)',
                                                        file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['db', 'sql'])
                if not files: return
                path = files[0].path
                if not path:
                    notify('Il selettore non ha restituito un percorso locale.',True)
                    return
                report = inspect_backup(path)
                if str(path).lower().endswith('.sql'):
                    description = ('Backup PostgreSQL: '+str(report['file'])+'\n'
                        +'Revisione backup: '+str(report['schema_backup'])+'\n'
                        +'Revisione richiesta: '+str(report['schema_required'])+'\n'
                        +'Compatibile con la versione corrente: '+('Sì' if report['compatible'] else 'NO: necessario upgrade offline dopo il ripristino')+'\n'
                        +'Checksum SQL e chiave audit (se presente): verificati.\n'
                        +'Per PostgreSQL il confronto delle singole colonne non è disponibile; ripristino SOLO da terminale su database VUOTO.')
                    dlg=ft.AlertDialog(modal=True,title=ft.Text('Verifica backup PostgreSQL'),
                        content=ft.Column([ft.Text(description,selectable=True),ft.Text('Per il ripristino: chiudere tutti i client, predisporre un database PostgreSQL vuoto, controllare la configurazione e usare il comando riportato sotto.'),
                         ft.Text('python cli.py restore '+repr(path)+' --confirm \"RIPRISTINA SIPA\"',selectable=True)],
                         width=690,height=340,scroll=ft.ScrollMode.AUTO),
                        actions=[ft.TextButton('Chiudi',on_click=lambda e:page.pop_dialog())])
                    page.show_dialog(dlg)
                    return
                def lines(label, value):
                    return label+': '+(json.dumps(value,ensure_ascii=False) if value else 'nessuna')
                description='\n'.join([
                    'Backup: '+str(report['file']),
                    'Versione schema backup: '+report['schema_backup'],
                    'Versione schema attuale: '+report['schema_current'],
                    lines('Tabelle presenti solo nel backup',report['tables_only_backup']),
                    lines('Tabelle presenti solo nel database attuale',report['tables_only_current']),
                    lines('Colonne presenti solo nel backup',report['columns_only_backup']),
                    lines('Colonne presenti solo nel database attuale',report['columns_only_current']),
                    lines('Colonne con tipo differente',report['changed_column_types']),
                    'Chiave audit nel backup: '+('sì' if report['key_present'] else 'no'),
                ])
                dlg=ft.AlertDialog(modal=True,title=ft.Text('Anteprima ripristino – differenze di struttura'),
                    content=ft.Column([
                        ft.Text('Il ripristino sostituisce tutti i dati, non unisce i registri. Le differenze mostrate sono di STRUTTURA, non di contenuto.',weight=ft.FontWeight.BOLD),
                        ft.Text(description,selectable=True),
                        ft.Divider(),
                        ft.Text('Per sicurezza, il ripristino si esegue solo a SIPA chiuso tramite CLI. Archivia prima database e chiave correnti. Nessun dato è stato modificato.'),
                        ft.Text('1. Chiudi SIPA e tutti gli altri processi.\n2. Conserva sipa.db e .sipa_audit_key fuori dalla cartella.\n3. Esegui:',size=12),
                        ft.Text('python cli.py restore '+repr(path)+' --confirm "RIPRISTINA SIPA"',selectable=True,size=12),
                        ft.Text('4. Se la revisione è precedente, esegui python cli.py upgrade-db --backup-dir ~/BackupSIPA, poi verifica con db-version e riavvia SIPA.',size=12),
                    ],scroll=ft.ScrollMode.AUTO,height=470,width=690),
                    actions=[ft.TextButton('Chiudi anteprima',on_click=lambda e:page.pop_dialog())])
                page.show_dialog(dlg)
            except Exception as exc:
                notify('Impossibile analizzare il backup: '+str(exc),True)

        def database_dialog(e=None):
            c = read_settings()
            kind = ft.Dropdown(label='Motore database (fisso)', disabled=True, value=c.get('driver', 'sqlite'), width=240,
                options=[ft.dropdown.Option('sqlite', 'SQLite'), ft.dropdown.Option('postgresql', 'PostgreSQL')])
            path = ft.TextField(label='File SQLite (percorso assoluto)', value=c.get('sqlite_path', str(Path(__file__).parent / 'sipa.db')), width=550)
            host = ft.TextField(label='Host PostgreSQL', value=c.get('host', 'localhost'))
            port = ft.TextField(label='Porta', value=str(c.get('port', 5432)))
            dbname = ft.TextField(label='Nome database', value=c.get('database', 'sipa'))
            dbuser = ft.TextField(label='Utente PostgreSQL', value=c.get('username', 'sipa'))
            envname = ft.TextField(label='Variabile ambiente della password', value=c.get('password_env', 'SIPA_PG_PASSWORD'))
            ssl = ft.Dropdown(label='Sicurezza TLS', value=c.get('sslmode', 'require'), options=[ft.dropdown.Option(x) for x in ('disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full')])
            info = ft.Text('La password non viene salvata: impostare la variabile ambiente prima di avviare SIPA.', size=12)
            admin_user = ft.TextField(label='Amministratore del database di destinazione')
            admin_password = ft.TextField(label='Password amministratore del database di destinazione', password=True, can_reveal_password=True)
            audit_source = ft.TextField(label='Percorso chiave audit originale (se diversa da quella locale)', width=550)
            msg = ft.Text(color=ft.Colors.RED_700)
            fields = ft.Column(spacing=8, tight=True)
            def refresh_fields(e=None):
                value = getattr(getattr(e, 'control', None), 'value', None) or kind.value
                fields.controls = [path] if value == 'sqlite' else [host, port, dbname, dbuser, envname, ssl, info]
                page.update()
            kind.on_select = refresh_fields
            kind.on_change = refresh_fields
            def save(e):
                try:
                    from db_management import connect_existing
                    result = connect_existing({'driver': c['driver'], 'sqlite_path': path.value, 'host': host.value,
                                   'port': port.value, 'database': dbname.value, 'username': dbuser.value,
                                   'password_env': envname.value, 'sslmode': ssl.value},
                                   admin_user.value or '', admin_password.value or '', audit_source.value or None)
                    page.pop_dialog()
                    notify('Collegamento verificato (revisione '+str(result['revision'])+'). Configurazione salvata. Riavviare SIPA.')
                except Exception as exc:
                    msg.value = str(exc)
                    page.update()
            dlg = ft.AlertDialog(modal=True, title=ft.Text('Configurazione database'),
                content=ft.Column([kind, fields,admin_user,admin_password,audit_source,msg,
                    ft.Text('Verifica obbligatoria: connessione, tabelle, colonne, revisione ESATTA, utenti, credenziali e catena audit. Il database di destinazione non viene alterato. Si salva solo la configurazione locale; riavviare SIPA.', size=12)],
                    width=580, tight=True, scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Annulla', on_click=lambda e: page.pop_dialog()),
                         ft.Button('Salva configurazione', on_click=save)])
            refresh_fields()
            page.show_dialog(dlg)

        def upgrade_dialog(e=None):
            current = revision()
            message = (f'Revisione database: {current or "non versionato"}\n'
                       f'Revisione richiesta: {HEAD}\n\n'
                       'Aggiornamento consentito SOLO con SIPA e tutti i client chiusi.\n'
                       '1. Salvare una copia di sicurezza delle impostazioni.\n'
                       '2. Aprire il terminale sulla postazione amministrativa.\n'
                       '3. Eseguire: python cli.py upgrade-db --backup-dir ~/BackupSIPA\n'
                       '4. Verificare: python cli.py db-version\n'
                       '5. Riavviare SIPA.\n\n'
                       'Il comando crea e verifica il backup PRIMA della migrazione.\n'
                       'Se il database è già alla revisione corretta, non apporta modifiche.')
            dlg = ft.AlertDialog(modal=True, title=ft.Text('Aggiornamento schema — procedura offline'),
                content=ft.Column([ft.Text(message, selectable=True)], width=650, height=330,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Chiudi', on_click=lambda e: page.pop_dialog())])
            page.show_dialog(dlg)

        def database_help(e=None):
            dlg=ft.AlertDialog(modal=True,title=ft.Text('Guida alle operazioni sul database'),
                content=ft.Column([ft.Text(DB_ADMIN_GUIDE,selectable=True,size=12)],
                   width=800,height=520,scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Chiudi guida',on_click=lambda e:page.pop_dialog())])
            page.show_dialog(dlg)

        if has_permission(user['id'],'backup.manage'):
            content.controls.extend([
                ft.Divider(),ft.Text('Database e aggiornamenti',size=20,weight=ft.FontWeight.BOLD),
                ft.Text(f'Revisione database: {revision() or "non versionato"} • Revisione applicazione: {HEAD}', size=12),
                ft.Row([ft.OutlinedButton('Configura database', icon=ft.Icons.STORAGE, on_click=database_dialog),
                        ft.Button('Aggiorna schema (con backup)', icon=ft.Icons.SYSTEM_UPDATE_ALT, on_click=upgrade_dialog)], wrap=True),
                ft.Divider(),ft.Text('Documenti e stampe',size=20,weight=ft.FontWeight.BOLD),
                ft.OutlinedButton('Configura cartella stampe / esportazioni', icon=ft.Icons.FOLDER_OPEN, on_click=export_directory_dialog),
                ft.Divider(),ft.Text('Backup e ripristino',size=20,weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Button('Genera backup',icon=ft.Icons.BACKUP,on_click=backup_dialog),
                    ft.OutlinedButton('Ripristina da file / confronta schema',icon=ft.Icons.RESTORE,on_click=restore_picker),
                ],wrap=True),
                ft.Text('Ripristino e migrazioni SOLO da terminale con tutti i client chiusi. I controlli e i backup sono consentiti nel programma.',size=12,color=ft.Colors.GREY_700),
                ft.OutlinedButton('Guida operazioni database',icon=ft.Icons.HELP_OUTLINE,on_click=database_help)
            ])

        content.controls.extend([
            ft.Row([ft.Text('Gestione utenti', size=21, weight=ft.FontWeight.BOLD),
                    ft.Button('Nuovo utente', icon=ft.Icons.PERSON_ADD, on_click=lambda e: user_dialog())], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            rows, ft.OutlinedButton('Permessi per ruolo', icon=ft.Icons.ADMIN_PANEL_SETTINGS, on_click=permission_dialog), ft.Divider(), ft.Text('Ultimi eventi di accesso e amministrazione', size=19, weight=ft.FontWeight.BOLD),
            ft.OutlinedButton('Aggiorna', icon=ft.Icons.REFRESH, on_click=lambda e: refresh()), events,
        ])
        refresh()

    login_screen()

if __name__ == '__main__':
    if revision() != HEAD:
        raise SystemExit(f'Schema non aggiornato: {revision() or "non versionato"}. Eseguire: python cli.py upgrade-db --backup-dir ~/BackupSIPA')
    if '--bootstrap-only' in sys.argv:
        init_database()
        bootstrap()
    else:
        init_database()
        ft.run(main, assets_dir=str(ASSETS))
