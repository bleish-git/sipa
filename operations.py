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

def backup(destination):
    source = _sqlite_path()
    if not source.exists():
        raise FileNotFoundError(source)
    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if dest == source.parent:
        raise ValueError('Usare una directory di backup separata dal database.')
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = dest / f'sipa_{stamp}.db'
    if target.exists():
        raise FileExistsError(target)
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Integrità backup fallita')
    key_dest = dest / f'sipa_{stamp}.auditkey'
    if KEY.exists():
        shutil.copy2(KEY, key_dest)
        os.chmod(key_dest, 0o600)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {'database':target.name, 'sha256':digest,
                'audit_key':key_dest.name if KEY.exists() else None}
    (dest / f'sipa_{stamp}.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return target

def restore(backup_file, confirmation):
    if confirmation != 'RIPRISTINA SIPA':
        raise ValueError('Conferma esplicita mancante.')
    source = Path(backup_file).expanduser().resolve()
    manifest_path = source.with_suffix('.json')
    if not manifest_path.exists():
        raise ValueError('Manifest del backup non trovato.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['database'] != source.name or hashlib.sha256(source.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Hash backup non corrispondente.')
    with sqlite3.connect(str(source)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup SQLite corrotto.')
    target = _sqlite_path()
    # IMPORTANT: run restore only when ALL SIPA processes are stopped.
    if target.exists():
        raise RuntimeError('Rimuovere o rinominare il DB corrente A SIPA SPENTO, dopo averne fatto una copia. Ripristino non eseguito.')
    shutil.copy2(source, target)
    if manifest.get('audit_key'):
        key_source = source.parent / manifest['audit_key']
        if not key_source.exists():
            raise ValueError('Chiave audit del backup assente')
        shutil.copy2(key_source, KEY)
        os.chmod(KEY, 0o600)
    return target
