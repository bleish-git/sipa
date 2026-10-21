"""Audit verification, safe SQLite backup, verified restore (offline CLI)."""
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import BASE_DIR, AuditEvent, engine, log

KEY = BASE_DIR / '.sipa_audit_key'

def verify_audit():
    if not KEY.exists():
        return False, 'Chiave di audit assente.'
    key = KEY.read_bytes()
    with Session(engine) as session:
        prev = 'GENESIS'
        for e in session.scalars(select(AuditEvent).order_by(AuditEvent.id)):
            stamp = e.created_at
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            payload = json.dumps([stamp.isoformat(), e.actor, e.action, e.target, e.details, prev], ensure_ascii=False)
            expected = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
            if e.previous_hash != prev or not hmac.compare_digest(expected, e.entry_hash):
                return False, f'Catena alterata al record {e.id}'
            prev = e.entry_hash
    return True, 'Catena audit verificata. Controllo locale, non prova di immodificabilità assoluta.'

def _sqlite_path():
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('Backup SQLite disponibile solo per database SQLite.')
    return Path(engine.url.database).resolve()


def _sha(path):
    return hashlib.file_digest(open(path, 'rb'), 'sha256').hexdigest()

def _tables(path):
    with sqlite3.connect(str(path)) as db:
        return {row[0]: {col[1]: col[2] for col in db.execute(f'PRAGMA table_info("{row[0]}")')} for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}

def _revision(path):
    with sqlite3.connect(str(path)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone():
            return 'non versionato'
        row = db.execute('SELECT version_num FROM alembic_version').fetchone()
        return row[0] if row else 'non versionato'

def backup(destination):
    from datetime import datetime, timezone
    from schema import check_current
    check_current()
    source = _sqlite_path()
    if not source.exists(): raise FileNotFoundError(source)
    dest = Path(destination).expanduser().resolve()
    if dest == source.parent: raise ValueError('Scegliere una cartella diversa da quella del database.')
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    stem = f'sipa_{stamp}'
    target = dest / (stem + '.db')
    try:
        with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Controllo integrità SQLite fallito')
        key_name = None
        key_hash = None
        if KEY.exists():
            key_dest = dest / (stem + '.auditkey')
            shutil.copy2(KEY, key_dest)
            os.chmod(key_dest, 0o600)
            key_name, key_hash = key_dest.name, _sha(key_dest)
        manifest = {'format': 2, 'application': 'SIPA', 'application_version': '0.4',
                    'engine': 'sqlite', 'schema_revision': _revision(target),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'database': target.name, 'sha256': _sha(target),
                    'audit_key': key_name, 'audit_key_sha256': key_hash}
        (dest / (stem + '.json')).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return target
    except Exception:
        target.unlink(missing_ok=True)
        (dest / (stem + '.auditkey')).unlink(missing_ok=True)
        raise

def inspect_backup(backup_file):
    source = Path(backup_file).expanduser().resolve()
    manifest_file = source.with_suffix('.json')
    if not source.is_file() or not manifest_file.is_file():
        raise ValueError('Backup o manifest JSON non trovato.')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('database') != source.name or manifest.get('engine', 'sqlite') != 'sqlite':
        raise ValueError('Manifest non corrispondente al backup SQLite.')
    if not hmac.compare_digest(_sha(source), manifest['sha256']):
        raise ValueError('Checksum database non valido.')
    with sqlite3.connect(str(source)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup SQLite non integro.')
    key_source = None
    if manifest.get('audit_key'):
        key_source = source.parent / Path(manifest['audit_key']).name
        if not key_source.is_file(): raise ValueError('Chiave audit del backup assente.')
        if manifest.get('audit_key_sha256') and not hmac.compare_digest(_sha(key_source), manifest['audit_key_sha256']):
            raise ValueError('Checksum della chiave audit non valido.')
    current = _sqlite_path()
    old = _tables(current) if current.exists() else {}
    new = _tables(source)
    added = sorted(set(new)-set(old))
    removed = sorted(set(old)-set(new))
    columns_added = {t:sorted(set(new[t])-set(old[t])) for t in set(old)&set(new) if set(new[t])-set(old[t])}
    columns_removed = {t:sorted(set(old[t])-set(new[t])) for t in set(old)&set(new) if set(old[t])-set(new[t])}
    changed_types = {t:[c for c in set(old[t])&set(new[t]) if old[t][c]!=new[t][c]] for t in set(old)&set(new)}
    changed_types = {t:v for t,v in changed_types.items() if v}
    return {'file':str(source), 'schema_backup':_revision(source),
            'schema_current':_revision(current) if current.exists() else 'assente',
            'tables_only_backup':added, 'tables_only_current':removed,
            'columns_only_backup':columns_added, 'columns_only_current':columns_removed,
            'changed_column_types':changed_types,
            'key_present':bool(key_source), 'manifest':manifest}

def restore(backup_file, confirmation):
    """Offline only: atomic replacement of DB and key after all validations.
    Refuses existing database: safe explicit move/archive required before CLI restore.
    """
    if confirmation != 'RIPRISTINA SIPA': raise ValueError('Conferma esplicita mancante.')
    report = inspect_backup(backup_file)
    source = Path(report['file'])
    manifest = report['manifest']
    target = _sqlite_path()
    if target.exists():
        raise RuntimeError('DB corrente presente: chiudere SIPA, archiviarlo fuori dalla cartella, poi ripetere il ripristino.')
    if KEY.exists():
        raise RuntimeError('Chiave audit corrente presente: archiviarla insieme al DB corrente prima del ripristino.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as td:
        staging = Path(td)
        staged_db = staging / target.name
        shutil.copy2(source, staged_db)
        staged_key = None
        if manifest.get('audit_key'):
            staged_key = staging / KEY.name
            shutil.copy2(source.parent / Path(manifest['audit_key']).name, staged_key)
            os.chmod(staged_key, 0o600)
        # Validate copies again before publishing.
        if _sha(staged_db) != manifest['sha256']:
            raise RuntimeError('Copia temporanea del DB non valida.')
        if staged_key and manifest.get('audit_key_sha256') and _sha(staged_key) != manifest['audit_key_sha256']:
            raise RuntimeError('Copia temporanea della chiave non valida.')
        try:
            if staged_key: os.replace(staged_key, KEY)
            os.replace(staged_db, target)
        except Exception:
            target.unlink(missing_ok=True)
            if staged_key: KEY.unlink(missing_ok=True)
            raise
    return target
