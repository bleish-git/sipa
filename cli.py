"""Amministrazione SIPA: aggiornamenti espliciti, backup e ripristino."""
import argparse
import json
import os
import sys

# Impostare il target PRIMA di importare i moduli che creano l’engine SQLAlchemy.
if "--target-config" in sys.argv:
    index = sys.argv.index("--target-config")
    if index+1 >= len(sys.argv):
        raise SystemExit("Manca il percorso --target-config")
    os.environ["SIPA_TARGET_CONFIG"] = sys.argv[index+1]
if '--audit-key' in sys.argv:
    index = sys.argv.index('--audit-key')
    if index+1 >= len(sys.argv):
        raise SystemExit('Manca il percorso --audit-key')
    os.environ['SIPA_TARGET_AUDIT_KEY'] = sys.argv[index+1]

from schema import revision, HEAD
from operations import verify_audit, backup, restore, inspect_backup, maintenance_upgrade

p = argparse.ArgumentParser(description='Manutenzione SIPA')
s = p.add_subparsers(dest='command', required=True)
u = s.add_parser('upgrade-db', help='Aggiornamento esplicito con backup preventivo')
u.add_argument('--backup-dir', default=None)
u.add_argument('--target-config', help='JSON del database esterno da aggiornare; non modifica la configurazione attiva')
u.add_argument('--audit-key', help='Chiave audit ORIGINALE del database esterno, se disponibile')
s.add_parser('db-version')
s.add_parser('verify-audit')
b = s.add_parser('backup'); b.add_argument('directory')
i = s.add_parser('inspect-backup'); i.add_argument('file')
r = s.add_parser('restore'); r.add_argument('file'); r.add_argument('--confirm', required=True)
a = p.parse_args()
if a.command == 'upgrade-db':
    from pathlib import Path
    folder = a.backup_dir or str(Path.home() / 'BackupSIPA')
    if a.target_config:
        if a.audit_key:
            from pathlib import Path
            if not Path(a.audit_key).expanduser().is_file():
                raise SystemExit('Chiave audit esterna non trovata.')
        else:
            print('ATTENZIONE: la chiave audit esterna NON è inclusa nel backup. Conservarla separatamente.')
        from db_settings import read_settings
        from schema import revision as target_revision, HEAD
        cfg = read_settings()
        identity = (f"{cfg['driver']}:{cfg['host']}:{cfg['port']}/{cfg['database']}" if cfg['driver']=='postgresql'
                    else 'sqlite:' + cfg['sqlite_path'])
        print('DESTINAZIONE DELLA MIGRAZIONE:', identity)
        print('REVISIONE:', target_revision() or 'non versionato', '→', HEAD)
        if input('Digitare AGGIORNA per procedere (SIPA e client chiusi): ').strip() != 'AGGIORNA':
            raise SystemExit('Operazione annullata.')
    print(json.dumps(maintenance_upgrade(folder), indent=2, ensure_ascii=False))
elif a.command == 'db-version':
    print('Database:', revision() or 'non versionato', '| Programma:', HEAD)
elif a.command == 'verify-audit':
    ok, msg = verify_audit(); print(msg); raise SystemExit(0 if ok else 1)
elif a.command == 'backup': print('Backup:', backup(a.directory))
elif a.command == 'inspect-backup': print(json.dumps(inspect_backup(a.file), indent=2, ensure_ascii=False))
elif a.command == 'restore': print('Ripristino:', restore(a.file, a.confirm))
