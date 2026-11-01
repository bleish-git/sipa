# SIPA v0.60 — Gestione anagrafiche e bozze Mercatino

> **ATTENZIONE: la migrazione `0007_mercatino_ristrutturazione` elimina definitivamente tutti i dati del modulo Mercatino.** Gli altri moduli, utenti, permessi e audit non vengono azzerati. Le istruzioni del Mercatino delle versioni 0.57–0.59 riportate più sotto sono solo storiche e non si applicano alla v0.60.

## Procedura di aggiornamento da v0.59

1. Arrestare SIPA su **tutte** le postazioni collegate al database.
2. Conservare una copia dell'installazione. Sostituire i file della patch, inclusa `migrations/versions/0007_mercatino_ristrutturazione.py`.
3. Nella cartella del programma, con ambiente virtuale attivo, eseguire **una sola volta**:

   **Linux Mint / macOS:**

   ```bash
   export SIPA_RESET_MERCATINO=CONFERMO_AZZERAMENTO
   python cli.py upgrade-db --backup-dir ~/BackupSIPA
   unset SIPA_RESET_MERCATINO
   python cli.py db-version
   python main.py
   ```

   **Windows PowerShell:**

   ```powershell
   $env:SIPA_RESET_MERCATINO = "CONFERMO_AZZERAMENTO"
   python cli.py upgrade-db --backup-dir "$env:USERPROFILE\BackupSIPA"
   Remove-Item Env:SIPA_RESET_MERCATINO
   python cli.py db-version
   python main.py
   ```

4. La revisione attesa è **`0007_mercatino_ristrutturazione`**. Conservare la copia di backup verificata, il manifesto JSON e la chiave audit, se presente. In PostgreSQL l'operazione deve essere coordinata da una sola postazione autorizzata.

**Non usare il comando `upgrade-db` senza il consenso all'azzeramento** quando lo schema è ancora a `0006`: il sistema impedirà la migrazione e lascerà il database da aggiornare. Se l'aggiornamento si interrompe, non riavviare SIPA finché non è stata verificata la revisione e la consistenza del database.

## Gestione delle bozze di rilevazione

- **Rileva presenze → Salva bozza:** conserva la rilevazione non ancora confermata. La bozza non alimenta gli accertamenti o i prospetti annuali.
- **Mercatino → Gestisci bozze:** apre l’elenco delle bozze, ordinato dalla data più recente; mostra data, luogo, giornata, operatore e riepilogo degli esiti provvisori.
- **Apri:** riapre la bozza selezionata già impostando data e giornata, recuperando le caselle delle ditte presenti. È possibile modificare e salvare nuovamente la bozza oppure confermarla.
- **Elimina:** richiede una conferma esplicita, cancella la bozza e i suoi esiti provvisori in una sola transazione, e registra l’operazione nell’audit. Non elimina assegnazioni o provvedimenti.
- Le **rilevazioni confermate** non compaiono nella gestione bozze e non possono essere eliminate con questo comando. Per correggerle si usa la rilevazione con motivazione di rettifica.
- **Nessuna migrazione Alembic necessaria:** vengono usate le tabelle già presenti nella revisione `0007_mercatino_ristrutturazione`.

## Gestione luoghi, giornate e assegnazioni (aggiornamento interfaccia)

- **Gestisci luoghi:** apre l'elenco dei luoghi con selezione di una riga e comandi **Nuovo**, **Salva** (inserimento/modifica), **Elimina selezionato** (doppia conferma), **Chiudi**. Non è possibile cancellare un luogo ancora collegato a una giornata.
- **Gestisci giornate:** apre l'elenco delle coppie luogo/giorno, con modifica, inserimento ed eliminazione. Una giornata che ha già assegnazioni o rilevazioni non può essere modificata nel giorno/luogo né eliminata.
- **Gestisci assegnazioni:** il pulsante nella riga della singola ditta apre un elenco delle sue assegnazioni. La selezione permette di correggere posteggio, ordine, giornata e validità oppure di eliminare l'assegnazione; è possibile anche aggiungerne altre. Le assegnazioni già collegate a provvedimenti o esiti di rilevazione non possono essere modificate o eliminate, per conservare lo storico.
- Le cancellazioni sono protette da una seconda conferma e le operazioni sono registrate nell'audit.
- Le nuove funzioni **non modificano la struttura del database**: chi è già alla revisione `0007_mercatino_ristrutturazione` deve solamente sostituire `main.py` e `mercatino.py`, senza eseguire migrazioni.

## Nuovo flusso Mercatino

