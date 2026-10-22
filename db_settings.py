"""Configurazione persistente del database (senza memorizzare password)."""
import json
import os
from pathlib import Path
from sqlalchemy.engine import URL

CONFIG_PATH = Path.home() / '.config' / 'sipa' / 'database.json'
DEFAULT = {'driver': 'sqlite', 'sqlite_path': str(Path(__file__).resolve().parent / 'sipa.db'),
           'host': '127.0.0.1', 'port': 5432, 'database': 'sipa', 'username': 'sipa', 'sslmode': 'require'}

def read_settings():
    values = DEFAULT.copy()
    if CONFIG_PATH.is_file():
        loaded = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        values.update({k: v for k, v in loaded.items() if k in DEFAULT})
    return values

def validate(values):
    driver = values.get('driver')
    if driver not in ('sqlite', 'postgresql'):
        raise ValueError('Tipo di database non supportato.')
    if driver == 'sqlite':
        path = Path(str(values.get('sqlite_path', '')).strip()).expanduser().resolve()
        if not path.is_file():
            raise ValueError('Il file SQLite deve esistere. Per creare un nuovo database usare il comando amministrativo da terminale.')
    else:
        if not all(str(values.get(k, '')).strip() for k in ('host', 'database', 'username')):
            raise ValueError('Host, nome database e utente PostgreSQL sono obbligatori.')
        port = int(values.get('port', 5432))
        if not 1 <= port <= 65535:
            raise ValueError('Porta PostgreSQL non valida.')
        if values.get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError('Selezionare una modalità TLS sicura.')

def save_settings(values):
    settings = {k: values.get(k, DEFAULT[k]) for k in DEFAULT}
    validate(settings)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_PATH)
    return CONFIG_PATH

def database_url():
    override = os.environ.get('SIPA_DB_URL')
    if override:
        return override
    s = read_settings()
    if s['driver'] == 'sqlite':
        return URL.create('sqlite', database=str(Path(s['sqlite_path']).expanduser().resolve()))
    return URL.create('postgresql+psycopg', username=s['username'],
                      password=os.environ.get('SIPA_PG_PASSWORD'), host=s['host'],
                      port=int(s['port']), database=s['database'],
                      query={'sslmode': s['sslmode']})

def describe():
    s = read_settings()
    return (f"SQLite: {s['sqlite_path']}" if s['driver'] == 'sqlite' else
            f"PostgreSQL: {s['host']}:{s['port']}/{s['database']} (TLS {s['sslmode']})")
