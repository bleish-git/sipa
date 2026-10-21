# SIPA — Sistema Informativo Polizia Amministrativa (v0.2)

Prototipo locale per Linux Mint, Python + Flet + SQLAlchemy + SQLite. 



```bash
cd SIPA
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py --init-admin
python main.py
```

La prima inizializzazione crea l'utente amministratore chiedendo nome e password (minimo 12 caratteri). Non esistono password predefinite. Il database viene creato come `sipa.db` nella cartella del progetto.

## Funzioni iniziali

- Login/logout, hash PBKDF2 con salt per le password.
- Utenti: creazione, modifica ruolo, disattivazione/riattivazione, reimpostazione password temporanea, cambio password personale, richiesta di cambio password al primo accesso dopo reset;
- Permessi granulari con 4 ruoli (admin, responsabile, operatore, consultazione); sezione Amministrazione riservata all'amministratore.
- Eventi di login e gestione utenti salvati nel database.
- Audit: catena HMAC-SHA256 con chiave separata. Verifica `python cli.py verify-audit`. Non è un registro WORM: chi controlla DB e chiave può riscrivere la catena. Per una vera difesa anti-manomissione servono invio dei log a sistema indipendente, controlli di accesso, marcatura temporale o storage immutabile e monitoraggio. 
- Backup DB: `python cli.py backup /percorso/backup` utilizza API SQLite online backup, controllo `integrity_check`, checksum SHA256 e copia della chiave audit. 
- Ripristino: `python cli.py restore /percorso/backup/sipa_YYYYMMDDTHHMMSSZ.db --confirm 'RIPRISTINA SIPA'`. Il ripristino rifiuta di sovrascrivere un database esistente. Ripristina anche la chiave audit corrispondente.


## Database

Usa SQLAlchemy per la persistenza. `SIPA_DB_URL` seleziona il database (default SQLite). 
Non basta cambiare l'URL per migrare i dati: serviranno migrazioni SQL.


## Packaging Windows (da Windows)

Per una build Windows, su una macchina Windows installare le dipendenze e provare `flet build windows` secondo la documentazione della versione Flet installata. 

## Limiti del prototipo
1. Non è un sistema distribuito: SQLite resta locale. Servirà PostgreSQL + API centralizzata con TLS, gestione sessioni, rate limit per IP e account, autorizzazioni server-side e backup PostgreSQL dedicati.
2. I tentativi distribuiti contro nomi utente differenti non sono mitigati dal solo rate limit per account. Il controllo IP deve usare l'indirizzo verificato dalla connessione server, non intestazioni client arbitrarie.
3. La catena audit è **tamper-evident locale**, non immutabile. Un amministratore che controlla anche la chiave può modificarla.
4. Il backup SQLite include solo il DB e la chiave audit.
5. Non memorizzare la chiave di audit nella stessa directory pubblicamente accessibile del database. In produzione separare privilegi, backup e segreti.
6. Le sessioni UI della versione dimostrativa non sono ancora token server-side e non offrono revoca immediata centralizzata.
7. La modifica dei permessi è applicata nei controlli attuali e nei futuri controlli di accesso, non conferisce sicurezza a moduli ancora inesistenti.

