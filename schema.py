"""Database versioning: Alembic migrations, safe legacy adoption."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from database import engine, Base

BASE = Path(__file__).resolve().parent
HEAD = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parent / 'alembic.ini'))).get_current_head()

def config():
    return Config(str(BASE / 'alembic.ini'))

def revision(connection=None):
    with engine.connect() as conn:
        if not inspect(conn).has_table('alembic_version'):
            return None
        return conn.execute(text('SELECT version_num FROM alembic_version')).scalar()

def adopt_legacy():
    """Stamp only if all tables AND columns from baseline exist; no silent schema changes."""
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    required = set(Base.metadata.tables) - {'attivita_economiche'}
    if not existing.intersection(required):
        return False
    missing = required - existing
    if missing:
        raise RuntimeError(f'Schema preesistente incompleto: tabelle mancanti {sorted(missing)}. Eseguire prima la migrazione v0.2→v0.3.')
    for name, table in Base.metadata.tables.items():
        if name not in required:
            continue
        present = {c['name'] for c in insp.get_columns(name)}
        missing_columns = {c.name for c in table.columns} - present
        if missing_columns:
            raise RuntimeError(f'Schema preesistente incompleto: {name} senza colonne {sorted(missing_columns)}')
    command.stamp(config(), '0001_initial')
    return True

def upgrade():
    if revision() is None:
        adopt_legacy()
    command.upgrade(config(), 'head')

def check_current():
    rev = revision()
    if rev != HEAD:
        raise RuntimeError(f'Schema database non aggiornato: {rev or "non versionato"}; richiesto {HEAD}. Eseguire python cli.py upgrade-db.')
