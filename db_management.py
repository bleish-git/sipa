"""Funzioni amministrative: collegamento verificato e configurazione protetta."""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from db_settings import CONFIG, read_settings, save_settings
from setup_wizard import inspect_existing

KEY = CONFIG.parent / '.sipa_audit_key'


def connect_existing(values, username, password, audit_key_path=None):
    """Verifica il target senza scriverlo; archivia la configurazione corrente.

    Il file di configurazione/chiave viene aggiornato solo dopo tutte le verifiche;
    in caso di errore prova a riportare in uso quelli precedenti.
    """
    result = inspect_existing(values, username, password, audit_key_path)
    original = read_settings()
    if values['driver'] != original['driver']:
        raise ValueError('Per cambiare motore usa la procedura iniziale offline in una nuova installazione; non è una migrazione dei dati.')
    source = result.get('audit_key_source')
    if source:
        newkey = Path(source).read_bytes()
    else:
        newkey = None
    previous_config = CONFIG.read_bytes() if CONFIG.exists() else None
    previous_key = KEY.read_bytes() if KEY.exists() else None
    # Conserva copia della precedente configurazione e chiave fuori dalla directory DB.
    archive = CONFIG.parent / 'SIPA_config_history' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive.mkdir(parents=True, mode=0o700)
    os.chmod(archive, 0o700)
    if previous_config is not None:
        (archive / 'sipa_database.json').write_bytes(previous_config)
        os.chmod(archive / 'sipa_database.json', 0o600)
    if previous_key is not None:
        (archive / '.sipa_audit_key').write_bytes(previous_key)
        os.chmod(archive / '.sipa_audit_key', 0o600)
    try:
        if newkey is not None:
            tmpkey = KEY.with_name('.sipa_audit_key.tmp')
            with tmpkey.open('wb') as f:
                f.write(newkey)
            os.chmod(tmpkey, 0o600)
            os.replace(tmpkey, KEY)
        elif KEY.exists():
            # Un DB privo di audit non deve usare la chiave di un altro DB.
            KEY.unlink()
        save_settings(values)
    except Exception:
        if previous_config is not None:
            CONFIG.write_bytes(previous_config)
            os.chmod(CONFIG, 0o600)
        else:
            CONFIG.unlink(missing_ok=True)
        if previous_key is not None:
            KEY.write_bytes(previous_key)
            os.chmod(KEY, 0o600)
        else:
            KEY.unlink(missing_ok=True)
        raise
    return {'revision': result['revision'], 'users': result['users'], 'previous_settings': str(archive), 'restart_required': True}
