"""Gestione attività economiche; stato calcolato, mai memorizzato."""
from datetime import date, datetime
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from database import engine, AttivitaEconomica, log
from security import has_permission

TIPOLOGIE = ('Non specificata', 'Commercio', 'Somministrazione', 'Artigianato', 'Servizi', 'Altro')
STATI = ('Tutte', 'Attiva', 'Da iniziare', 'Sospesa', 'Cessata')


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
    if tipo not in TIPOLOGIE:
        raise ValueError('Tipologia non valida.')
    fields = {'nome': nome, 'tipologia': tipo,
              'titolare': (values.get('titolare') or '').strip(),
              'pec': (values.get('pec') or '').strip(),
              'descrizione': (values.get('descrizione') or '').strip(),
              'note': (values.get('note') or '').strip(),
              'data_inizio': start, 'data_cessazione': end,
              'data_sospensione_inizio': pause_start, 'data_sospensione_fine': pause_end}
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
