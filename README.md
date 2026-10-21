# SIPA v0.3 — Sicurezza (prototipo)

**Solo dati fittizi.** Non ancora autorizzato per dati amministrativi reali.

## Avvio su Linux Mint

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --init-admin
python main.py
```

Se hai già un database v0.2: **prima chiudi SIPA e fai una copia di `sipa.db`**. Esegui `python migrate_v02.py`. La migrazione è additiva ma **gli eventi di audit precedenti non erano firmati**: conservali come archivio storico separato; per avere una catena verificabile dalla genesi si consiglia un database nuovo per v0.3. Non sostituire la chiave `.sipa_audit_key`.

## Controlli aggiunti

- **Rate limit per account**: dopo 5 credenziali errate, blocco di 15 minuti condiviso tra processi che usano lo stesso database. Il messaggio di login non rivela l'esistenza dell'utente. In SQLite `BEGIN IMMEDIATE` serializza gli aggiornamenti di autenticazione. Non protegge da attacchi distribuiti su molti account: in produzione aggiungere rate limit per IP/rete e controllo perimetrale su un'API centrale.
- **Ruoli e permessi**: admin, responsabile, operatore, consultazione; `permissions` e `role_permissions`. La UI filtra i settori, mentre i metodi amministrativi verificano i permessi nel database. Ogni futuro endpoint CRUD dovrà verificare il permesso appropriato **sul server**, non fidarsi del client.
- **Audit**: catena HMAC-SHA256 con chiave separata `.sipa_audit_key` (da proteggere e conservare anche nei backup). Verifica `python cli.py verify-audit`. Non è un registro WORM: chi controlla DB e chiave può riscrivere la catena. Per una vera difesa anti-manomissione servono invio dei log a sistema indipendente, controlli di accesso, marcatura temporale o storage immutabile e monitoraggio. Le scritture audit vanno serializzate anche sul DB server.
- **Backup SQLite**: `python cli.py backup /percorso/backup` utilizza API SQLite online backup, controllo `integrity_check`, checksum SHA256 e copia della chiave audit. La cartella backup deve essere separata e protetta; conservarne copie offline/immutabili e provare i ripristini.
- **Ripristino**: spegnere TUTTE le istanze, conservare copia del database attuale, spostare manualmente `sipa.db` fuori dalla cartella del programma; poi `python cli.py restore /percorso/backup/sipa_YYYYMMDDTHHMMSSZ.db --confirm 'RIPRISTINA SIPA'`. Il ripristino rifiuta di sovrascrivere un database esistente. Ripristina anche la chiave audit corrispondente.

## Limitazioni importanti

1. La v0.3 non è un sistema distribuito: SQLite resta locale. Su QNAP servirà PostgreSQL + API centralizzata con TLS, gestione sessioni, rate limit per IP e account, autorizzazioni server-side e backup PostgreSQL dedicati.
2. I tentativi distribuiti contro nomi utente differenti non sono mitigati dal solo rate limit per account. Il controllo IP deve usare l'indirizzo verificato dalla connessione server, non intestazioni client arbitrarie.
3. La catena audit è **tamper-evident locale**, non immutabile. Un amministratore che controlla anche la chiave può modificarla.
4. Il backup SQLite include solo il DB e la chiave audit, **non** gli allegati SMB, le impostazioni QNAP o i segreti del futuro server.
5. Non memorizzare la chiave di audit nella stessa directory pubblicamente accessibile del database. In produzione separare privilegi, backup e segreti.
6. Le sessioni UI della versione dimostrativa non sono ancora token server-side e non offrono revoca immediata centralizzata.
7. La modifica dei permessi è applicata nei controlli attuali e nei futuri controlli di accesso, non conferisce sicurezza a moduli ancora inesistenti.
