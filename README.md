# SIPA — Sistema Informativo Polizia Amministrativa (v0.2)

Prototipo locale per Linux Mint, Python + Flet + SQLAlchemy + SQLite. Contiene il logo fornito dall'utente e l'icona PNG/ICO ottenuta dal logo originale. Non inserire dati amministrativi reali.

## Avvio su Linux Mint

```bash
cd SIPA
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py --init-admin
python main.py
```

La prima inizializzazione crea l'utente amministratore chiedendo nome e password (minimo 12 caratteri). Non esistono password predefinite. Il database viene creato come `sipa.db` nella cartella del progetto.

## Funzioni fase 2

- Login/logout, hash PBKDF2 con salt per le password.
- Utenti: creazione, modifica ruolo, disattivazione/riattivazione, reimpostazione password temporanea.
- Cambio password personale, richiesta di cambio password al primo accesso dopo reset.
- Ruoli `admin` e `operatore`; sezione Amministrazione riservata all'amministratore.
- Eventi di login e gestione utenti salvati nel database.
- Logo su login e sidebar, icone `assets/sipa-icon.png` e `assets/sipa.ico`.

## Database e migrazione dalla v0.1

Usa SQLAlchemy per la persistenza. `SIPA_DB_URL` seleziona il database (default SQLite). Non basta cambiare l'URL per migrare i dati: in futuro serviranno migrazioni SQL e un'API centrale sul NAS QNAP. **Non mettere SQLite in una cartella SMB condivisa tra più PC.**

La v0.1 precedente usava `gestionale.db`. Questa versione usa `sipa.db` nuovo e non importa automaticamente gli account della v0.1. Non copiare o rinominare il vecchio database: la struttura è diversa. Se desideri conservare gli account esistenti, prima di procedere servirà una migrazione esplicita con backup.

## Packaging Windows (da Windows)

Per una futura build Windows, su una macchina Windows installare le dipendenze e provare `flet build windows` secondo la documentazione della versione Flet installata. Il file `assets/sipa.ico` è pronto per l'icona dell'eseguibile, ma il packaging non è stato ancora verificato.

## Limiti di sicurezza

**Solo prototipo con dati fittizi.** Mancano: limitazione dei tentativi di accesso, sessioni centralizzate e revoca, protezione da accessi concorrenti distribuiti, permessi granulari, audit anti-manomissione, procedure di backup e ripristino, TLS, autorizzazioni e validazione da parte del servizio IT comunale. L'interfaccia Flet non sostituisce controlli di autorizzazione sul server quando si passerà a client multipli. Il registro eventi è locale e modificabile da chi abbia accesso diretto al file SQLite.
