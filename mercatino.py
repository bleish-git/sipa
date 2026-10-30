"""Registro mercatino: ditte e assenze, con autorizzazioni e audit."""
from datetime import date, datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import engine, MercatinoDitta, MercatinoAssenza, log
from security import has_permission

STATI = ('Attivo', 'Sospeso', 'Cessato')


def _check(uid, perm):
    if not has_permission(uid, perm):
        raise PermissionError('Operazione non autorizzata: ' + perm)


def data_input(raw):
    if isinstance(raw, date):
        return raw
    try:
        return datetime.strptime(str(raw).strip(), '%d/%m/%Y').date()
    except ValueError as exc:
        raise ValueError('Usare una data valida nel formato GG/MM/AAAA.') from exc


def _dto(d):
    return dict(id=d.id, denominazione=d.denominazione, numero_posto=d.numero_posto,
                luogo=d.luogo, stato=d.stato)


def luoghi(uid):
    _check(uid, 'mercatino.read')
    with Session(engine) as session:
        return list(session.scalars(select(MercatinoDitta.luogo).distinct().order_by(MercatinoDitta.luogo)))


def elenco(uid, ricerca='', luoghi_selezionati=None, stato='Tutti'):
    _check(uid, 'mercatino.read')
    ricerca = (ricerca or '').strip()
    if ricerca and len(ricerca) < 3:
        return []
    if stato not in ('Tutti',) + STATI:
        raise ValueError('Stato non valido')
    with Session(engine) as session:
        q = select(MercatinoDitta)
        if ricerca:
            q = q.where(func.lower(MercatinoDitta.denominazione).contains(ricerca.lower(), autoescape=True))
        if luoghi_selezionati is not None:
            if not luoghi_selezionati:
                return []
            q = q.where(MercatinoDitta.luogo.in_(list(luoghi_selezionati)))
        if stato != 'Tutti':
            q = q.where(MercatinoDitta.stato == stato)
        return [_dto(x) for x in session.scalars(q.order_by(MercatinoDitta.luogo, MercatinoDitta.numero_posto, MercatinoDitta.denominazione))]


def dettaglio(uid, pk):
    _check(uid, 'mercatino.read')
    with Session(engine) as session:
        d = session.get(MercatinoDitta, pk)
        if d is None:
            raise ValueError('Ditta non trovata')
        return _dto(d)


def salva(uid, username, valori, pk=None):
    _check(uid, 'mercatino.update' if pk is not None else 'mercatino.create')
    data = {k: (valori.get(k) or '').strip() for k in ('denominazione','numero_posto','luogo','stato')}
    data['denominazione'] = data['denominazione'].upper()
    for key, maxlen in [('denominazione', 200), ('numero_posto', 30), ('luogo', 150)]:
        if not data[key] or len(data[key]) > maxlen:
            raise ValueError(f'Campo {key} obbligatorio (massimo {maxlen} caratteri)')
    if data['stato'] not in STATI:
        raise ValueError('Stato non valido')
    with Session(engine) as session:
        d = session.get(MercatinoDitta, pk) if pk is not None else MercatinoDitta()
        if d is None:
            raise ValueError('Ditta non trovata')
        for k, v in data.items():
            setattr(d, k, v)
        session.add(d)
        session.flush()
        log(session, username, 'mercatino.update' if pk else 'mercatino.create', str(d.id), d.denominazione)
        session.commit()
        return d.id


def assenze(uid, pk, anno=None):
    _check(uid, 'mercatino.read')
    with Session(engine) as session:
        if session.get(MercatinoDitta, pk) is None:
            raise ValueError('Ditta non trovata')
        q = select(MercatinoAssenza.giorno).where(MercatinoAssenza.ditta_id == pk)
        if anno is not None:
            q = q.where(func.extract('year', MercatinoAssenza.giorno) == int(anno))
        return list(session.scalars(q.order_by(MercatinoAssenza.giorno)))


def segna_assenza(uid, username, pk, giorno, assente=True):
    _check(uid, 'mercatino.absence')
    giorno = data_input(giorno)
    with Session(engine) as session:
        ditta = session.get(MercatinoDitta, pk)
        if ditta is None:
            raise ValueError('Ditta non trovata')
        if assente and ditta.stato != 'Attivo':
            raise ValueError('La registrazione di assenze è consentita soltanto per ditte attive')
        a = session.scalar(select(MercatinoAssenza).where(MercatinoAssenza.ditta_id == pk, MercatinoAssenza.giorno == giorno))
        if assente and a is None:
            session.add(MercatinoAssenza(ditta_id=pk, giorno=giorno))
        elif not assente and a is not None:
            session.delete(a)
        else:
            return False
        log(session, username, 'mercatino.assenza' if assente else 'mercatino.assenza.annulla', str(pk), giorno.isoformat())
        session.commit()
        return True


def matrice(uid, anno, ricerca='', luoghi_selezionati=None, stato='Tutti', ditta_id=None):
    _check(uid, 'mercatino.read')
    anno = int(anno)
    if anno < 1900 or anno > 2200:
        raise ValueError('Anno non valido')
    ditte = elenco(uid, ricerca, luoghi_selezionati, stato)
    if ditta_id is not None:
        ditte = [d for d in ditte if d['id'] == ditta_id]
    ids = [d['id'] for d in ditte]
    if not ids:
        return ditte, [], {}
    with Session(engine) as session:
        q = select(MercatinoAssenza).where(MercatinoAssenza.ditta_id.in_(ids),
                  MercatinoAssenza.giorno >= date(anno, 1, 1),
                  MercatinoAssenza.giorno <= date(anno, 12, 31))
        rows = session.scalars(q).all()
        dates = sorted({a.giorno for a in rows})
        indexed = {(a.ditta_id, a.giorno) for a in rows}
    return ditte, dates, indexed


def assenze_per_giorno(uid, giorno):
    """Restituisce le sole ditte con assenza registrata nel giorno indicato.

    Non filtra lo stato corrente: conserva le rilevazioni storiche di ditte
    nel frattempo sospese o cessate.
    """
    _check(uid, 'mercatino.read')
    giorno = data_input(giorno)
    with Session(engine) as session:
        q = (select(MercatinoDitta)
             .join(MercatinoAssenza, MercatinoAssenza.ditta_id == MercatinoDitta.id)
             .where(MercatinoAssenza.giorno == giorno)
             .order_by(MercatinoDitta.luogo, MercatinoDitta.numero_posto, MercatinoDitta.denominazione))
        return [_dto(d) for d in session.scalars(q).all()]
