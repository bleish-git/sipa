"""Preparazione aggiornamento offline su database non attivo, senza cambiare la configurazione SIPA."""
import json
import os
import uuid
from pathlib import Path
from db_settings import CONFIG, _normalized

PENDING_DIR = CONFIG.parent / 'SIPA_aggiornamenti_in_attesa'


def prepare(values, revision, required):
    cfg = _normalized(values)
    PENDING_DIR.mkdir(exist_ok=True)
    path = PENDING_DIR / ('destinazione_' + uuid.uuid4().hex[:12] + '.json')
    with path.open('x', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.chmod(path, 0o600)
    return path


def instructions(path, current, required):
    return (f'Revisione database: {current or "non versionato"}; SIPA richiede: {required}.\n'
            'Il collegamento NON è stato cambiato e il database NON è stato modificato.\n'
            'Chiudere SIPA e tutti i client, poi eseguire da terminale:\n'
            f'python cli.py upgrade-db --target-config "{path}" --backup-dir "BackupSIPA"\n'
            'Il comando chiederà conferma dell’identità del database e farà un backup preventivo.\n'
            'Dopo l’aggiornamento riaprire SIPA e ripetere il collegamento.\n'
            'Se esiste una migrazione distruttiva, servirà una conferma aggiuntiva specifica.')


def incompatible(values, exc):
    """Riconosce SOLO un errore reale di mismatch, non errori di accesso o di struttura."""
    import re
    from setup_wizard import EXPECTED_REVISION
    msg = str(exc)
    m = re.search(r'Revisione incompatibile: database (.*?), SIPA richiede ([\w_]+)', msg)
    if not m:
        return None
    actual, expected = m.group(1), m.group(2)
    if expected != EXPECTED_REVISION:
        return None
    # Non suggerire un upgrade se la revisione non è nota (può essere più recente).
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    versions = {r.revision for r in ScriptDirectory.from_config(Config(str(CONFIG.parent/'alembic.ini'))).walk_revisions()}
    if actual not in versions:
        return msg + '\nIl database potrebbe essere più recente; usare una versione SIPA compatibile.'
    if actual == EXPECTED_REVISION:
        return None
    path = prepare(values, actual, expected)
    return msg + '\n\n' + instructions(path, actual, expected)
