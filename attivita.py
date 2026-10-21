"""Operazioni sulle attività economiche; stato derivato dalle date, mai salvato."""
from datetime import date
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from database import engine, AttivitaEconomica, log
from security import has_permission


def stato(item, oggi=None):
    oggi = oggi or date.today()
    if item.data_cessazione is not None and item.data_cessazione <= oggi:
        return 'Cessata'
    if item.data_inizio is not None and item.data_inizio > oggi:
        return 'Da iniziare'
    return 'Attiva'


def _record(item):
    return dict(id=item.id, nome=(item.nome or '').upper(), titolare=item.titolare, pec=item.pec,
                descrizione=item.descrizione, note=item.note,
                data_inizio=item.data_inizio.isoformat() if item.data_inizio else '',
                data_cessazione=item.data_cessazione.isoformat() if item.data_cessazione else '',
                stato=stato(item))


def elenco(user_id, ricerca='', filtro='Tutte'):
    if not has_permission(user_id, 'attivita.read'):
        raise PermissionError('Non autorizzato alla consultazione delle attività.')
    ricerca = (ricerca or '').strip()
    if ricerca and len(ricerca) < 3:
        return []
    oggi = date.today()
    with Session(engine) as session:
        query = select(AttivitaEconomica)
        if ricerca:
            query = query.where(or_(
                func.lower(AttivitaEconomica.nome).contains(ricerca.lower(), autoescape=True),
                func.lower(AttivitaEconomica.titolare).contains(ricerca.lower(), autoescape=True),
                func.lower(AttivitaEconomica.descrizione).contains(ricerca.lower(), autoescape=True),
                func.lower(AttivitaEconomica.note).contains(ricerca.lower(), autoescape=True),
            ))
        if filtro == 'Cessata':
            query = query.where(AttivitaEconomica.data_cessazione.is_not(None), AttivitaEconomica.data_cessazione <= oggi)
        elif filtro == 'Da iniziare':
            query = query.where(AttivitaEconomica.data_inizio > oggi,
                or_(AttivitaEconomica.data_cessazione.is_(None), AttivitaEconomica.data_cessazione > oggi))
        elif filtro == 'Attiva':
            query = query.where(or_(AttivitaEconomica.data_inizio.is_(None), AttivitaEconomica.data_inizio <= oggi),
                or_(AttivitaEconomica.data_cessazione.is_(None), AttivitaEconomica.data_cessazione > oggi))
        elif filtro != 'Tutte':
            raise ValueError('Filtro non valido.')
        items = session.scalars(query.order_by(AttivitaEconomica.nome, AttivitaEconomica.id)).all()
        return [_record(item) for item in items]


def dettaglio(user_id, item_id):
    if not has_permission(user_id, 'attivita.read'):
        raise PermissionError('Accesso non autorizzato.')
    with Session(engine) as session:
        item = session.get(AttivitaEconomica, item_id)
        if item is None:
            raise ValueError('Attività non trovata.')
        return _record(item)


def salva(user_id, username, values, item_id=None):
    permission = 'attivita.update' if item_id is not None else 'attivita.create'
    if not has_permission(user_id, permission):
        raise PermissionError('Non hai il permesso di salvare questa attività.')
    nome = (values.get('nome') or '').strip().upper()
    if not nome:
        raise ValueError('Il nome dell’attività è obbligatorio.')
    if len(nome) > 200:
        raise ValueError('Il nome supera 200 caratteri.')
    def parse_date(key):
        value = (values.get(key) or '').strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f'Data non valida per {key}: usare AAAA-MM-GG.')
    start = parse_date('data_inizio')
    end = parse_date('data_cessazione')
    if start and end and end < start:
        raise ValueError('La data di cessazione non può precedere quella di inizio.')
    fields = {'nome': nome, 'titolare': (values.get('titolare') or '').strip(),
              'pec': (values.get('pec') or '').strip(),
              'descrizione': (values.get('descrizione') or '').strip(),
              'note': (values.get('note') or '').strip(),
              'data_inizio': start, 'data_cessazione': end}
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
