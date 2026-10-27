"""First-run graphical and CLI setup for SIPA 0.56.

An existing database is only inspected, never migrated, stamped or seeded.
"""
import getpass
import hashlib
import hmac
import json
import shutil
from datetime import timezone
import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from db_settings import CONFIG, DEFAULT, database_url, save_settings, test_connection

from alembic.config import Config
from alembic.script import ScriptDirectory
EXPECTED_REVISION = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parent / 'alembic.ini'))).get_current_head()
REQUIRED_COLUMNS = {
    'users': {'id','username','salt','password_hash','role','active','must_change_password','failed_attempts','locked_until'},
    'attivita_economiche': {'id','nome','titolare','pec','descrizione','note','data_inizio','data_cessazione'},
    'audit_events': {'id','created_at','actor','action','target','details','previous_hash','entry_hash'},
    'permissions': {'code','description'},
    'role_permissions': {'role','permission_code'},
    'login_throttle': {'identifier','failures','blocked_until'},
}

WARNING = ('SQLite è adatto a installazioni locali. Non è consigliato utilizzare il file '
           'su condivisioni di rete (SMB/NAS) o con più postazioni concorrenti: '
           'per SIPA multiutente utilizzare PostgreSQL.')


def _engine(values, *, readonly=False):
    values = dict(values)
    if values['driver'] == 'sqlite':
        path = Path(values['sqlite_path']).expanduser().resolve()
        if readonly:
            # mode=ro prevents SQLite from creating or changing the database.
            return create_engine('sqlite+pysqlite://', creator=lambda: sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True), pool_pre_ping=True)
        return create_engine(URL.create('sqlite', database=str(path)), pool_pre_ping=True)
    password = os.environ.get(str(values['password_env']))
    if not password:
        raise ValueError('Impostare la variabile ambiente della password PostgreSQL prima di procedere.')
    url = URL.create('postgresql+psycopg', username=values['username'], password=password,
                     host=values['host'], port=int(values['port']), database=values['database'],
                     query={'sslmode': values['sslmode'], 'connect_timeout': '5'})
    return create_engine(url, pool_pre_ping=True)


def inspect_existing(values, username, password, audit_key_path=None):
    """Only SELECT and metadata reads; rejects incompatible DB without mutating it."""
    if values['driver'] == 'sqlite' and not Path(values['sqlite_path']).expanduser().is_file():
        raise ValueError('Il database SQLite indicato non esiste.')
    if values['driver'] != 'sqlite':
        test_connection(values)
    # No database/security imports: these modules create a global engine on import.
    from sqlalchemy import inspect as sa_inspect
    engine = _engine(values, readonly=(values['driver'] == 'sqlite'))
    try:
        with engine.connect() as conn:
            if values['driver'] == 'postgresql':
                conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            names = set(sa_inspect(conn).get_table_names())
            required = set(REQUIRED_COLUMNS) | {'alembic_version'}
            missing = required - names
            if missing:
                raise ValueError('Schema incompleto, mancano tabelle: ' + ', '.join(sorted(missing)))
            for table, needed in REQUIRED_COLUMNS.items():
                columns = {x['name'] for x in sa_inspect(conn).get_columns(table)}
                if needed - columns:
                    raise ValueError(f'Colonne mancanti in {table}: {sorted(needed - columns)}')
            rev = conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one_or_none()
            if rev != EXPECTED_REVISION:
                raise ValueError(f'Revisione incompatibile: database {rev or "non versionato"}, SIPA richiede {EXPECTED_REVISION}. '
                                 'Effettuare l’aggiornamento amministrativo sul server, non su questo client.')
            total = conn.execute(text('SELECT count(*) FROM users')).scalar_one()
            if total < 1:
                raise ValueError('Database privo di utenti: collegamento annullato.')
            # Explicit administrative credential check without writing throttle/audit rows.
            record = conn.execute(text('SELECT salt, password_hash, active, role FROM users WHERE username=:name'),
                                  {'name': username.strip()}).first()
            from hashlib import pbkdf2_hmac
            from hmac import compare_digest
            test_salt = bytes(record.salt) if record else bytes(16)
            candidate = pbkdf2_hmac('sha256', password.encode('utf-8'), test_salt, 600_000)
            if not (record and record.active and record.role == 'admin'
                    and compare_digest(candidate, bytes(record.password_hash))):
                raise ValueError('Credenziali amministrative non valide per il database esistente.')
            # Existing HMAC history requires the SAME audit key on every SIPA client.
            audit_count = conn.execute(text('SELECT count(*) FROM audit_events')).scalar_one()
            key_target = Path(__file__).resolve().parent / '.sipa_audit_key'
            key_file = Path(audit_key_path).expanduser().resolve() if audit_key_path else key_target
            if audit_count and not key_file.is_file():
                raise ValueError('È necessaria la chiave audit originale (.sipa_audit_key). '
                                 'Fornire il percorso del file proveniente dall’installazione già in uso.')
            if audit_count:
                key = key_file.read_bytes()
                if len(key) != 32:
                    raise ValueError('Chiave audit non valida.')
                prev = 'GENESIS'
                for row in conn.execute(text('SELECT id, created_at, actor, action, target, details, '
                                             'previous_hash, entry_hash FROM audit_events ORDER BY id')):
                    stamp = row.created_at
                    if isinstance(stamp, str):
                        from datetime import datetime
                        stamp = datetime.fromisoformat(stamp)
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    payload = json.dumps([stamp.isoformat(), row.actor, row.action, row.target,
                                          row.details, prev], ensure_ascii=False)
                    check = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
                    if row.previous_hash != prev or not hmac.compare_digest(check, row.entry_hash):
                        raise ValueError('Chiave audit errata o catena audit non valida; collegamento interrotto.')
                    prev = row.entry_hash
            return {'revision': rev, 'users': total, 'tables': len(names),
                    'audit_key_source': str(key_file) if audit_count else None}
    finally:
        engine.dispose()


