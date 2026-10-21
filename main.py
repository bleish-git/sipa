"""SIPA v0.2 - Flet desktop UI; demonstration only, not production-ready."""
import sys
import json
from pathlib import Path
import flet as ft
from database import init_database, engine, log
from schema import upgrade as upgrade_schema
from operations import backup as create_backup, inspect_backup
from sqlalchemy.orm import Session
from security import (authenticate, bootstrap, has_permission, role_permissions, set_role_permissions, list_users, list_events, create_user,
                      update_user, reset_password, change_password)

ASSETS = Path(__file__).resolve().parent / 'assets'
SECTIONS = [
    ('Dashboard', ft.Icons.DASHBOARD_OUTLINED),
    ('Attività economiche', ft.Icons.STOREFRONT_OUTLINED),
    ('Sanzioni amministrative', ft.Icons.DESCRIPTION_OUTLINED),
    ('Accertamenti', ft.Icons.FACT_CHECK_OUTLINED),
    ('Archivio documentale', ft.Icons.FOLDER_OUTLINED),
    ('Amministrazione', ft.Icons.MANAGE_ACCOUNTS_OUTLINED),
]

def main(page: ft.Page):
    page.title = 'SIPA - Sistema Informativo Polizia Amministrativa'
    page.theme_mode = ft.ThemeMode.LIGHT
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
                ft.Text('SIPA v0.3 • ambiente dimostrativo', size=12, color=ft.Colors.GREY_600),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15))
        page.add(ft.Container(content=card, alignment=ft.Alignment.CENTER, expand=True, bgcolor=ft.Colors.BLUE_GREY_50))
        page.update()

    def dashboard():
        nonlocal selected_section
        page.clean()
        if selected_section == 5 and not has_permission(user['id'], 'users.manage'):
            selected_section = 0
        content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)
        navigation = ft.Column(spacing=5)

        def choose(index):
            nonlocal selected_section
            if user['must_change_password']:
                password_dialog(force=True)
                return
            if index == 5 and not has_permission(user['id'], 'users.manage'):
                return
            needed = {0:'dashboard.view',1:'attivita.read',2:'verbali.read',3:'accertamenti.read',4:'documenti.read',5:'users.manage'}[index]
            if not has_permission(user['id'], needed):
                notify('Accesso non autorizzato a questo settore.', True)
                return
            selected_section = index
            render_navigation()
            render_content()
            page.update()

        def render_navigation():
            navigation.controls.clear()
            for i, (label, icon) in enumerate(SECTIONS):
                required = {0:'dashboard.view',1:'attivita.read',2:'verbali.read',3:'accertamenti.read',4:'documenti.read',5:'users.manage'}[i]
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
                ft.Text('SIPA • ambiente di sviluppo, dati fittizi', color=ft.Colors.GREY_700),
                ft.Divider(),
            ])
            if selected_section == 5:
                render_admin(content)
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
            selected_role = ft.Dropdown(label='Ruolo', value='operatore',
                options=[ft.dropdown.Option(r) for r in ('responsabile','operatore','consultazione')])
            checks = {code: ft.Checkbox(label=f'{code} — {desc}') for code,desc in PERMISSIONS.items()}
            box = ft.Column(list(checks.values()), scroll=ft.ScrollMode.AUTO, height=390, width=530)
            message = ft.Text(color=ft.Colors.RED_700)
            def load(e=None):
                allowed = set(current.get(selected_role.value, []))
                for code, control in checks.items():
                    control.value = code in allowed
                page.update()
            def save(e):
                try:
                    set_role_permissions(user['id'], selected_role.value,
                                         [code for code, c in checks.items() if c.value])
                    page.pop_dialog()
                    notify('Permessi aggiornati. Le modifiche si applicano ai nuovi controlli.')
                except (ValueError, PermissionError) as exc:
                    message.value = str(exc)
                    page.update()
            selected_role.on_change = load
            dlg = ft.AlertDialog(modal=True, title=ft.Text('Permessi granulari per ruolo'),
                content=ft.Column([selected_role, box, message], tight=True, width=550),
                actions=[ft.TextButton('Annulla', on_click=lambda e: page.pop_dialog()),
                         ft.Button('Salva', on_click=save)])
            load()
            page.show_dialog(dlg)

        # FilePicker desktop (Flet 0.80+): UI operations only; restore must be done offline.
        def backup_dialog(e=None):
            directory = ft.TextField(label='Cartella di destinazione', value=str(Path.home() / 'BackupSIPA'), width=500)
            message = ft.Text(color=ft.Colors.RED_700)
            dlg = ft.AlertDialog(modal=True, title=ft.Text('Crea backup SIPA'),
                content=ft.Column([ft.Text('Backup completo SQLite, versione dello schema e chiave audit. Non include allegati esterni.'),directory,message],tight=True,width=540),actions=[])
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
                files = await ft.FilePicker().pick_files(allow_multiple=False, dialog_title='Seleziona backup SIPA (.db)',
                                                        file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['db'])
                if not files: return
                path = files[0].path
                if not path:
                    notify('Il selettore non ha restituito un percorso locale.',True)
                    return
                report = inspect_backup(path)
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
                        ft.Text('4. Esegui python cli.py upgrade-db, quindi riavvia SIPA.',size=12),
                    ],scroll=ft.ScrollMode.AUTO,height=470,width=690),
                    actions=[ft.TextButton('Chiudi anteprima',on_click=lambda e:page.pop_dialog())])
                page.show_dialog(dlg)
            except Exception as exc:
                notify('Impossibile analizzare il backup: '+str(exc),True)

        if has_permission(user['id'],'backup.manage'):
            content.controls.extend([
                ft.Divider(),ft.Text('Backup e ripristino',size=20,weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Button('Genera backup',icon=ft.Icons.BACKUP,on_click=backup_dialog),
                    ft.OutlinedButton('Ripristina da file / confronta schema',icon=ft.Icons.RESTORE,on_click=restore_picker),
                ],wrap=True),
                ft.Text('Il ripristino è intenzionalmente offline: il confronto non altera il database.',size=12,color=ft.Colors.GREY_700)
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
    upgrade_schema()
    if '--init-admin' in sys.argv:
        init_database()
        bootstrap()
    else:
        init_database()
        ft.run(main, assets_dir=str(ASSETS))
