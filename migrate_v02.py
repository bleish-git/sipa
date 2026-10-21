"""One-time additive migration from SIPA v0.2 SQLite schema. Run with SIPA stopped."""
import sqlite3
from pathlib import Path
from database import BASE_DIR, init_database

def migrate():
    path = BASE_DIR / 'sipa.db'
    if not path.exists():
        init_database()
        return
    with sqlite3.connect(path) as conn:
        for table, columns in {
            'users': [('failed_attempts', 'INTEGER NOT NULL DEFAULT 0'), ('locked_until', 'DATETIME')],
            'audit_events': [('previous_hash', "VARCHAR(64) NOT NULL DEFAULT ''"), ('entry_hash', "VARCHAR(64) NOT NULL DEFAULT ''")]
        }.items():
            existing = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            for column, typ in columns:
                if column not in existing:
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {typ}')
        conn.commit()
    init_database()
    print('Schema aggiornato. ATTENZIONE: vecchi eventi v0.2 non sono concatenati; archiviarli separatamente prima della migrazione.')
if __name__ == '__main__':
    migrate()