- **Nuovo luogo:** registra una sede fisica con nome univoco.
- **Nuova giornata:** associa a un luogo un giorno della settimana; uno stesso luogo può essere attivo più giorni.
- **Nuova ditta:** anagrafica generale indipendente dai posteggi.
- **Nuova assegnazione:** collega ditta e giornata, con posto, ordine di rilevazione e periodo di validità; non sovrapporre periodi della stessa ditta e giornata.
- **Provvedimenti:** registra numero/data dell'atto, tipologia, periodo di efficacia e assegnazioni interessate; sospensione, revoca, decadenza e riattivazione. La prima versione blocca intervalli sovrapposti per evitare stati ambigui.
- **Rileva presenze:** seleziona data e giornata, spunta i presenti. Gli esclusi per sospensione, cessazione e fuori validità sono mostrati separatamente. `Salva bozza` non produce accertamenti; `Conferma rilevazione` fissa gli esiti presenti/assenti. Una modifica a una rilevazione confermata richiede motivazione registrata nell'audit.
- **Accertamento assenze per data / luogo:** stampa un PDF solo con gli esiti ASSENTE delle rilevazioni confermate, raggruppati per luogo.
- **Prospetti annuali:** riepilogo per ditta e complessivo ricavati esclusivamente da rilevazioni confermate.

L'elenco delle ditte mostra le assegnazioni nel formato `STRASATTI martedì (posto 34), STRASATTI domenica (posto 43), CENTRO venerdì (posto 9)`.

**Nota operativa:** lo stato amministrativo è calcolato alla data della rilevazione. Gli esiti confermati conservano denominazione e posto. Non si deve considerare un PDF generato automaticamente come attestazione di circostanze ulteriori rispetto ai rilievi effettivamente registrati.

---

# SIPA — Sistema Informativo Polizia Amministrativa

**Versione 0.58** · Applicazione desktop in Python per la gestione delle attività di polizia amministrativa.

