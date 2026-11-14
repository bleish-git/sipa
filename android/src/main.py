"""SIPA Presenze: app Android/tablet offline con navigazione a viste."""
import flet as ft
from scambio_presenze import crea_esiti, leggi_elenco, serialize
import archivio_locale as archivio

VERSIONE = "0.1.2"
COPYRIGHT = "© 2026 bleish · Licenza MIT"


def main(page: ft.Page):
    page.title = "SIPAdroid"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.Colors.GREY_50
    page.padding = 0

    elenco = None
    presenti = set()
    messaggi = {}
    messaggio_attivo = None
    picker = ft.FilePicker()
    # Il percorso della bozza appartiene allo storage privato dell'app.

    def notifica(msg, errore=False):
        if messaggio_attivo is not None:
            messaggio_attivo.value = msg
            messaggio_attivo.color = ft.Colors.RED_700 if errore else ft.Colors.GREEN_700
            page.update()

    def clear_message():
        if messaggio_attivo is not None:
            messaggio_attivo.value = ""

    def go(route):
        clear_message()
        page.navigate(route)

    def contenuto(*controls, expand=False):
        """SafeArea per barre Android, larghezza comoda su tablet."""
        inner = ft.Column(
            controls=list(controls), spacing=14,
            expand=True, scroll=ft.ScrollMode.AUTO if not expand else None,
        )
        return ft.SafeArea(
            expand=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.START,
                expand=True,
                controls=[ft.Container(
                    width=min(900, max(280, (page.width or 400) - 24)),
                    padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                    content=inner,
                )],
            ),
        )

    def make_view(route, title, controls, expand=False):
        nota = ft.Text(size=13, selectable=True)
        messaggi[route] = nota
        return ft.View(
            route=route,
            appbar=ft.AppBar(title=ft.Text(title), center_title=False),
            bgcolor=ft.Colors.GREY_50,
            padding=0,
            controls=[contenuto(*controls, nota, expand=expand)],
        )

    def accedi(e):
        """Punto previsto per il futuro login: adesso accesso diretto al menu."""
        go("/menu")

    def splash_view():
        """Schermata iniziale: l'accesso al menu richiede un tocco su Accedi."""
        return ft.View(
            route="/",
            bgcolor=ft.Colors.WHITE,
            padding=0,
            controls=[ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=18,
                    controls=[
                        ft.Image(src="logo-sipa.png", width=300, height=175,
                                 fit=ft.BoxFit.CONTAIN),
                        ft.Text(f"SIPAdroid - Versione {VERSIONE}", color=ft.Colors.BLUE_GREY_700),
                        ft.Text(COPYRIGHT, color=ft.Colors.BLUE_GREY_700,
                                text_align=ft.TextAlign.CENTER, size=12),
                        ft.TextButton("github.com/bleish-git/sipa",
                                      on_click=lambda e: page.launch_url("https://github.com/bleish-git/sipa")),
                        ft.Container(height=14),
                        ft.Button("Accedi", icon=ft.Icons.LOGIN,
                                  on_click=accedi, width=220, height=48),
                    ],
                ),
            )],
        )

    def home_view():
        """Menu modulare: altre funzioni potranno essere inserite qui."""
        return make_view("/menu", "SIPAdroid", [
            ft.Image(src="logo-sipa.png", width=190, height=100, fit=ft.BoxFit.CONTAIN),
            ft.Text("Seleziona una funzione", size=19, weight=ft.FontWeight.BOLD),
            ft.Button("Mercatino · Rilevazione presenze", icon=ft.Icons.CHECKLIST,
                      on_click=lambda e: go("/inizia")),
            ft.OutlinedButton("Informazioni e licenza", icon=ft.Icons.INFO_OUTLINE,
                              on_click=lambda e: go("/about")),
        ])

    def about_view():
        return make_view("/about", "Informazioni", [
            ft.Image(src="logo-sipa.png", width=210, height=110, fit=ft.BoxFit.CONTAIN),
            ft.Text(f"SIPAdroid — versione {VERSIONE}", weight=ft.FontWeight.BOLD),
            ft.Text("Modulo mobile del progetto SIPA, sviluppato in Python con Flet."),
            ft.Text(COPYRIGHT),
            ft.TextButton("Repository / Sviluppo: github.com/bleish-git/sipa",
                          on_click=lambda e: page.launch_url("https://github.com/bleish-git/sipa")),
            ft.TextButton("Indietro", on_click=lambda e: go("/menu")),
        ])

    async def importa(e):
        nonlocal elenco, presenti
        try:
            files = await picker.pick_files(
                allow_multiple=False, with_data=True,
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["json"],
            )
            if not files:
                return
            selected = files[0]
            raw = selected.bytes if selected.bytes else open(selected.path, "rb").read()
            nuovo = leggi_elenco(raw)
            try:
                old = archivio.leggi()
            except Exception:
                old = None

            def sostituisci(ev):
                nonlocal elenco, presenti
                try:
                    archivio.salva(nuovo, set())
                    elenco = nuovo
                    presenti = set()
                    if old:
                        page.pop_dialog()
                    go("/riepilogo")
                except Exception as exc:
                    notifica("Impossibile salvare l'elenco: " + str(exc), True)

            if old:
                page.show_dialog(ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Sostituire la bozza?"),
                    content=ft.Text("L'importazione eliminerà le spunte della bozza precedente sul dispositivo. Procedere?"),
                    actions=[
                        ft.TextButton("Annulla", on_click=lambda ev: page.pop_dialog()),
                        ft.Button("Importa e sostituisci", on_click=sostituisci),
                    ],
                ))
            else:
                sostituisci(None)
        except Exception as exc:
            notifica("Importazione non riuscita: " + str(exc), True)

    def riprendi(e=None):
        nonlocal elenco, presenti
        try:
            data = archivio.leggi()
            if not data:
                raise ValueError("Nessuna bozza da riprendere.")
            elenco = data["elenco"]
            presenti = set(data["presenti"])
            go("/riepilogo")
        except Exception as exc:
            notifica("Errore bozza locale: " + str(exc), True)

    def inizia_view():
        try:
            old = archivio.leggi()
            err = None
        except Exception as exc:
            old = None
            err = str(exc)
        actions = [
            ft.Text("Scegli come iniziare:"),
            ft.Button("Importa nuovo elenco dal PC", on_click=importa),
        ]
        if old:
            actions.append(ft.OutlinedButton("Riprendi bozza non esportata", on_click=riprendi))
        if err:
            actions.append(ft.Text("Errore archivio locale: " + err, color=ft.Colors.RED_700))
        return make_view("/inizia", "Rilevamento presenze", actions)

    def riepilogo_view():
        if not elenco:
            return make_view("/riepilogo", "Riepilogo elenco", [
                ft.Text("Nessun elenco caricato."),
                ft.Button("Importa elenco", on_click=lambda e: go("/inizia")),
            ])
        return make_view("/riepilogo", "Riepilogo elenco", [
            ft.Text(f"Data: {elenco['data']}"),
            ft.Text(f"Mercato: {elenco['giornata']}"),
            ft.Text(f"Luogo: {elenco['luogo']}"),
            ft.Text(f"Ditte da controllare: {len(elenco['ditte'])}"),
            ft.Text(f"Già spuntate: {len(presenti)}"),
            ft.Text("Elenco: " + ", ".join(x["denominazione"] for x in elenco["ditte"][:20]) +
                    (" ..." if len(elenco["ditte"]) > 20 else "")),
            ft.Button("Apri rilevazione", icon=ft.Icons.CHECKLIST,
                      on_click=lambda e: go("/presenze")),
            ft.TextButton("Indietro", on_click=lambda e: go("/inizia")),
        ])

    def presenze_view():
        if not elenco:
            return make_view("/presenze", "Presenze", [ft.Text("Nessun elenco caricato.")])
        ricerca = ft.TextField(label="Cerca ditta (almeno 3 caratteri)",
                               prefix_icon=ft.Icons.SEARCH)
        count = ft.Text(weight=ft.FontWeight.W_600)
        ordered = sorted(elenco["ditte"], key=lambda x: (
            x["ordine"], str(x["posto"]), x["denominazione"]
        ))
        rows = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
        checkboxes = {}

        def aggiorna_conteggio():
            count.value = f"{len(presenti)} presenti · {len(ordered)-len(presenti)} non spuntate"

        for d in ordered:
            aid = d["assegnazione_id"]
            cb = ft.Checkbox(
                label=f"{d['denominazione']} — posto {d['posto']}",
                value=aid in presenti,
            )

            def toggle(ev, aid=aid):
                if ev.control.value:
                    presenti.add(aid)
                else:
                    presenti.discard(aid)
                try:
                    archivio.salva(elenco, presenti)
                    aggiorna_conteggio()
                    page.update()
                except Exception as exc:
                    notifica("Errore nel salvataggio: " + str(exc), True)

            cb.on_change = toggle
            checkboxes[aid] = (d["denominazione"].casefold(), cb)

        def filter_rows(e=None):
            q = (ricerca.value or "").strip().casefold()
            rows.controls = [
                ft.Container(content=cb, padding=ft.Padding.symmetric(vertical=4))
                for name, cb in checkboxes.values()
                if len(q) < 3 or q in name
            ]
            aggiorna_conteggio()
            page.update()

        async def esporta(e):
            try:
                result = crea_esiti(elenco, presenti)
                data = serialize(result)
                path = await picker.save_file(
                    file_name=f"sipa_esiti_{elenco['data']}_{elenco['elenco_id'][:8]}.json",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["json"], src_bytes=data,
                )
                if path:
                    archivio.cancella()
                    go("/menu")
                    notifica("Esiti esportati. La bozza locale è stata rimossa.")
                else:
                    notifica("Esportazione annullata: la bozza è conservata.", True)
            except Exception as exc:
                notifica("Esportazione non riuscita: " + str(exc), True)

        ricerca.on_change = filter_rows
        aggiorna_conteggio()
        # La lista occupa l'altezza residua e scorre al tocco senza altezza fissa.
        lista = ft.Container(
            content=rows, expand=True,
            # Flet 0.86.5 non espone ft.border.all: evitare l'API rimossa.
            bgcolor=ft.Colors.GREY_100,
            border_radius=12,
            padding=8,
        )
        view = make_view("/presenze", "Rilevazione presenze", [
            ft.Text(f"{elenco['giornata']} — {elenco['data']}"),
            ft.Text("Spuntare esclusivamente le ditte presenti."),
            ricerca, count, lista,
            ft.Button("Esporta sul dispositivo", icon=ft.Icons.SAVE_ALT, on_click=esporta),
            ft.TextButton("Indietro (salva automaticamente)",
                          on_click=lambda e: go("/riepilogo")),
        ], expand=True)
        return view

    def route_change(e=None):
        nonlocal messaggio_attivo
        route = page.route or "/"
        routes = ["/", "/menu", "/inizia", "/riepilogo", "/presenze"]
        if route == "/about":
            page.views = [splash_view(), home_view(), about_view()]
        elif route in routes:
            index = routes.index(route)
            builders = [splash_view, home_view, inizia_view, riepilogo_view, presenze_view]
            page.views = [builders[i]() for i in range(index + 1)]
        else:
            page.views = [splash_view()]
        messaggio_attivo = messaggi.get(route)
        page.update()

    def view_pop(e):
        # Android Back: torna alla vista precedente; sulla schermata iniziale
        # non si chiude automaticamente l'app e rimane visibile Accedi.
        if len(page.views) > 1:
            go(page.views[-2].route)
        else:
            go("/")

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    route_change()


if __name__ == "__main__":
    ft.run(main)
