"""Configurazione iniziale, connessione verificata e creazione amministratore."""
import os
import subprocess
import sys
from pathlib import Path
from db_settings import CONFIG, read_settings, save_settings, test_connection


def init_admin():
    current = read_settings()
    existing = CONFIG.exists()
    print('SIPA 0.5 — inizializzazione amministrativa')
    print('Configurazione già presente: il motore non è modificabile.' if existing else 'Selezionare il database prima di inizializzare.')
    driver = current['driver'] if existing else (input('Motore [sqlite/postgresql] (sqlite): ').strip().lower() or 'sqlite')
    if driver not in ('sqlite', 'postgresql'):
        raise SystemExit('Motore non valido.')
    values = dict(current, driver=driver)
    if driver == 'sqlite':
        values['sqlite_path'] = input(f"Percorso SQLite [{current['sqlite_path']}]: ").strip() or current['sqlite_path']
    else:
        for key, title in [('host','Host'),('port','Porta'),('database','Database'),('username','Utente'),('password_env','Variabile ambiente password'),('sslmode','TLS (require/verify-ca/verify-full)')]:
            values[key] = input(f'{title} [{current[key]}]: ').strip() or current[key]
        print(f"La password viene letta dalla variabile {values['password_env']} (non salvata su disco).")
    print('Verifica configurazione e connessione...')
    test_connection(values, allow_new_sqlite=(driver == 'sqlite' and not existing))
    if existing and values['driver'] != current['driver']:
        raise SystemExit('Cambio motore non consentito.')
    save_settings(values, initial=not existing)
    print('Connessione verificata. Controllo revisione e aggiornamento esplicito...')
    folder = str(Path.home() / 'BackupSIPA')
    subprocess.run([sys.executable, str(Path(__file__).parent / 'cli.py'), 'upgrade-db', '--backup-dir', folder], check=True)
    print('Creazione amministratore (se non già presente)...')
    subprocess.run([sys.executable, str(Path(__file__).parent / 'main.py'), '--bootstrap-only'], check=True)
