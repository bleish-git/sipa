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
- Utenti: creazione, modifica ruolo, disattivazione/riattivazione, reimpostazione password temporanea.
- Cambio password personale, richiesta di cambio password al primo accesso dopo reset.
- Ruoli `admin` e `operatore`; sezione Amministrazione riservata all'amministratore.
- Eventi di login e gestione utenti salvati nel database.
- Logo su login e sidebar, icone `assets/sipa-icon.png` e `assets/sipa.ico`.

## Database

Usa SQLAlchemy per la persistenza. `SIPA_DB_URL` seleziona il database (default SQLite). 
Non basta cambiare l'URL per migrare i dati: serviranno migrazioni SQL.


## Packaging Windows (da Windows)

Per una build Windows, su una macchina Windows installare le dipendenze e provare `flet build windows` secondo la documentazione della versione Flet installata. 

## Limiti di sicurezza

**Solo prototipo con dati fittizi.** Mancano: limitazione dei tentativi di accesso, sessioni centralizzate e revoca, protezione da accessi concorrenti distribuiti, permessi granulari, audit anti-manomissione, procedure di backup e ripristino, TLS.  L'interfaccia Flet non sostituisce controlli di autorizzazione sul server quando si usano client multipli. 
Il registro eventi è locale e modificabile da chi abbia accesso diretto al file SQLite.
