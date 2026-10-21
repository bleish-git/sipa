"""SIPA v0.2 - Flet desktop UI; demonstration only, not production-ready."""
import sys
from pathlib import Path
import flet as ft
from database import init_database, engine, log
from sqlalchemy.orm import Session
from security import (authenticate, bootstrap, list_users, list_events, create_user,
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
                error.value = 'Credenziali non valide o account disattivato.'
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
                ft.Text('SIPA v0.2 • ambiente dimostrativo', size=12, color=ft.Colors.GREY_600),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15))
        page.add(ft.Container(content=card, alignment=ft.Alignment.CENTER, expand=True, bgcolor=ft.Colors.BLUE_GREY_50))
        page.update()

    def dashboard():
        nonlocal selected_section
        page.clean()
        if selected_section == 5 and user['role'] != 'admin':
            selected_section = 0
        content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=15)
        navigation = ft.Column(spacing=5)

        def choose(index):
            nonlocal selected_section
            if user['must_change_password']:
                password_dialog(force=True)
                return
            if index == 5 and user['role'] != 'admin':
                return
            selected_section = index
            render_navigation()
            render_content()
            page.update()

        def render_navigation():
            navigation.controls.clear()
            for i, (label, icon) in enumerate(SECTIONS):
                if i == 5 and user['role'] != 'admin':
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
        if user['role'] != 'admin':
            return
        rows = ft.Column(spacing=5)
        events = ft.Column(spacing=5)

        def user_dialog(existing=None, mode='create'):
            username = ft.TextField(label='Nome utente', value=existing['username'] if existing else '', disabled=existing is not None)
            password = ft.TextField(label='Password temporanea (min. 12 caratteri)', password=True, can_reveal_password=True)
            role = ft.Dropdown(label='Ruolo', value=existing['role'] if existing else 'operatore',
                options=[ft.dropdown.Option('admin', 'Amministratore'), ft.dropdown.Option('operatore', 'Operatore')])
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

        content.controls.extend([
            ft.Row([ft.Text('Gestione utenti', size=21, weight=ft.FontWeight.BOLD),
                    ft.Button('Nuovo utente', icon=ft.Icons.PERSON_ADD, on_click=lambda e: user_dialog())], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            rows, ft.Divider(), ft.Text('Ultimi eventi di accesso e amministrazione', size=19, weight=ft.FontWeight.BOLD),
            ft.OutlinedButton('Aggiorna', icon=ft.Icons.REFRESH, on_click=lambda e: refresh()), events,
        ])
        refresh()

    login_screen()

if __name__ == '__main__':
    if '--init-admin' in sys.argv:
        bootstrap()
    else:
        init_database()
        ft.run(main, assets_dir=str(ASSETS))
