"""Configurazione unica del database SIPA; non salva password in chiaro.

Compatibilità: importa, solo in lettura, la vecchia configurazione per-utente
quando il file sipa_database.json non esiste ancora.
"""
import json
import os
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent
CONFIG = BASE / 'sipa_database.json'
LEGACY = Path.home() / '.config' / 'sipa' / 'database.json'
DEFAULT = {
    'driver': 'sqlite', 'sqlite_path': str(BASE / 'sipa.db'),
    'host': '127.0.0.1', 'port': 5432, 'database': 'sipa',
    'username': 'sipa', 'password_env': 'SIPA_PG_PASSWORD',
    'sslmode': 'require',
}


def _normalized(raw):
    values = DEFAULT.copy()
    if 'type' in raw or 'path' in raw:
        # Formato originale db_config.py (v0.5).
        values.update(driver=raw.get('type', 'sqlite'),
                      sqlite_path=raw.get('path') or DEFAULT['sqlite_path'])
    values.update({key: value for key, value in raw.items() if key in DEFAULT})
    return values


def read_settings():
    source = CONFIG if CONFIG.is_file() else LEGACY
    if not source.is_file():
        return DEFAULT.copy()
    data = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Configurazione database non valida')
    return _normalized(data)


def validate(values):
    driver = values.get('driver')
    if driver not in ('sqlite', 'postgresql'):
        raise ValueError('Selezionare SQLite o PostgreSQL')
    if driver == 'sqlite':
        path = str(values.get('sqlite_path') or '').strip()
        if not path:
            raise ValueError('Specificare il percorso SQLite')
        resolved = Path(path).expanduser().resolve()
        if not resolved.parent.is_dir():
            raise ValueError('La cartella SQLite non esiste')
        # Un nuovo DB può essere creato dal comando amministrativo, non dal cambio configurazione.
        if not resolved.is_file():
            raise ValueError('Il file SQLite non esiste. Crearlo tramite procedura amministrativa.')
    else:
        if not all(str(values.get(k) or '').strip() for k in ('host', 'database', 'username')):
            raise ValueError('Host, database e utente PostgreSQL obbligatori')
        try:
            port = int(values.get('port') or 5432)
        except (ValueError, TypeError) as exc:
            raise ValueError('Porta PostgreSQL non valida') from exc
        if not 1 <= port <= 65535:
            raise ValueError('Porta PostgreSQL non valida')
        env = str(values.get('password_env') or '').strip()
        if not env.isidentifier():
            raise ValueError('Nome variabile ambiente password non valido')
        if values.get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError('Modalità TLS non valida')


def test_connection(values, *, allow_new_sqlite=False):
    """Test real connectivity; do not persist untested settings."""
    result = _normalized(values)
    if result['driver'] == 'sqlite' and allow_new_sqlite:
        target = Path(result['sqlite_path']).expanduser().resolve()
        if not target.parent.is_dir():
            raise ValueError('La directory SQLite non esiste')
        if target.exists() and not target.is_file():
            raise ValueError('Il percorso SQLite non è un file')
    else:
        validate(result)
    if result['driver'] == 'sqlite':
        url = URL.create('sqlite', database=str(Path(result['sqlite_path']).expanduser().resolve()))
    else:
        env = result['password_env']
        password = os.environ.get(env)
        if not password:
            raise RuntimeError(f'Password PostgreSQL assente: impostare {env}')
        url = URL.create('postgresql+psycopg', username=result['username'], password=password,
                         host=result['host'], port=int(result['port']), database=result['database'],
                         query={'sslmode': result['sslmode'], 'connect_timeout': '5'})
    test_engine = create_engine(url, pool_pre_ping=True, connect_args={'timeout': 5} if result['driver']=='sqlite' else {})
    try:
        with test_engine.connect() as conn:
            conn.execute(text('SELECT 1'))
    finally:
        test_engine.dispose()
    return result


def save_settings(values, *, initial=False):
    result = _normalized(values)
    if not initial and result['driver'] != read_settings()['driver']:
        raise ValueError('Il motore database non può essere modificato dalla configurazione amministrativa.')
    test_connection(result, allow_new_sqlite=initial)
    if result['driver'] == 'sqlite':
        result['sqlite_path'] = str(Path(result['sqlite_path']).expanduser().resolve())
    else:
        result['port'] = int(result['port'])
    tmp = CONFIG.with_suffix('.json.tmp')
    try:
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG)
    finally:
        tmp.unlink(missing_ok=True)
    return CONFIG


def database_url():
    s = read_settings()
    if s['driver'] == 'sqlite':
        return URL.create('sqlite', database=str(Path(s['sqlite_path']).expanduser().resolve()))
    secret = str(s['password_env'])
    if not secret.isidentifier():
        raise ValueError('Nome variabile ambiente password non valido')
    password = os.environ.get(secret)
    if not password:
        raise RuntimeError(f'Password PostgreSQL assente: impostare {secret}')
    return URL.create('postgresql+psycopg', username=s['username'], password=password,
                      host=s['host'], port=int(s['port']), database=s['database'],
                      query={'sslmode': s['sslmode']})
