## SIPA — Sistema Informativo Polizia Amministrativa 

**Versione 0.60** · Applicazione desktop in Python per la gestione delle attività di polizia amministrativa.

[Repository GitHub — bleish-git/sipa](https://github.com/bleish-git/sipa) · **Licenza MIT**

**Work in progress**

## Panoramica

SIPA (Sistema Informativo Polizia Amministrativa) è un’applicazione desktop pensata per supportare le attività amministrative e di controllo degli uffici.
Il sistema prevede accessi con ruoli e autorizzazioni differenziati, tracciamento delle operazioni e strumenti per il backup e l’aggiornamento. Può utilizzare SQLite per installazioni locali o PostgreSQL per una base dati centralizzata.
Il progetto è sviluppato in Python con interfaccia Flet ed è organizzato in moduli, per consentire l’introduzione progressiva di nuove funzioni e l’evoluzione delle procedure operative.

## Funzionalità disponibili

Generali:
- **Autenticazione e utenti:** 
- **Ruoli e autorizzazioni:** quattro ruoli (`admin`, `responsabile`, `operatore`, `consultazione`), permessi granulari 
- **Audit:** registrazione di accessi e operazioni amministrative, con catena HMAC-SHA256 e chiave separata; verifica da terminale.
- **Amministrazione database:** configurazione SQLite/PostgreSQL, controllo della revisione Alembic e aggiornamento esplicito dello schema con backup preventivo.
- **Backup SQLite e PostgreSQL:** 

Specifiche:
- **Gestione presenze Mercatino**
- **Gestione anagrafica attività economiche**

Alcune voci di navigazione non sono implementate e sono in corso di programmazione

## Requisiti

- Python 3 e ambiente virtuale `venv`.
- Dipendenze indicate in `requirements.txt`: Flet, SQLAlchemy, Alembic e `psycopg` per PostgreSQL o altro per SQLite.
- Linux Mint/Linux per i comandi qui riportati. Per Windows cambiano i comandi di attivazione dell'ambiente virtuale.
- Per i backup PostgreSQL: `pg_dump` nel `PATH`; per il ripristino PostgreSQL: anche `psql`. Il dump in testo è destinato a PostgreSQL.

## Installazione e comandi operativi

### 1. Installare dipendenze e ambiente Python

Aprire il terminale nella directory del progetto (adattare il percorso):

```bash
cd /home/bleish/Scrivania/sipa
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Per produrre le stampe PDF è necessaria anche la dipendenza `reportlab`, installata da `requirements.txt`. Per le sessioni successive è sufficiente riattivare l'ambiente con `source .venv/bin/activate`.

### 2. Prima configurazione grafica o da terminale

Con `python main.py`, se `sipa_database.json` è già presente SIPA si avvia normalmente, dopo il controllo della versione dello schema. Se il file manca si apre automaticamente la **configurazione guidata grafica**.

La procedura chiede prima username e password amministrativi, poi consente di scegliere:

- **Crea nuovo database:** crea lo schema in un file SQLite nuovo, oppure su un database PostgreSQL predisposto e vuoto; crea il primo amministratore (password di almeno 12 caratteri).
- **Collega database esistente:** controlla connessione, tabelle e colonne richieste, revisione Alembic, presenza degli utenti e credenziali di un account amministratore già presente. Il controllo è in sola lettura: nessuna migrazione, scrittura o creazione di utenti. Uno schema incompatibile viene rifiutato.

È possibile configurare **SQLite** oppure **PostgreSQL**. Per SQLite viene mostrato l'avviso che **non è consigliato l'uso del file su condivisioni di rete o con client concorrenti**. Per PostgreSQL occorre rendere disponibile sul PC la variabile d'ambiente contenente la password del server (predefinita `SIPA_PG_PASSWORD`).

Alla conclusione della configurazione, chiudere la finestra e **riavviare SIPA**.

La stessa procedura è disponibile da terminale senza interfaccia grafica:

```bash
python main.py --init-admin
```

**Secondo PC:** installare SIPA, eseguire `python main.py`, selezionare **Collega database esistente**, inserire i parametri e autenticarsi con un amministratore già registrato. Se il database ha registrazioni audit, fornire anche la chiave `.sipa_audit_key` originale tramite percorso locale sicuro: la procedura ne verifica la corrispondenza senza cambiare il database e ne conserva una copia protetta nella cartella SIPA. Non creare una nuova chiave per un archivio già utilizzato. Non scegliere «Crea nuovo» e non effettuare migrazioni su ogni client.

**Installazione già funzionante:** conservando `sipa_database.json` SIPA non avvia la procedura iniziale; nessuna reinizializzazione è richiesta.

### 3. Comandi amministrativi da terminale (`cli.py`)

Eseguire i comandi dalla directory SIPA, con l'ambiente virtuale attivo e, per le operazioni di manutenzione, con l'applicazione chiusa.

| Comando | Funzione |
|---|---|
| `python cli.py db-version` | Visualizza la revisione del database e quella richiesta dal programma. |
| `python cli.py upgrade-db --backup-dir ~/BackupSIPA` | Aggiorna esplicitamente lo schema alla revisione corrente; se serve una migrazione, crea e verifica prima un backup. |
| `python cli.py verify-audit` | Verifica la catena degli eventi di audit. |
| `python cli.py backup ~/BackupSIPA` | SQLite: `.db`; PostgreSQL: `.sql` in testo, con manifest SHA256 e chiave audit. |
| `python cli.py inspect-backup /percorso/backup.db` | Verifica il backup e confronta la sua struttura con quella del database attuale. |
| `python cli.py restore /percorso/backup.db --confirm 'RIPRISTINA SIPA'` | Ripristina SQLite solo con DB e chiave correnti archiviati e assenti dalla destinazione. |
| `python cli.py restore /percorso/backup.sql --confirm 'RIPRISTINA SIPA'` | Ripristina PostgreSQL esclusivamente su un database PostgreSQL VUOTO, configurato come destinazione, con SIPA chiuso. |

### Aggiornamenti dello schema con Alembic

La revisione attualmente prevista dal programma è **`0005_presenze_ordine`**. I file delle migrazioni sono conservati in `migrations/versions/` e **devono accompagnare il codice** nelle installazioni e negli aggiornamenti.

```bash
python cli.py db-version
python cli.py upgrade-db --backup-dir ~/BackupSIPA
python cli.py db-version
```

Se lo schema è già aggiornato, `upgrade-db` non applica migrazioni e non crea un nuovo backup. Se invece è necessario aggiornare, il backup preventivo viene eseguito prima delle modifiche. Per SQLite la copia comprende database e, se disponibile, chiave audit; per PostgreSQL l'aggiornamento utilizza `pg_dump` in formato personalizzato.

**Nota:** una migrazione modifica la struttura dei dati, non trasferisce automaticamente i record da SQLite a PostgreSQL. Il ripristino di un backup con schema precedente può richiedere un successivo aggiornamento Alembic.

### Backup e ripristino SQLite

Il backup manuale produce un file `.db`, un manifest `.json` con checksum SHA256 e, quando presente, un file `.auditkey`. Conservare i file insieme, in un luogo protetto e preferibilmente su un supporto diverso da quello del database principale.

Il ripristino **non sovrascrive** automaticamente il database in uso. Chiudere SIPA, archiviare in un luogo sicuro il database corrente e la sua chiave audit, verificare il backup e soltanto dopo lanciare il comando `restore`. Evitare operazioni concorrenti da altre postazioni.

## Impostazioni del database

La sezione **Amministrazione → Configura database** mostra il motore scelto (non modificabile), richiede le credenziali di un amministratore del database di destinazione e verifica connessione, tabelle, colonne, revisione ESATTA, utenti e audit senza modificare il database prima di salvare la configurazione locale. Il riavvio è obbligatorio. Il modulo di configurazione è **`db_settings.py`**; il file delle impostazioni è **`sipa_database.json`** nella directory SIPA. Ogni postazione mantiene la propria configurazione locale.

**SQLite:** percorso del file `.db`. È la configurazione predefinita, adatta all'uso locale. Non utilizzare un file SQLite condiviso via SMB come database concorrente per più client.

**PostgreSQL:** host, porta (predefinita `5432`), nome del database, utente, nome della variabile d'ambiente contenente la password e modalità TLS (`require`, `verify-ca`, `verify-full`). La password non viene scritta nel JSON di configurazione.

Esempio Linux, utilizzando il nome predefinito della variabile d'ambiente:

```bash
export SIPA_PG_PASSWORD='password_da_impostare_localmente'
python main.py
```

L'ambiente deve contenere la variabile anche quando vengono eseguiti i comandi `cli.py`. La configurazione attiva è letta dal file `sipa_database.json`; non sono previsti override tramite URL ambientali.

**La selezione del motore non importa né converte i dati esistenti.** Prima di usare PostgreSQL con dati operativi, verificare connettività, certificati TLS, permessi, backup, ripristino e compatibilità delle migrazioni.

## Avvio dell'applicazione

Dopo la configurazione e gli eventuali aggiornamenti:

```bash
cd /home/bleish/Scrivania/sipa
source .venv/bin/activate
python main.py
```

Accedere con l'account amministratore creato durante la prima inizializzazione. Se SIPA segnala che la revisione del database non è aggiornata, chiudere il programma ed eseguire `python cli.py upgrade-db --backup-dir ~/BackupSIPA` prima di riprovare.

## Distribuzione su Windows

Per predisporre una build Windows, installare le dipendenze su una macchina Windows e consultare la documentazione della versione Flet installata per il comando `flet build windows`. Prima della distribuzione verificare i percorsi di configurazione, le dipendenze e l'accesso al database.

## Sicurezza e gestione operativa

- La catena audit è **tamper-evident**, non un archivio immutabile (WORM): chi controlla database e chiave può teoricamente ricostruirla. Per una protezione più forte occorrono conservazione esterna, privilegi separati e monitoraggio.
- Limitare l'accesso ai file `sipa_database.json`, `.sipa_audit_key`, al database e ai backup; proteggere i segreti e non inserirli nel repository Git.
- Il backup SQLite riguarda il database e la chiave audit; eventuali documenti o allegati conservati esternamente richiedono un piano di backup separato.
- Il confronto del backup riguarda principalmente la struttura delle tabelle e delle colonne, non le differenze tra singoli record.
- Per l'utilizzo da più postazioni occorre definire e collaudare un'architettura centralizzata con autorizzazioni lato server, gestione delle sessioni, protezione TLS, controlli sugli accessi e procedure di disaster recovery.
- Pianificare backup periodici, conservazione delle copie e prove effettive di ripristino: il solo checksum non garantisce la recuperabilità dell'intero sistema.

## Licenza, copyright e contatti

**© 2026 [bleish](https://github.com/bleish-git/sipa)** — SIPA, Sistema Informativo Polizia Amministrativa.

Il codice del progetto è distribuito secondo la **licenza MIT**, riportata nel file [`LICENSE`](LICENSE). La licenza permette uso, modifica e redistribuzione, anche commerciale, purché siano mantenuti gli avvisi di copyright e di licenza previsti dal testo MIT. Le dipendenze di terze parti restano soggette alle rispettive licenze.

Repository ufficiale: **https://github.com/bleish-git/sipa**.

**Contatto dell’autore:** `bleish [at] gmail [dot] com` (sostituire `[at]` con `@` e `[dot]` con `.`). 
L’avviso di copyright e il testo della licenza MIT nel file `LICENSE` devono rimanere integri nelle redistribuzioni; l’indirizzo email qui indicato non modifica i termini della licenza.