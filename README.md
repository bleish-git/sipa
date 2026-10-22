# SIPA — Sistema Informativo Polizia Amministrativa

**Versione 0.5** · Applicazione desktop in Python per la gestione delle attività di polizia amministrativa.

[Repository GitHub — bleish-git/sipa](https://github.com/bleish-git/sipa) · **Licenza MIT**

## Panoramica

SIPA offre un'interfaccia grafica realizzata con **Flet**, utilizza **SQLAlchemy** per l'accesso ai dati e **Alembic** per le migrazioni dello schema. Sono previste configurazioni per **SQLite** e **PostgreSQL**. L'utilizzo con più postazioni e un database centralizzato richiede un'adeguata architettura di distribuzione e la verifica dei controlli di sicurezza.

## Funzionalità disponibili

- **Autenticazione e utenti:** accesso e disconnessione, password protette con PBKDF2 e salt, creazione e gestione degli utenti, disattivazione e riattivazione, reimpostazione password e cambio obbligatorio dopo il reset.
- **Ruoli e autorizzazioni:** quattro ruoli (`admin`, `responsabile`, `operatore`, `consultazione`), permessi granulari e matrice dei permessi modificabile dall'amministratore.
- **Protezione degli accessi:** limitazione dei tentativi ripetuti di autenticazione.
- **Registro attività economiche:** inserimento, elenco, modifica e consultazione; campi nome, titolare, PEC, descrizione, note, data d'inizio e cessazione. Nome attività normalizzato in maiuscolo; ricerca automatica da tre caratteri su nome, titolare, descrizione e note; filtro per stato calcolato dalle date (**Da iniziare**, **Attiva**, **Cessata**).
- **Audit:** registrazione di accessi e operazioni amministrative, con catena HMAC-SHA256 e chiave separata; verifica da terminale.
- **Amministrazione database:** configurazione SQLite/PostgreSQL, controllo della revisione Alembic e aggiornamento esplicito dello schema con backup preventivo.
- **Backup SQLite:** copia coerente tramite API SQLite, controllo d'integrità, impronta SHA256, manifest JSON e copia della chiave audit quando presente.
- **Confronto backup:** analisi del backup e confronto di tabelle e colonne con il database corrente; ripristino offline tramite CLI.

Le voci di navigazione relative a **Sanzioni amministrative**, **Accertamenti** e **Archivio documentale** non implicano che i rispettivi moduli applicativi siano già implementati.

## Requisiti

- Python 3 e ambiente virtuale `venv`.
- Dipendenze indicate in `requirements.txt`: Flet, SQLAlchemy, Alembic e `psycopg` per PostgreSQL.
- Linux Mint/Linux per i comandi qui riportati. Per Windows cambiano i comandi di attivazione dell'ambiente virtuale.
- Per i backup preventivi di PostgreSQL: eseguibile `pg_dump` installato e disponibile nel `PATH`.

## Installazione e comandi operativi

### 1. Installare dipendenze e ambiente Python

Aprire il terminale nella directory del progetto (adattare il percorso):

```bash
cd /home/bleish/Scrivania/sipa
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Per le sessioni successive è sufficiente riattivare l'ambiente con `source .venv/bin/activate`.

### Prima inizializzazione del database e dell'amministratore

In SIPA 0.5 la scelta del motore avviene durante l'inizializzazione, prima della creazione dell'amministratore:

```bash
python main.py --init-admin
```

La procedura richiede SQLite o PostgreSQL e i relativi parametri, verifica la connessione con `SELECT 1`, salva la configurazione e lancia l'aggiornamento esplicito dello schema (con backup preventivo se il database esiste). Infine richiede username e password amministratore di almeno 12 caratteri. Per PostgreSQL occorre predisporre un database raggiungibile e impostare nell'ambiente la variabile della password indicata; servono `pg_dump` e `pg_restore` per i backup prima delle migrazioni. Il motore non può essere modificato successivamente dal menu Amministrazione.

**Installazione su database già esistente:** prima di eseguire qualsiasi aggiornamento, conservare una copia del database e della chiave audit. Controllare la revisione con `python cli.py db-version` e applicare eventuali migrazioni con il comando esplicito `upgrade-db`. Non rieseguire `--init-admin` se l'amministratore esiste già.

### 3. Comandi amministrativi da terminale (`cli.py`)

Eseguire i comandi dalla directory SIPA, con l'ambiente virtuale attivo e, per le operazioni di manutenzione, con l'applicazione chiusa.

| Comando | Funzione |
|---|---|
| `python cli.py db-version` | Visualizza la revisione del database e quella richiesta dal programma. |
| `python cli.py upgrade-db --backup-dir ~/BackupSIPA` | Aggiorna esplicitamente lo schema alla revisione corrente; se serve una migrazione, crea e verifica prima un backup. |
| `python cli.py verify-audit` | Verifica la catena degli eventi di audit. |
| `python cli.py backup ~/BackupSIPA` | Crea un backup manuale SQLite. |
| `python cli.py inspect-backup /percorso/backup.db` | Verifica il backup e confronta la sua struttura con quella del database attuale. |
| `python cli.py restore /percorso/backup.db --confirm 'RIPRISTINA SIPA'` | Ripristina un backup SQLite, solo dopo aver archiviato separatamente database e chiave correnti. |

### Aggiornamenti dello schema con Alembic

La revisione attualmente prevista dal programma è **`0002_attivita_economiche`**. I file delle migrazioni sono conservati in `migrations/versions/` e **devono accompagnare il codice** nelle installazioni e negli aggiornamenti.

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

La sezione **Amministrazione → Configura database** mostra il motore scelto (non modificabile) e consente di aggiornare solo i parametri di connessione, dopo verifica della raggiungibilità. Il modulo di configurazione è **`db_settings.py`**; il file delle impostazioni è **`sipa_database.json`** nella directory SIPA. `db_config.py` non è più richiesto dopo l'applicazione della patch di unificazione della v0.5.

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

Dopo l'inizializzazione e gli eventuali aggiornamenti:

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

**Contatto dell’autore:** `bleish [at] gmail [dot] com` (sostituire `[at]` con `@` e `[dot]` con `.`). L’indirizzo non è un link `mailto:` per ridurre la raccolta automatica più semplice. **L’offuscamento testuale non impedisce ai bot evoluti di ricostruire l’indirizzo**; per minimizzare lo spam, è preferibile usare le *Issues* del repository GitHub per richieste pubbliche e riservare l’email ai contatti privati.

L’avviso di copyright e il testo della licenza MIT nel file `LICENSE` devono rimanere integri nelle redistribuzioni; l’indirizzo email qui indicato non modifica i termini della licenza.
