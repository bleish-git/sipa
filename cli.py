import argparse
from database import init_database
from operations import verify_audit, backup, restore

p = argparse.ArgumentParser(description='Operazioni di manutenzione SIPA')
s = p.add_subparsers(dest='command', required=True)
s.add_parser('verify-audit')
b = s.add_parser('backup'); b.add_argument('directory')
r = s.add_parser('restore'); r.add_argument('file'); r.add_argument('--confirm', required=True)
a = p.parse_args()
if a.command == 'verify-audit':
    ok, msg = verify_audit()
    print(msg)
    raise SystemExit(0 if ok else 1)
if a.command == 'backup':
    print('Backup creato:', backup(a.directory))
if a.command == 'restore':
    print('Ripristino completato:', restore(a.file, a.confirm))