def create_new(values, username, password):
    """Initialize empty database only; provision the first administrator."""
    if not username.strip() or len(username.strip()) > 80:
        raise ValueError('Nome amministratore non valido.')
    if len(password) < 12:
        raise ValueError('La password amministrativa deve contenere almeno 12 caratteri.')
    values = dict(values)
    if values['driver'] == 'sqlite':
        p = Path(values['sqlite_path']).expanduser().resolve()
        if p.exists() and p.stat().st_size > 0:
            raise ValueError('Il file SQLite non è vuoto: scegliere “Collega esistente” oppure un nuovo percorso.')
        if not p.parent.is_dir():
            raise ValueError('La directory SQLite non esiste.')
    else:
        test_connection(values)
        engine = _engine(values)
        try:
            if inspect(engine).get_table_names():
                raise ValueError('Il database PostgreSQL non è vuoto: usare “Collega esistente”.')
        finally:
            engine.dispose()
    if CONFIG.exists():
        raise ValueError('Configurazione già presente: procedura iniziale non consentita.')
    # The SQLAlchemy/Alembic modules create their engines at import time, so save config first.
    save_settings(values, initial=True)
    try:
        from schema import upgrade, check_current
        from database import engine, init_database, User, log
        from security import set_password
        upgrade()
        check_current()
        init_database()
        with Session(engine) as session:
            if session.scalar(select(User.id).limit(1)) is not None:
                raise RuntimeError('Utenti già presenti: inizializzazione interrotta.')
            user = User(username=username.strip(), role='admin', active=True)
            set_password(user, password)
            session.add(user)
            log(session, username.strip(), 'bootstrap_admin', username.strip())
            session.commit()
        return {'revision': EXPECTED_REVISION, 'users': 1}
    except Exception:
        # Do not hide a partial initialization; remove only config so setup can resume deliberately.
        CONFIG.unlink(missing_ok=True)
        raise


def setup(values, mode, username, password, audit_key_path=None):
    if CONFIG.exists():
        raise ValueError('SIPA è già configurato; utilizzare le impostazioni in Amministrazione.')
    if mode == 'existing':
        result = inspect_existing(values, username, password, audit_key_path)
        key_source = result.pop('audit_key_source', None)
        target = Path(__file__).resolve().parent / '.sipa_audit_key'
        if key_source and Path(key_source).resolve() != target.resolve():
            if target.exists():
                raise ValueError('Esiste già una chiave audit locale diversa: non sovrascriverla.')
            # Staging of the already verified key, no remote database mutation.
            with target.open('xb') as f:
                f.write(Path(key_source).read_bytes())
            os.chmod(target, 0o600)
        save_settings(values, initial=True)
        return result
    if mode == 'new':
        return create_new(values, username, password)
    raise ValueError('Modalità non valida.')


def cli_setup():
    if CONFIG.exists():
        raise SystemExit('Configurazione già presente: --init-admin è riservato alla prima installazione.')
    print('SIPA 0.56 — configurazione iniziale senza interfaccia grafica')
    mode = input('Operazione: [1] Crea nuovo / [2] Collega esistente: ').strip()
    if mode not in ('1', '2'):
        raise SystemExit('Operazione non valida')
    username = input('Nome amministratore: ').strip()
    password = getpass.getpass('Password amministratore: ')
    if mode == '1' and password != getpass.getpass('Conferma password: '):
        raise SystemExit('Le password non coincidono')
    driver = (input('Motore [sqlite/postgresql] (sqlite): ').strip().lower() or 'sqlite')
    if driver not in ('sqlite', 'postgresql'):
        raise SystemExit('Motore non valido')
    values = dict(DEFAULT, driver=driver)
    if driver == 'sqlite':
        print('ATTENZIONE:', WARNING)
        values['sqlite_path'] = input(f"Percorso DB SQLite [{values['sqlite_path']}]: ").strip() or values['sqlite_path']
    else:
        for key, label in [('host','Host'),('port','Porta'),('database','Database'),('username','Utente PostgreSQL'),
                           ('password_env','Variabile ambiente password'),('sslmode','TLS')]:
            value = input(f'{label} [{values[key]}]: ').strip()
            if value:
                values[key] = value
    audit_file = input('Percorso chiave audit esistente (.sipa_audit_key), se necessaria [invio=cartella SIPA]: ').strip() if mode == '2' else None
    result = setup(values, 'new' if mode == '1' else 'existing', username, password, audit_file)
    print('Configurazione completata:', result)