[Repository GitHub — bleish-git/sipa](https://github.com/bleish-git/sipa) · **Licenza MIT**

## Panoramica

SIPA offre un'interfaccia grafica realizzata con **Flet**, utilizza **SQLAlchemy** per l'accesso ai dati e **Alembic** per le migrazioni dello schema. Sono previste configurazioni per **SQLite** e **PostgreSQL**. L'utilizzo con più postazioni e un database centralizzato richiede un'adeguata architettura di distribuzione e la verifica dei controlli di sicurezza.

## Funzionalità disponibili

- **Autenticazione e utenti:** accesso e disconnessione, password protette con PBKDF2 e salt, creazione e gestione degli utenti, disattivazione e riattivazione, reimpostazione password e cambio obbligatorio dopo il reset.
- **Ruoli e autorizzazioni:** quattro ruoli (`admin`, `responsabile`, `operatore`, `consultazione`), permessi granulari e matrice dei permessi modificabile dall'amministratore.
- **Protezione degli accessi:** limitazione dei tentativi ripetuti di autenticazione.
- **Registro attività economiche:** inserimento, elenco, modifica e consultazione; campi nome, titolare, PEC, descrizione, note, data d'inizio e cessazione. Nome attività normalizzato in maiuscolo; ricerca automatica OR su più termini, anche parziali, in nome, titolare, descrizione e note; filtro per stato calcolato dalle date (**Da iniziare**, **Attiva**, **Sospesa**, **Cessata**); esportazione in PDF dell’elenco filtrato nella cartella `~/SIPA_Stampe`.
- **Audit:** registrazione di accessi e operazioni amministrative, con catena HMAC-SHA256 e chiave separata; verifica da terminale.
- **Amministrazione database:** configurazione SQLite/PostgreSQL, controllo della revisione Alembic e aggiornamento esplicito dello schema con backup preventivo.
- **Backup SQLite e PostgreSQL:** copia coerente tramite API SQLite, controllo d'integrità, impronta SHA256, manifest JSON e copia della chiave audit quando presente.
- **Verifica backup:** SQLite confronta anche tabelle e colonne; PostgreSQL verifica manifest, file SQL e revisione (senza confronto completo delle colonne). Ripristino offline tramite CLI, PostgreSQL solo su database vuoto.

Le voci di navigazione relative a **Sanzioni amministrative**, **Accertamenti** e **Archivio documentale** non implicano che i rispettivi moduli applicativi siano già implementati.

## Requisiti

- Python 3 e ambiente virtuale `venv`.
- Dipendenze indicate in `requirements.txt`: Flet, SQLAlchemy, Alembic e `psycopg` per PostgreSQL.
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

**Contatto dell’autore:** `bleish [at] gmail [dot] com` (sostituire `[at]` con `@` e `[dot]` con `.`). L’indirizzo non è un link `mailto:` per ridurre la raccolta automatica più semplice. **L’offuscamento testuale non impedisce ai bot evoluti di ricostruire l’indirizzo**; per minimizzare lo spam, è preferibile usare le *Issues* del repository GitHub per richieste pubbliche e riservare l’email ai contatti privati.

L’avviso di copyright e il testo della licenza MIT nel file `LICENSE` devono rimanere integri nelle redistribuzioni; l’indirizzo email qui indicato non modifica i termini della licenza.


## Guida operativa database in Amministrazione

La voce **Amministrazione → Guida operazioni database** mostra le seguenti procedure, distinte per luogo di esecuzione e conseguenze:

| Operazione | Dove | Verifica | Modifica | Riavvio |
|---|---|---|---|---|
| Configura database (stesso motore) | SIPA aperto | Connessione, struttura, revisione Alembic esatta, utenti, password amministratore e audit | Solo configurazione locale e chiave audit, quando richiesta; **non** cambia i dati del server | **Sì** |
| Genera backup | SIPA aperto o CLI | Integrità SQLite / esito pg_dump e impronta SHA256 | Scrive solo i file di backup esterni | No |
| Ripristina da file / confronta schema | SIPA aperto | File, manifest, checksum, chiave; SQLite confronta struttura | Nessuna modifica al database | No |
| Aggiorna schema (con backup) | **Solo CLI, SIPA e altri client chiusi** | Revisione Alembic, backup preventivo | Applica migrazioni allo schema; talvolta anche ai dati | **Sì** |
| Ripristino reale backup | **Solo CLI, SIPA e altri client chiusi** | Manifest SHA256, integrità SQLite; revisione non più recente del programma | Ripristina interamente i dati; PostgreSQL solo verso database vuoto | **Sì** |
| Nuova installazione / collega esistente | Prima esecuzione grafica o `--init-admin` | Database, revisione esatta, amministratore, chiave | Crea solo configurazione locale; collegamento senza scritture sul DB | **Sì**, dopo configurazione |

### Regole di versione e recupero

SIPA si avvia soltanto se la revisione dello schema del database corrisponde **esattamente** a quella richiesta dall'applicazione. Non avviene alcuna migrazione automatica all'avvio. Un backup con schema più vecchio può essere ripristinato offline, ma **prima di riaprire SIPA** occorre eseguire `python cli.py upgrade-db --backup-dir ~/BackupSIPA` e verificare `python cli.py db-version`. Un backup con schema più nuovo o non riconosciuto viene rifiutato dal ripristino: installare una versione di SIPA compatibile, non forzare il downgrade.

Il **cambio di destinazione** non trasferisce i dati: ad esempio collegare un PostgreSQL remoto non copia automaticamente il precedente SQLite. Per cambiare motore, arrestare l'applicazione e procedere con una nuova configurazione iniziale, conservando in modo sicuro file JSON e chiave audit precedenti. Un trasferimento di dati tra motori richiede una procedura di migrazione distinta, non ancora disponibile. Per PostgreSQL ripristinato da `.sql`, predisporre preventivamente un database **vuoto**, configurarlo come destinazione a SIPA chiuso e utilizzare il comando di ripristino dal terminale.

**Nota sulla portabilità:** `pg_dump --format=plain --column-inserts` esporta SQL testuale con nomi di colonne espliciti, ma può contenere comandi e tipi specifici di PostgreSQL. Non è garantita la compatibilità con SQLite o altri DBMS.

**Protezione copie:** database, export SQL, manifest e chiavi di audit possono contenere dati sensibili. Conservare backup e cartelle di storico delle configurazioni in un percorso protetto, accessibile solo agli amministratori. Effettuare periodicamente prove di ripristino su un ambiente isolato.

## Aggiornamento da SIPA 0.55 a SIPA 0.56

La revisione Alembic cambia da `0002_attivita_economiche` a `0003_sospensione_tipologia`. Dopo aver installato i file della patch, **prima di avviare SIPA** chiudere tutti i client e lanciare:

```bash
python -m pip install -r requirements.txt
python cli.py upgrade-db --backup-dir ~/BackupSIPA
python cli.py db-version
python main.py
```

L'aggiornamento esegue un backup preventivo e aggiunge le colonne senza cancellare le registrazioni già presenti. Se più postazioni condividono PostgreSQL, applicare la migrazione **una sola volta** dal PC amministrativo. Le tipologie disponibili nella v0.56 sono: Non specificata, Commercio, Somministrazione, Artigianato, Servizi, Altro.

L'intervallo di sospensione è **inclusivo** (la data di fine è ancora sospesa); se la fine è vuota la sospensione rimane attiva. Lo stato Cessata prevale su Sospesa, e Da iniziare prevale su Sospesa. La ricerca combina le parole separate da spazi con OR: `srl oloc` restituisce le attività che contengono `srl` **oppure** `oloc` in uno dei campi ricercabili. La stampa PDF riproduce i filtri e le righe visualizzate (non comprende PEC, descrizione o note).


## Aggiornamento a SIPA 0.57 — Mercatino

La revisione Alembic richiesta è **`0004_mercatino`** (precedente: `0003_sospensione_tipologia`).
Chiudere SIPA su **tutte** le postazioni prima dell'aggiornamento; creare una copia dei file attuali e sostituire solo i file della patch. Poi eseguire:

```bash
python -m pip install -r requirements.txt
python cli.py upgrade-db --backup-dir ~/BackupSIPA
python cli.py db-version
python main.py
```

L'aggiornamento dello schema è **esplicito e offline**, con backup preventivo. Non viene cancellata alcuna attività economica esistente.

### Funzionalità Mercatino

- **Dit­te:** denominazione, numero posto, stato *Attivo/Sospeso/Cessato*, luogo mercatino. Inserimento e modifica autorizzati per ruolo.
- **Ricerca:** denominazione, a partire da **3 caratteri complessivi**; filtro per stato; selezione multipla dei luoghi effettivamente registrati (anche nessun luogo).
- **Assenze:** nella riga della ditta, *Registra / annulla assenza* permette di indicare un giorno `GG/MM/AAAA`. La stessa ditta può avere al massimo una registrazione per ciascuna data. L'annullamento è tracciato nell'audit.
- **Stampe:** *Stampa elenco PDF* usa la ricerca e i filtri correnti; *Prospetto annuale complessivo PDF* utilizza l'anno selezionato e le ditte attualmente filtrate. Dalla singola riga si stampa il prospetto annuale della ditta. La matrice mostra **una riga per ditta e una colonna per data con almeno un'assenza registrata**; una `X` identifica un'assenza. Per leggibilità, più di 12 date vengono suddivise in blocchi di colonne, mantenendo la ditta in ogni blocco. I file sono salvati in `~/SIPA_Stampe`.
- **Ruoli:** autorizzazioni `mercatino.read`, `.create`, `.update`, `.absence`, `.export`. La v0.57 inizializza i permessi predefiniti per i ruoli al primo avvio, dopo la migrazione; possono essere personalizzati in Amministrazione.

### Ricerca Attività economiche

La ricerca OR si attiva quando **l'intera stringa, senza spazi iniziali/finali**, è lunga almeno **3 caratteri**, non quando ogni parola ha almeno tre caratteri. I termini sono separati da spazi, possono essere anche di 1–2 caratteri e vengono cercati in OR nei campi nome, titolare, descrizione e note, senza distinzione fra maiuscole e minuscole. Ad esempio, `a srl` cerca `a` **oppure** `srl`. Una ricerca vuota mostra l'elenco completo.

### Note di sicurezza e funzionamento

Il Mercatino conserva le assenze come date e non come celle fisse del calendario; il prospetto viene generato dai dati registrati nell'anno. Non sono previsti cancellazioni automatiche o modifiche allo schema durante il normale avvio. Le prove delle migrazioni e delle stampe vanno ripetute sul sistema operativo di destinazione prima dell'utilizzo su dati operativi.


## SIPA 0.58 — Rilevazione presenze Mercatino

La revisione richiesta è **`0005_presenze_ordine`**. Con SIPA chiuso su tutte le postazioni, sostituire i file della patch ed eseguire:

```bash
python cli.py upgrade-db --backup-dir ~/BackupSIPA
python cli.py db-version
python main.py
```

La migrazione aggiunge il campo numerico **Ordine rilevazione** (predefinito 0, per le ditte già registrate) e la tabella `mercatino_rilevazioni`, che tiene traccia delle giornate e dei luoghi per i quali il controllo presenze è stato salvato. Non elimina le assenze esistenti.

Nella scheda della ditta si imposta **Ordine rilevazione**, intero da 0 a 999999, indipendente dal numero posto. Il comando **Registra / annulla presenze** nel menu Mercatino apre una maschera con **data** e **luogo**, quindi visualizza soltanto le ditte **attive** di quel luogo, ordinate per tale campo, numero posto e denominazione. Spuntare **le ditte presenti**; quelle non spuntate vengono registrate assenti quando si sceglie **Salva e chiudi**. **Annulla** chiude senza modifiche.

Una data/luogo già salvata può essere riaperta: le caselle vengono ricostruite dalle assenze registrate e il nuovo salvataggio aggiunge o annulla le assenze per differenza. Ogni rilevazione usa una transazione unica e registra un evento nell'audit. La tabella delle rilevazioni distingue una giornata già verificata con tutti presenti da una giornata mai verificata. Le assenze pregresse rimangono conservate.

**Avvertenza:** quando una giornata non è stata ancora rilevata le caselle partono tutte vuote. Verificare le spunte prima del salvataggio; se nessuna è selezionata, il programma registrerà tutte le ditte attive del luogo come assenti. Se una ditta cambia stato o luogo durante la compilazione, SIPA richiede di ricaricare l'elenco prima di salvare.
