"""Guida visualizzata nel menu Amministrazione."""
DB_ADMIN_GUIDE = '''SIPA 0.55 — GUIDA DATABASE E MANUTENZIONE

REGOLE DI COMPATIBILITÀ
• Il database collegato deve avere la revisione Alembic esattamente uguale a quella richiesta dall'applicazione. Non sono ammessi DB più vecchi o più nuovi durante l'uso normale.
• La procedura Collega esistente verifica raggiungibilità, tabelle, colonne, revisione, utenti, credenziali admin e catena audit senza scrivere sul DB.
• Un backup di revisione precedente si ripristina SOLO offline e poi si aggiorna con Alembic prima dell'avvio. Una revisione più nuova richiede un software corrispondente: NON effettuare downgrade automatici.
• Cambiare collegamento NON importa, combina o trasferisce i dati.

OPERAZIONE                      DOVE                   MODIFICA / CONTROLLI
--------------------------------------------------------------------------------
Configura database             APP + RIAVVIO          Prova connessione, struttura, revisione ESATTA, utenti, credenziali amministrative e audit; salva SOLO impostazioni locali e relativa chiave. Motore invariato.

Genera backup                 APP                    SQLite: snapshot consistente .db; PostgreSQL: dump .sql in testo (dialetto PostgreSQL, con INSERT espliciti). Crea manifest SHA256 e copia protetta chiave audit; non modifica il database sorgente.

Verifica / confronta backup    APP                    SQLite: verifica SHA256, integrità e confronta tabelle/colonne. PostgreSQL: verifica file SQL, manifest, revisione e chiave; NON confronta ancora tutte le colonne. Solo lettura.

Aggiorna schema                SOLO CLI, APP CHIUSA    db-version; upgrade-db con backup obbligatorio verificato e migrazioni Alembic. Modifica LO SCHEMA (e i dati, se previsti dalla migrazione). Nessun downgrade automatico.

Ripristina backup              SOLO CLI, APP CHIUSA    restore con conferma testuale. SQLite: destinazione DB e chiave assenti; PostgreSQL: database di destinazione VUOTO. Sostituisce il contenuto con quello del backup; nessuna fusione dei dati. Dopo ripristino, revisionare/aggiornare e verificare prima di avviare.

Nuovo collegamento             APP + RIAVVIO          Usare Configura database per stesso motore. Il passaggio da SQLite a PostgreSQL richiede nuova configurazione iniziale a programma chiuso (archiviando configurazione e chiave); NON trasferisce automaticamente i record.

Installazione nuovo PC         AVVIO INIZIALE         main.py senza configurazione → Collega esistente. Non eseguire una nuova inizializzazione degli utenti e non aggiornare lo schema da ogni PC.

COMANDI NELLA CARTELLA SIPA
python cli.py db-version
python cli.py verify-audit
python cli.py backup ~/BackupSIPA
python cli.py inspect-backup /percorso/backup.db
python cli.py inspect-backup /percorso/backup.sql
python cli.py upgrade-db --backup-dir ~/BackupSIPA
python cli.py restore /percorso/backup.db --confirm "RIPRISTINA SIPA"
python cli.py restore /percorso/backup.sql --confirm "RIPRISTINA SIPA"

ATTENZIONE
• Prima di manutenzione/ripristino fermare SIPA e ogni altro client e archiviare configurazione, DB e chiave audit. Per PostgreSQL predisporre un database realmente vuoto e accessibile con permessi adeguati.
• L'SQL esportato con pg_dump è leggibile e contiene INSERT espliciti, ma non è SQL ANSI portabile su qualsiasi motore: il ripristino è progettato per PostgreSQL.
• PostgreSQL SQL dump: la verifica SHA256 NON equivale a una prova completa di ripristino. Effettuare prove periodiche in un ambiente separato.
• SQLite su NAS/SMB e accessi concorrenti da più PC NON consigliati; usare PostgreSQL centralizzato.
• Tutte le operazioni di ripristino riportano i dati al momento della copia: gli inserimenti successivi non verranno recuperati automaticamente.
'''