def launch_gui():
    import flet as ft

    def wizard(page: ft.Page):
        page.title = 'SIPA 0.56 — prima configurazione'
        page.window.width = 850
        page.window.height = 760
        page.scroll = ft.ScrollMode.AUTO
        username = ft.TextField(label='Amministratore SIPA', width=420)
        password = ft.TextField(label='Password amministratore', password=True, can_reveal_password=True, width=420)
        confirm = ft.TextField(label='Conferma password (solo nuovo database)', password=True, can_reveal_password=True, width=420)
        mode = ft.RadioGroup(value='new', content=ft.Column([
            ft.Radio(value='new', label='Crea nuovo database'),
            ft.Radio(value='existing', label='Collega database esistente (sola lettura)'),
        ]))
        driver = ft.Dropdown(label='Database', width=280, value='sqlite', options=[
            ft.dropdown.Option('sqlite', 'SQLite'),
            ft.dropdown.Option('postgresql', 'PostgreSQL'),
        ])
        path = ft.TextField(label='File SQLite', value=DEFAULT['sqlite_path'], width=650)
        host = ft.TextField(label='Host', value=DEFAULT['host'], width=240)
        port = ft.TextField(label='Porta', value=str(DEFAULT['port']), width=110)
        dbname = ft.TextField(label='Nome database', value=DEFAULT['database'], width=220)
        dbuser = ft.TextField(label='Utente PostgreSQL', value=DEFAULT['username'], width=220)
        pwenv = ft.TextField(label='Variabile ambiente password PostgreSQL', value=DEFAULT['password_env'], width=380)
        ssl = ft.Dropdown(label='TLS', value='require', options=[ft.dropdown.Option(x) for x in ('require', 'verify-ca','verify-full')], width=200)
        warning = ft.Text(WARNING, color=ft.Colors.ORANGE_800, size=12)
        postgres_info = ft.Text('Configurare prima la variabile ambiente della password PostgreSQL sul PC.', size=12)
        pgcontrols = ft.Column([ft.Row([host, port, dbname], wrap=True),
                                ft.Row([dbuser, pwenv, ssl], wrap=True), postgres_info])
        audit_path = ft.TextField(label='Chiave audit originale (.sipa_audit_key): percorso facoltativo', width=650)
        msg = ft.Text(color=ft.Colors.RED_700, selectable=True)
        def change(e=None):
            sqlite = driver.value == 'sqlite'
            path.visible, warning.visible, pgcontrols.visible = sqlite, sqlite, not sqlite
            confirm.visible = mode.value == 'new'
            audit_path.visible = mode.value == 'existing'
            page.update()
        def proceed(e):
            msg.value = 'Verifica in corso...'
            page.update()
            try:
                if mode.value == 'new' and password.value != confirm.value:
                    raise ValueError('Le password non coincidono.')
                values = dict(DEFAULT, driver=driver.value, sqlite_path=path.value,
                              host=host.value, port=port.value, database=dbname.value,
                              username=dbuser.value, password_env=pwenv.value, sslmode=ssl.value)
                result = setup(values, mode.value, username.value or '', password.value or '', audit_path.value or None)
                msg.color = ft.Colors.GREEN_700
                msg.value = f'Configurazione completata. Revisione: {result["revision"]}; utenti: {result["users"]}. Chiudere questa finestra e riavviare SIPA.'
                submit.disabled = True
            except Exception as exc:
                msg.color = ft.Colors.RED_700
                msg.value = str(exc)
            page.update()
        mode.on_change = change
        driver.on_select = change
        driver.on_change = change
        submit = ft.Button('Verifica e completa configurazione', on_click=proceed)
        page.add(ft.Container(padding=25, content=ft.Column([
            ft.Text('SIPA 0.56 · Prima configurazione', size=25, weight=ft.FontWeight.BOLD),
            ft.Text('Credenziali amministrative: per un nuovo archivio verrà creato questo utente; '
                    'per un archivio esistente ne verrà verificata la password senza modificarlo.'),
            username, password, confirm, ft.Divider(), ft.Text('Operazione', weight=ft.FontWeight.BOLD), mode,
            ft.Text('Motore database', weight=ft.FontWeight.BOLD), driver, warning, path,
            pgcontrols, audit_path, ft.Divider(), submit, msg,
        ], scroll=ft.ScrollMode.AUTO, spacing=12)))
        change()
    ft.run(wizard)
