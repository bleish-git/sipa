"""Gestione attività economiche; stato calcolato, mai memorizzato."""
from datetime import date, datetime
from sqlalchemy import select, or_, func, delete
from sqlalchemy.orm import Session
from database import engine, AttivitaEconomica, AttivitaTipologia, log
from security import has_permission

TIPOLOGIE = ('Non specificata', 'Commercio', 'Somministrazione', 'Artigianato', 'Servizi', 'Altro')
STATI = ('Tutte', 'Attiva', 'Da iniziare', 'Sospesa', 'Cessata')


def elenco_tipologie(user_id):
    if not has_permission(user_id, 'attivita.read'):
        raise PermissionError('Non autorizzato alla consultazione delle tipologie.')
    with Session(engine) as session:
        return [{'nome': item.nome, 'descrizione': item.descrizione}
                for item in session.scalars(select(AttivitaTipologia).order_by(AttivitaTipologia.nome)).all()]


def salva_tipologia(user_id, username, nome, descrizione, nome_originale=None):
    if not has_permission(user_id, 'attivita.update'):
        raise PermissionError('Permesso di modifica attività necessario.')
    nome = (nome or '').strip()
    descrizione = (descrizione or '').strip()
    if not nome or len(nome) > 80:
        raise ValueError('Nome tipologia obbligatorio (massimo 80 caratteri).')
    if len(descrizione) > 2000:
        raise ValueError('Descrizione troppo lunga (massimo 2000 caratteri).')
    with Session(engine) as session:
        if nome_originale:
            item = session.get(AttivitaTipologia, nome_originale)
            if item is None:
                raise ValueError('Tipologia non trovata.')
            if nome != nome_originale:
                if session.get(AttivitaTipologia, nome) is not None:
                    raise ValueError('Esiste già una tipologia con questo nome.')
                # Aggiornamento atomico dei riferimenti esistenti (nessun record perso).
                for att in session.scalars(select(AttivitaEconomica).where(AttivitaEconomica.tipologia == nome_originale)):
                    att.tipologia = nome
                session.delete(item)
                session.flush()
                session.add(AttivitaTipologia(nome=nome, descrizione=descrizione))
            else:
                item.descrizione = descrizione
            action = 'attivita.tipologia.update'
        else:
            if session.get(AttivitaTipologia, nome) is not None:
                raise ValueError('Tipologia già esistente.')
            session.add(AttivitaTipologia(nome=nome, descrizione=descrizione))
            action = 'attivita.tipologia.create'
        log(session, username, action, nome, f'Tipologia {nome}'[:300])
        session.commit()


def elimina_tipologia(user_id, username, nome):
    if not has_permission(user_id, 'attivita.update'):
        raise PermissionError('Permesso di modifica attività necessario.')
    if nome == 'Non specificata':
        raise ValueError('La tipologia predefinita non può essere eliminata.')
    with Session(engine) as session:
        item = session.get(AttivitaTipologia, nome)
        if item is None:
            raise ValueError('Tipologia non trovata.')
        # Blocco in presenza di collegamenti: SERIALIZABLE/lock applicativo per
        # multiutente richiederebbe un FK; la migrazione mantiene compatibilità.
        count = session.scalar(select(func.count()).select_from(AttivitaEconomica).where(AttivitaEconomica.tipologia == nome))
        if count:
            raise ValueError(f'Tipologia associata a {count} attività: cancellazione non consentita.')
        session.delete(item)
        log(session, username, 'attivita.tipologia.delete', nome, f'Tipologia {nome}'[:300])
        session.commit()


def stato(item, oggi=None):
    oggi = oggi or date.today()
    if item.data_cessazione is not None and item.data_cessazione <= oggi:
        return 'Cessata'
    if item.data_inizio is not None and item.data_inizio > oggi:
        return 'Da iniziare'
    if (item.data_sospensione_inizio is not None and
            item.data_sospensione_inizio <= oggi and
            (item.data_sospensione_fine is None or oggi <= item.data_sospensione_fine)):
        return 'Sospesa'
    return 'Attiva'


def _display_date(value):
    return value.strftime('%d/%m/%Y') if value else ''


def _record(item):
    return dict(id=item.id, nome=(item.nome or '').upper(), titolare=item.titolare,
                tipologia=item.tipologia or 'Non specificata', pec=item.pec,
                descrizione=item.descrizione, note=item.note,
                numero_fascicolo=item.numero_fascicolo, indirizzo=item.indirizzo,
                protocollo_inizio=item.protocollo_inizio, riscontro_inizio=item.riscontro_inizio,
                protocollo_cessazione=item.protocollo_cessazione, riscontro_cessazione=item.riscontro_cessazione,
                note_provvedimenti=item.note_provvedimenti, altri_dati=item.altri_dati,
                data_inizio=_display_date(item.data_inizio),
                data_cessazione=_display_date(item.data_cessazione),
                data_sospensione_inizio=_display_date(item.data_sospensione_inizio),
                data_sospensione_fine=_display_date(item.data_sospensione_fine),
                stato=stato(item))


