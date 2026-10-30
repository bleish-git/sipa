"""Esportazione/ripristino PostgreSQL in SQL testuale (dialetto PostgreSQL)."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone
from sqlalchemy import inspect
from database import engine
from db_settings import read_settings
from schema import check_current, revision, HEAD

KEY = Path(__file__).resolve().parent / '.sipa_audit_key'


def _sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def _pg_env():
    c = read_settings()
    if c['driver'] != 'postgresql':
        raise RuntimeError('Questo comando richiede PostgreSQL')
    password = os.getenv(c['password_env'])
    if not password:
        raise RuntimeError(f'Variabile {c["password_env"]} non impostata')
    env = {**os.environ, 'PGPASSWORD': password, 'PGSSLMODE': c['sslmode']}
    common = ['--no-password', '-h', c['host'], '-p', str(c['port']), '-U', c['username']]
    return c, env, common


def backup_sql(destination, *, require_current=True):
    if require_current:
        check_current()
    if not shutil.which('pg_dump'):
        raise RuntimeError('pg_dump non installato')
    c, env, common = _pg_env()
    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    sql = dest / f'sipa_{stamp}.sql'
    # --column-inserts rende esplicito ogni nome di colonna; il SQL rimane
    # specifico di PostgreSQL (DDL, sequenze, tipi) e NON SQL ANSI portabile.
    cmd = ['pg_dump', *common, '--format=plain', '--column-inserts',
           '--no-owner', '--no-acl', '--file', str(sql), c['database']]
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        if result.returncode or not sql.exists() or sql.stat().st_size == 0:
            raise RuntimeError('Esportazione PostgreSQL fallita: ' + result.stderr[-500:])
        os.chmod(sql, 0o600)
        manifest = {'application':'SIPA','application_version':'0.57','format':3,
                    'engine':'postgresql','schema_revision':revision(),
                    'database':sql.name,'sha256':_sha(sql),
                    'created_at':datetime.now(timezone.utc).isoformat(),
                    'restore_requires_empty_database':True}
        if KEY.exists():
            keyfile = sql.with_suffix('.auditkey')
            shutil.copy2(KEY, keyfile)
            os.chmod(keyfile, 0o600)
            manifest['audit_key'] = keyfile.name
            manifest['audit_key_sha256'] = _sha(keyfile)
        sql.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return sql
    except Exception:
        sql.unlink(missing_ok=True)
        sql.with_suffix('.auditkey').unlink(missing_ok=True)
        raise


def inspect_sql(source):
    sql = Path(source).expanduser().resolve()
    manifest_path = sql.with_suffix('.json')
    if not sql.is_file() or not manifest_path.is_file():
        raise ValueError('File SQL o manifest mancante')
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    if data.get('engine') != 'postgresql' or data.get('database') != sql.name:
        raise ValueError('Manifest PostgreSQL non valido')
    if not hmac.compare_digest(_sha(sql), data.get('sha256', '')):
        raise ValueError('Checksum SQL non valido')
    if data.get('audit_key'):
        key = sql.parent / Path(data['audit_key']).name
        if not key.is_file() or not hmac.compare_digest(_sha(key), data.get('audit_key_sha256', '')):
            raise ValueError('Chiave audit del backup mancante o alterata')
    return {'file':str(sql), 'schema_backup':data.get('schema_revision'),
            'schema_required':HEAD,'compatible':data.get('schema_revision') == HEAD,
            'manifest':data}


def restore_sql(source, confirmation):
    """Ripristino SOLO CLI su DB PostgreSQL preesistente completamente vuoto."""
    if confirmation != 'RIPRISTINA SIPA':
        raise ValueError('Conferma esatta mancante')
    report = inspect_sql(source)
    from operations import require_supported_backup_revision
    require_supported_backup_revision(report['schema_backup'])
    if not shutil.which('psql'):
        raise RuntimeError('psql non installato')
    # Questa verifica non può garantire da sola l'assenza di altri client:
    # chiudere tutti i client ed eseguire solo su un database nuovo e isolato.
    if inspect(engine).get_table_names():
        raise RuntimeError('Il database PostgreSQL di destinazione non è vuoto: ripristino rifiutato')
    c, env, common = _pg_env()
    if KEY.exists():
        raise RuntimeError('Chiave audit locale già presente: archiviarla prima del ripristino')
    cmd = ['psql', '-X', '-v', 'ON_ERROR_STOP=1', '--single-transaction',
           *common, '-d', c['database'], '-f', report['file']]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError('Ripristino PostgreSQL non riuscito: ' + result.stderr[-900:])
    manifest = report['manifest']
    if manifest.get('audit_key'):
        src = Path(report['file']).parent / Path(manifest['audit_key']).name
        shutil.copy2(src, KEY)
        os.chmod(KEY, 0o600)
    return report
