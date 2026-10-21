import argparse, json
from schema import upgrade, revision
from operations import verify_audit, backup, restore, inspect_backup

p=argparse.ArgumentParser(description='Manutenzione SIPA')
s=p.add_subparsers(dest='command',required=True)
s.add_parser('upgrade-db'); s.add_parser('db-version'); s.add_parser('verify-audit')
b=s.add_parser('backup');b.add_argument('directory')
i=s.add_parser('inspect-backup');i.add_argument('file')
r=s.add_parser('restore');r.add_argument('file');r.add_argument('--confirm',required=True)
a=p.parse_args()
if a.command=='upgrade-db': upgrade();print('Schema aggiornato:',revision())
elif a.command=='db-version':print(revision() or 'non versionato')
elif a.command=='verify-audit':
    ok,msg=verify_audit();print(msg);raise SystemExit(0 if ok else 1)
elif a.command=='backup':print('Backup:',backup(a.directory))
elif a.command=='inspect-backup':print(json.dumps(inspect_backup(a.file),indent=2,ensure_ascii=False))
elif a.command=='restore':print('Ripristino:',restore(a.file,a.confirm))