def elenco(user_id, ricerca='', filtro='Tutte'):
    if not has_permission(user_id, 'attivita.read'):
        raise PermissionError('Non autorizzato alla consultazione delle attività.')
    ricerca = (ricerca or '').strip()
    if ricerca and len(ricerca) < 3:
        return []
    if filtro not in STATI:
        raise ValueError('Filtro non valido.')
    with Session(engine) as session:
        query = select(AttivitaEconomica)
        # OR tra parole e fra i campi: anche porzioni di parole, case insensitive.
        if ricerca:
            conditions = []
            for token in ricerca.split():
                token = token.lower()
                for column in (AttivitaEconomica.nome, AttivitaEconomica.titolare,
                               AttivitaEconomica.descrizione, AttivitaEconomica.note):
                    conditions.append(func.lower(column).contains(token, autoescape=True))
            query = query.where(or_(*conditions))
        items = session.scalars(query.order_by(AttivitaEconomica.nome, AttivitaEconomica.id)).all()
        return [_record(item) for item in items if filtro == 'Tutte' or stato(item) == filtro]


def dettaglio(user_id, item_id):
    if not has_permission(user_id, 'attivita.read'):
        raise PermissionError('Accesso non autorizzato.')
    with Session(engine) as session:
        item = session.get(AttivitaEconomica, item_id)
        if item is None:
            raise ValueError('Attività non trovata.')
        return _record(item)


def _parse_date(values, key):
    value = (values.get(key) or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%d/%m/%Y').date()
    except ValueError as exc:
        raise ValueError(f'Data non valida per {key}: utilizzare GG/MM/AAAA.') from exc


def salva(user_id, username, values, item_id=None):
    permission = 'attivita.update' if item_id is not None else 'attivita.create'
    if not has_permission(user_id, permission):
        raise PermissionError('Non hai il permesso di salvare questa attività.')
    nome = (values.get('nome') or '').strip().upper()
    if not nome:
        raise ValueError('Il nome dell’attività è obbligatorio.')
    if len(nome) > 200:
        raise ValueError('Il nome supera 200 caratteri.')
    start = _parse_date(values, 'data_inizio')
    end = _parse_date(values, 'data_cessazione')
    pause_start = _parse_date(values, 'data_sospensione_inizio')
    pause_end = _parse_date(values, 'data_sospensione_fine')
    if start and end and end < start:
        raise ValueError('La data di cessazione non può precedere quella di inizio.')
    if pause_end and not pause_start:
        raise ValueError('Indicare la data di inizio sospensione quando si specifica la fine.')
    if pause_start and pause_end and pause_end < pause_start:
        raise ValueError('La fine sospensione non può precedere l’inizio sospensione.')
    tipo = (values.get('tipologia') or 'Non specificata').strip()
    with Session(engine) as check_session:
        if check_session.get(AttivitaTipologia, tipo) is None:
            raise ValueError('Tipologia non presente nel catalogo.')
    fields = {'nome': nome, 'tipologia': tipo,
              'titolare': (values.get('titolare') or '').strip(),
              'pec': (values.get('pec') or '').strip(),
              'descrizione': (values.get('descrizione') or '').strip(),
              'note': (values.get('note') or '').strip(),
              'data_inizio': start, 'data_cessazione': end,
              'data_sospensione_inizio': pause_start, 'data_sospensione_fine': pause_end,
              **{key: (values.get(key) or '').strip() for key in (
                  'numero_fascicolo', 'indirizzo', 'protocollo_inizio', 'riscontro_inizio',
                  'protocollo_cessazione', 'riscontro_cessazione', 'note_provvedimenti', 'altri_dati')}}
    limits = {'numero_fascicolo': 60, 'indirizzo': 300, 'protocollo_inizio': 120,
              'protocollo_cessazione': 120}
    for key, limit in limits.items():
        if len(fields[key]) > limit:
            raise ValueError(f'{key}: massimo {limit} caratteri.')
    if len(fields['titolare']) > 200 or len(fields['pec']) > 254:
        raise ValueError('Titolare o PEC troppo lunghi.')
    with Session(engine) as session:
        if item_id is None:
            item = AttivitaEconomica(**fields)
            session.add(item)
            session.flush()
            action = 'attivita.create'
        else:
            item = session.get(AttivitaEconomica, item_id)
            if item is None:
                raise ValueError('Attività non trovata.')
            for key, value in fields.items():
                setattr(item, key, value)
            action = 'attivita.update'
        log(session, username, action, str(item.id), f'Attività: {nome}'[:300])
        session.commit()
        return item.id
