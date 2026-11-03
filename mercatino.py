"""Mercatino 0.60: calendario, titoli di partecipazione, provvedimenti ed esiti storicizzati."""
from datetime import date, datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import (engine, MercatinoDitta as Ditta, MercatinoLuogo as Luogo,
                      MercatinoGiornata as Giornata, MercatinoAssegnazione as Assegnazione,
                      MercatinoProvvedimento as Provvedimento, MercatinoProvvedimentoAssegnazione as Destinatario,
                      MercatinoRilevazione as Rilevazione, MercatinoEsito as Esito, log)
from security import has_permission

GIORNI = ('Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica')
STATI = ('Attivo','Sospeso','Cessato')
TIPI = ('Sospensione','Revoca','Decadenza','Riattivazione')


def _check(uid, permission):
    if not has_permission(uid, permission):
        raise PermissionError('Permesso mancante: '+permission)


def data_input(raw, optional=False):
    if optional and not raw: return None
    if isinstance(raw, datetime): return raw.date()
    if isinstance(raw, date): return raw
    try: return datetime.strptime(str(raw).strip(), '%d/%m/%Y').date()
    except ValueError as exc: raise ValueError('Usare una data valida GG/MM/AAAA.') from exc


def _intervallo(start, end, day):
    return (start is None or day >= start) and (end is None or day <= end)


def luoghi(uid):
    _check(uid,'mercatino.read')
    with Session(engine) as s:
        return [dict(id=x.id, nome=x.nome, descrizione=x.descrizione) for x in s.scalars(select(Luogo).order_by(Luogo.nome))]


def giornate(uid, luogo_id=None):
    _check(uid,'mercatino.read')
    with Session(engine) as s:
        q=select(Giornata,Luogo).join(Luogo,Luogo.id==Giornata.luogo_id)
        if luogo_id is not None:q=q.where(Giornata.luogo_id==int(luogo_id))
        return [dict(id=g.id,luogo_id=l.id,luogo=l.nome,giorno=g.giorno_settimana,
                     descrizione=f'{l.nome} — {GIORNI[g.giorno_settimana]}')
                for g,l in s.execute(q.order_by(Luogo.nome,Giornata.giorno_settimana))]


def salva_luogo(uid, username, nome, descrizione=''):
    _check(uid,'mercatino.create')
    nome=(nome or '').strip().upper()
    if not nome or len(nome)>150:raise ValueError('Nome del luogo obbligatorio (massimo 150 caratteri).')
    with Session(engine) as s:
        if s.scalar(select(Luogo.id).where(func.lower(Luogo.nome)==nome.lower())):
            raise ValueError('Luogo già esistente.')
        item=Luogo(nome=nome,descrizione=(descrizione or '').strip())
        s.add(item);s.flush();log(s,username,'mercatino.luogo.crea',str(item.id),nome);s.commit();return item.id


def salva_giornata(uid,username,luogo_id,giorno):
    _check(uid,'mercatino.create')
    giorno=int(giorno)
    if giorno not in range(7):raise ValueError('Giorno della settimana non valido.')
    with Session(engine) as s:
        if s.get(Luogo,int(luogo_id)) is None:raise ValueError('Luogo inesistente.')
        existing=s.scalar(select(Giornata.id).where(Giornata.luogo_id==int(luogo_id),Giornata.giorno_settimana==giorno))
        if existing:raise ValueError('Giornata già configurata per questo luogo.')
        row=Giornata(luogo_id=int(luogo_id),giorno_settimana=giorno)
        s.add(row);s.flush();log(s,username,'mercatino.giornata.crea',str(row.id),str(giorno));s.commit();return row.id



def modifica_luogo(uid, username, luogo_id, nome, descrizione=''):
    _check(uid, 'mercatino.update')
    nome=(nome or '').strip().upper()
    if not nome or len(nome)>150:raise ValueError('Nome del luogo obbligatorio (massimo 150 caratteri).')
    with Session(engine) as s:
        row=s.get(Luogo,int(luogo_id))
        if row is None:raise ValueError('Luogo inesistente.')
        conflict=s.scalar(select(Luogo.id).where(func.lower(Luogo.nome)==nome.lower(),Luogo.id!=row.id))
        if conflict:raise ValueError('Esiste già un luogo con questo nome.')
        row.nome=nome;row.descrizione=(descrizione or '').strip()
        log(s,username,'mercatino.luogo.modifica',str(row.id),nome)
        s.commit()


def elimina_luogo(uid, username, luogo_id):
    _check(uid,'mercatino.update')
    with Session(engine) as s:
        row=s.get(Luogo,int(luogo_id))
        if row is None:raise ValueError('Luogo inesistente.')
        if s.scalar(select(Giornata.id).where(Giornata.luogo_id==row.id).limit(1)) is not None:
            raise ValueError('Impossibile eliminare: esistono giornate associate. Eliminarle prima.')
        nome=row.nome;s.delete(row)
        log(s,username,'mercatino.luogo.elimina',str(luogo_id),nome)
        s.commit()


def modifica_giornata(uid,username,giornata_id,luogo_id,giorno):
    _check(uid,'mercatino.update')
    giorno=int(giorno);luogo_id=int(luogo_id)
    if giorno not in range(7):raise ValueError('Giorno della settimana non valido.')
    with Session(engine) as s:
        row=s.get(Giornata,int(giornata_id))
        if row is None or s.get(Luogo,luogo_id) is None:raise ValueError('Giornata o luogo inesistente.')
        if row.luogo_id!=luogo_id or row.giorno_settimana!=giorno:
            if s.scalar(select(Assegnazione.id).where(Assegnazione.giornata_id==row.id).limit(1)) is not None or s.scalar(select(Rilevazione.id).where(Rilevazione.giornata_id==row.id).limit(1)) is not None:
                raise ValueError('La giornata è già utilizzata: per preservare lo storico non è possibile cambiarne luogo o giorno.')
        conflict=s.scalar(select(Giornata.id).where(Giornata.luogo_id==luogo_id,Giornata.giorno_settimana==giorno,Giornata.id!=row.id))
        if conflict:raise ValueError('Giornata già esistente per questo luogo.')
        row.luogo_id=luogo_id;row.giorno_settimana=giorno
        log(s,username,'mercatino.giornata.modifica',str(row.id),f'{luogo_id}:{giorno}')
        s.commit()


def elimina_giornata(uid,username,giornata_id):
    _check(uid,'mercatino.update')
    with Session(engine) as s:
        row=s.get(Giornata,int(giornata_id))
        if row is None:raise ValueError('Giornata inesistente.')
        if s.scalar(select(Assegnazione.id).where(Assegnazione.giornata_id==row.id).limit(1)) is not None:
            raise ValueError('Impossibile eliminare: la giornata ha assegnazioni collegate.')
        if s.scalar(select(Rilevazione.id).where(Rilevazione.giornata_id==row.id).limit(1)) is not None:
            raise ValueError('Impossibile eliminare: esistono rilevazioni storiche.')
        s.delete(row);log(s,username,'mercatino.giornata.elimina',str(giornata_id));s.commit()


def modifica_assegnazione(uid,username,assegnazione_id,giornata_id,posto,ordine=0,dal='',al=''):
    _check(uid,'mercatino.update')
    posto=(posto or '').strip();ordine=int(ordine)
    dal=data_input(dal,True);al=data_input(al,True)
    if not posto or len(posto)>30:raise ValueError('Posto obbligatorio (massimo 30 caratteri).')
    if not 0<=ordine<=999999:raise ValueError('Ordine non valido.')
    if dal and al and al<dal:raise ValueError('Periodo non valido.')
    with Session(engine) as s:
        row=s.get(Assegnazione,int(assegnazione_id))
        if row is None or s.get(Giornata,int(giornata_id)) is None:raise ValueError('Assegnazione o giornata inesistente.')
        if s.scalar(select(Destinatario.provvedimento_id).where(Destinatario.assegnazione_id==row.id).limit(1)) is not None or s.scalar(select(Esito.id).where(Esito.assegnazione_id==row.id).limit(1)) is not None:
            raise ValueError('Assegnazione con provvedimenti o esiti storici: modifica bloccata per tutelare gli accertamenti.')
        others=s.scalars(select(Assegnazione).where(Assegnazione.id!=row.id,Assegnazione.ditta_id==row.ditta_id,Assegnazione.giornata_id==int(giornata_id))).all()
        for other in others:
            if (al is None or other.valida_dal is None or al>=other.valida_dal) and (other.valida_al is None or dal is None or dal<=other.valida_al):
                raise ValueError('Periodo sovrapposto a un’altra assegnazione della ditta nella stessa giornata.')
        row.giornata_id=int(giornata_id);row.posto=posto;row.ordine=ordine
        row.valida_dal=dal;row.valida_al=al
        log(s,username,'mercatino.assegnazione.modifica',str(row.id),posto)
        s.commit()


def elimina_assegnazione(uid,username,assegnazione_id):
    _check(uid,'mercatino.update')
    with Session(engine) as s:
        row=s.get(Assegnazione,int(assegnazione_id))
        if row is None:raise ValueError('Assegnazione inesistente.')
        if s.scalar(select(Destinatario.provvedimento_id).where(Destinatario.assegnazione_id==row.id).limit(1)) is not None:
            raise ValueError('Impossibile eliminare: assegnazione collegata a provvedimenti.')
        if s.scalar(select(Esito.id).where(Esito.assegnazione_id==row.id).limit(1)) is not None:
            raise ValueError('Impossibile eliminare: assegnazione presente nelle rilevazioni storiche.')
        s.delete(row);log(s,username,'mercatino.assegnazione.elimina',str(assegnazione_id));s.commit()

def _assegnazioni(s, ditta_id=None):
    q=(select(Assegnazione,Giornata,Luogo)
       .join(Giornata,Giornata.id==Assegnazione.giornata_id)
       .join(Luogo,Luogo.id==Giornata.luogo_id))
    if ditta_id is not None:q=q.where(Assegnazione.ditta_id==ditta_id)
    rows=[]
    for a,g,l in s.execute(q.order_by(Luogo.nome,Giornata.giorno_settimana,Assegnazione.ordine,Assegnazione.posto)):
        rows.append(dict(id=a.id,ditta_id=a.ditta_id,giornata_id=g.id,luogo_id=l.id,luogo=l.nome,
                         giorno_settimana=g.giorno_settimana,giorno=GIORNI[g.giorno_settimana],
                         posto=a.posto,ordine=a.ordine,dal=a.valida_dal,al=a.valida_al))
    return rows


def elenco(uid,ricerca='',luoghi_selezionati=None,stato='Tutti'):
    _check(uid,'mercatino.read')
    ricerca=(ricerca or '').strip()
    if ricerca and len(ricerca)<3:return []
    with Session(engine) as s:
        q=select(Ditta)
        if ricerca:q=q.where(func.lower(Ditta.denominazione).contains(ricerca.lower(),autoescape=True))
        if stato!='Tutti':q=q.where(Ditta.stato==stato)
        assignments=_assegnazioni(s)
        result=[]
        for d in s.scalars(q.order_by(Ditta.denominazione)):
            ass=[a for a in assignments if a['ditta_id']==d.id]
            if luoghi_selezionati is not None and not any(a['luogo_id'] in luoghi_selezionati for a in ass):continue
            labels=[f"{a['luogo']} {a['giorno'].lower()} (posto {a['posto']})" for a in ass]
            result.append(dict(id=d.id,denominazione=d.denominazione,stato=d.stato,
                               assegnazioni=ass,luoghi_posti=', '.join(labels)))
        return result


def dettaglio(uid,pk):
    _check(uid,'mercatino.read')
    with Session(engine) as s:
        d=s.get(Ditta,int(pk))
        if d is None:raise ValueError('Ditta non trovata.')
        return dict(id=d.id,denominazione=d.denominazione,stato=d.stato,note=d.note,
                    assegnazioni=_assegnazioni(s,d.id))


def salva_ditta(uid,username,denominazione,stato='Attivo',note='',pk=None):
    _check(uid,'mercatino.update' if pk else 'mercatino.create')
    denominazione=(denominazione or '').strip().upper()
    if not denominazione or len(denominazione)>200:raise ValueError('Denominazione obbligatoria.')
    if stato not in STATI:raise ValueError('Stato non valido.')
    with Session(engine) as s:
        d=s.get(Ditta,int(pk)) if pk else Ditta()
        if d is None:raise ValueError('Ditta non trovata.')
        d.denominazione=denominazione;d.stato=stato;d.note=(note or '').strip()
        s.add(d);s.flush();log(s,username,'mercatino.ditta.salva',str(d.id),denominazione);s.commit();return d.id


def salva_assegnazione(uid,username,ditta_id,giornata_id,posto,ordine=0,dal='',al=''):
    _check(uid,'mercatino.update')
    posto=(posto or '').strip()
    if not posto or len(posto)>30:raise ValueError('Posto obbligatorio.')
    ordine=int(ordine)
    if not 0<=ordine<=999999:raise ValueError('Ordine non valido.')
    dal=data_input(dal,True);al=data_input(al,True)
    if dal and al and al<dal:raise ValueError('Periodo assegnazione non valido.')
    with Session(engine) as s:
        if not s.get(Ditta,int(ditta_id)) or not s.get(Giornata,int(giornata_id)):
            raise ValueError('Ditta o giornata inesistente.')
        # Una assegnazione storica non si riscrive: eventuali variazioni producono una nuova riga.
        existing=s.scalars(select(Assegnazione).where(Assegnazione.ditta_id==int(ditta_id),Assegnazione.giornata_id==int(giornata_id))).all()
        for a in existing:
            if (al is None or a.valida_dal is None or al>=a.valida_dal) and (a.valida_al is None or dal is None or dal<=a.valida_al):
                raise ValueError('Esiste già una assegnazione con periodo sovrapposto per questa ditta e giornata.')
        a=Assegnazione(ditta_id=int(ditta_id),giornata_id=int(giornata_id),posto=posto,ordine=ordine,valida_dal=dal,valida_al=al)
        s.add(a);s.flush();log(s,username,'mercatino.assegnazione.crea',str(a.id),posto);s.commit();return a.id


def provvedimenti(uid,ditta_id=None):
    _check(uid,'mercatino.read')
    with Session(engine) as s:
        q=select(Provvedimento,Destinatario).join(Destinatario,Destinatario.provvedimento_id==Provvedimento.id)
        if ditta_id is not None:q=q.join(Assegnazione,Assegnazione.id==Destinatario.assegnazione_id).where(Assegnazione.ditta_id==int(ditta_id))
        return [dict(id=p.id,assegnazione_id=d.assegnazione_id,tipo=p.tipo,numero_atto=p.numero_atto,
                     data_atto=p.data_atto,dal=p.efficace_dal,al=p.efficace_al,motivo=p.motivazione)
                for p,d in s.execute(q.order_by(Provvedimento.efficace_dal.desc()))]


def salva_provvedimento(uid,username,assegnazione_ids,tipo,numero_atto,data_atto,dal,al='',motivazione=''):
    _check(uid,'mercatino.update')
    ids=set(int(x) for x in assegnazione_ids)
    if not ids:raise ValueError('Selezionare almeno una assegnazione.')
    if tipo not in TIPI:raise ValueError('Tipo provvedimento non valido.')
    dal=data_input(dal);al=data_input(al,True);data_atto=data_input(data_atto)
    if al and al<dal:raise ValueError('Fine efficacia precedente all’inizio.')
    if tipo=='Sospensione' and al is None:raise ValueError('Indicare la data finale della sospensione.')
    with Session(engine) as s:
        if len(s.scalars(select(Assegnazione.id).where(Assegnazione.id.in_(ids))).all())!=len(ids):
            raise ValueError('Assegnazione non trovata.')
        # Evita intervalli incompatibili sulla stessa assegnazione; rettifiche mediante gestione amministrativa dedicata.
        for aid in ids:
            q=(select(Provvedimento).join(Destinatario,Destinatario.provvedimento_id==Provvedimento.id)
               .where(Destinatario.assegnazione_id==aid))
            for old in s.scalars(q):
                if (old.efficace_al is None or dal<=old.efficace_al) and (al is None or old.efficace_dal<=al):
                    raise ValueError(f'Provvedimento sovrapposto per assegnazione {aid}.')
        p=Provvedimento(tipo=tipo,numero_atto=numero_atto.strip(),data_atto=data_atto,
                        efficace_dal=dal,efficace_al=al,motivazione=motivazione.strip())
        s.add(p);s.flush()
        for aid in ids:s.add(Destinatario(provvedimento_id=p.id,assegnazione_id=aid))
        log(s,username,'mercatino.provvedimento.crea',str(p.id),f'{tipo} {numero_atto}'[:300]);s.commit();return p.id


def _stato(s,a,day):
    if not _intervallo(a.valida_dal,a.valida_al,day):return 'Fuori validità'
    q=(select(Provvedimento).join(Destinatario,Destinatario.provvedimento_id==Provvedimento.id)
       .where(Destinatario.assegnazione_id==a.id,Provvedimento.efficace_dal<=day)
       .order_by(Provvedimento.efficace_dal,Provvedimento.id))
    acts=[p for p in s.scalars(q) if p.efficace_al is None or day<=p.efficace_al]
    if not acts:return 'Attivo'
    return {'Sospensione':'Sospeso','Revoca':'Revocato','Decadenza':'Decaduto','Riattivazione':'Attivo'}[acts[-1].tipo]


def anteprima(uid,giorno,giornata_id):
    _check(uid,'mercatino.read')
    giorno=data_input(giorno)
    with Session(engine) as s:
        g=s.get(Giornata,int(giornata_id))
        if g is None or giorno.weekday()!=g.giorno_settimana:raise ValueError('Giornata non di mercato per la data selezionata.')
        q=(select(Assegnazione,Ditta).join(Ditta,Ditta.id==Assegnazione.ditta_id)
           .where(Assegnazione.giornata_id==g.id)
           .order_by(Assegnazione.ordine,Assegnazione.posto,Ditta.denominazione))
        eligible=[];excluded=[]
        for a,d in s.execute(q):
            stato=_stato(s,a,giorno)
            if d.stato!='Attivo' and stato=='Attivo':stato=d.stato
            record=dict(assegnazione_id=a.id,ditta_id=d.id,denominazione=d.denominazione,posto=a.posto,ordine=a.ordine,stato=stato)
            (eligible if stato=='Attivo' else excluded).append(record)
        survey=s.scalar(select(Rilevazione).where(Rilevazione.giorno==giorno,Rilevazione.giornata_id==g.id))
        if survey:
            results=list(s.scalars(select(Esito).join(Assegnazione,Assegnazione.id==Esito.assegnazione_id)
                .where(Esito.rilevazione_id==survey.id)
                .order_by(Assegnazione.ordine,Assegnazione.posto,Esito.denominazione)))
            ordine_per_id={a.id:a.ordine for a in s.scalars(select(Assegnazione).where(
                Assegnazione.id.in_([e.assegnazione_id for e in results])))}
            # Riapertura: snapshot storico non modificabile tramite riconfigurazione delle assegnazioni.
            return dict(rilevazione_id=survey.id,stato=survey.stato,
                        ditte=[dict(assegnazione_id=e.assegnazione_id,ditta_id=e.ditta_id,denominazione=e.denominazione,
                                    posto=e.posto,ordine=ordine_per_id.get(e.assegnazione_id,0),esito=e.esito) for e in results if e.esito in ('PRESENTE','ASSENTE')],
                        esclusi=[dict(assegnazione_id=e.assegnazione_id,denominazione=e.denominazione,posto=e.posto,
                                      stato=e.esito) for e in results if e.esito not in ('PRESENTE','ASSENTE')],
                        note=survey.note)
        return dict(rilevazione_id=None,stato='Nuova',ditte=[dict(x,esito='NON RILEVATO') for x in eligible],esclusi=excluded,note='')


def salva_rilevazione(uid,username,giorno,giornata_id,presenti,ids_visualizzati,conferma=False,motivo='',note=''):
    _check(uid,'mercatino.absence')
    giorno=data_input(giorno);giornata_id=int(giornata_id)
    presenti={int(x) for x in presenti};ids={int(x) for x in ids_visualizzati}
    if not presenti.issubset(ids):raise ValueError('Selezione non valida.')
    with Session(engine) as s:
        g=s.get(Giornata,giornata_id)
        if g is None or g.giorno_settimana!=giorno.weekday():raise ValueError('Data non corrispondente alla giornata di mercato.')
        survey=s.scalar(select(Rilevazione).where(Rilevazione.giorno==giorno,Rilevazione.giornata_id==g.id))
        if survey is None:
            data=anteprima(uid,giorno,giornata_id)
            expected={x['assegnazione_id'] for x in data['ditte']}
            if expected!=ids or not ids:raise ValueError('Elenco modificato o vuoto: ricaricare la rilevazione.')
            survey=Rilevazione(giornata_id=g.id,giorno=giorno,stato='Bozza',operatore=username,note=note)
            s.add(survey);s.flush()
            active_by_id={x['assegnazione_id']:x for x in data['ditte']}
            all_items=data['ditte']+data['esclusi']
            for item in all_items:
                aid=item['assegnazione_id'];a=s.get(Assegnazione,aid)
                s.add(Esito(rilevazione_id=survey.id,assegnazione_id=aid,ditta_id=item['ditta_id'],
                            denominazione=item['denominazione'],posto=item['posto'],
                            esito=('PRESENTE' if aid in presenti else 'ASSENTE') if aid in active_by_id else item['stato']))
        else:
            esiti=list(s.scalars(select(Esito).where(Esito.rilevazione_id==survey.id)))
            valid={e.assegnazione_id for e in esiti if e.esito in ('PRESENTE','ASSENTE','NON RILEVATO')}
            if ids!=valid:raise ValueError('Elenco non corrispondente alla rilevazione registrata.')
            newvalues={e.assegnazione_id:('PRESENTE' if e.assegnazione_id in presenti else 'ASSENTE') for e in esiti if e.assegnazione_id in valid}
            changed=any(e.esito!=newvalues[e.assegnazione_id] for e in esiti if e.assegnazione_id in valid)
            if survey.stato=='Confermata' and changed and not motivo.strip():
                raise ValueError('Per correggere una rilevazione confermata indicare il motivo.')
            for e in esiti:
                if e.assegnazione_id in valid:e.esito=newvalues[e.assegnazione_id]
            if survey.stato=='Confermata' and changed:
                log(s,username,'mercatino.rilevazione.rettifica',str(survey.id),motivo.strip()[:300])
        if conferma:survey.stato='Confermata';survey.confermata_il=datetime.now(timezone.utc)
        survey.note=note.strip();survey.operatore=username
        log(s,username,'mercatino.rilevazione.conferma' if conferma else 'mercatino.rilevazione.bozza',str(survey.id),
            f'{giorno.isoformat()} giornata={g.id} presenti={len(presenti)} assenti={len(ids-presenti)}')
        s.commit();return len(presenti),len(ids-presenti)



def bozze_rilevazioni(uid):
    """Elenco sintetico delle sole rilevazioni ancora in bozza."""
    _check(uid, 'mercatino.read')
    with Session(engine) as s:
        q=(select(Rilevazione, Giornata, Luogo)
           .join(Giornata, Giornata.id==Rilevazione.giornata_id)
           .join(Luogo, Luogo.id==Giornata.luogo_id)
           .where(Rilevazione.stato=='Bozza')
           .order_by(Rilevazione.giorno.desc(), Luogo.nome, Giornata.giorno_settimana))
        result=[]
        for r,g,l in s.execute(q):
            counts=list(s.scalars(select(Esito.esito).where(Esito.rilevazione_id==r.id)))
            result.append(dict(id=r.id, giorno=r.giorno, giornata_id=g.id,
                luogo=l.nome, giorno_settimana=GIORNI[g.giorno_settimana],
                operatore=r.operatore, presenti=counts.count('PRESENTE'),
                assenti=counts.count('ASSENTE'), note=r.note))
        return result


def elimina_bozza(uid, username, rilevazione_id):
    """Eliminazione atomica di una bozza e dei suoi esiti; mai di una confermata."""
    _check(uid, 'mercatino.absence')
    with Session(engine) as s:
        row=s.get(Rilevazione,int(rilevazione_id))
        if row is None:
            raise ValueError('Bozza non trovata: potrebbe essere già stata eliminata.')
        if row.stato!='Bozza':
            raise ValueError('È possibile eliminare solo le rilevazioni in bozza.')
        details=f'{row.giorno.isoformat()} giornata={row.giornata_id}'
        s.query(Esito).filter(Esito.rilevazione_id==row.id).delete(synchronize_session=False)
        s.delete(row)
        log(s,username,'mercatino.rilevazione.bozza.elimina',str(rilevazione_id),details)
        s.commit()


def accertamenti(uid,giorno,luogo_id=None):
    _check(uid,'mercatino.read')
    giorno=data_input(giorno)
    with Session(engine) as s:
        q=(select(Rilevazione,Giornata,Luogo)
           .join(Giornata,Giornata.id==Rilevazione.giornata_id)
           .join(Luogo,Luogo.id==Giornata.luogo_id)
           .where(Rilevazione.giorno==giorno,Rilevazione.stato=='Confermata'))
        if luogo_id is not None:q=q.where(Luogo.id==int(luogo_id))
        output=[]
        for r,g,l in s.execute(q.order_by(Luogo.nome)):
            esiti=list(s.scalars(select(Esito).where(Esito.rilevazione_id==r.id)))
            output.append(dict(id=r.id,luogo=l.nome,giorno=giorno,settimanale=GIORNI[g.giorno_settimana],
                               operatore=r.operatore,note=r.note,
                               presenti=sum(e.esito=='PRESENTE' for e in esiti),
                               assenti=[dict(denominazione=e.denominazione,posto=e.posto) for e in esiti if e.esito=='ASSENTE'],
                               esclusi=sum(e.esito not in ('PRESENTE','ASSENTE') for e in esiti)))
        return output


def assenze_anno(uid,anno,ditta_id=None):
    _check(uid,'mercatino.read');anno=int(anno)
    with Session(engine) as s:
        q=(select(Esito,Rilevazione,Giornata,Luogo)
           .join(Rilevazione,Rilevazione.id==Esito.rilevazione_id)
           .join(Giornata,Giornata.id==Rilevazione.giornata_id)
           .join(Luogo,Luogo.id==Giornata.luogo_id)
           .where(Rilevazione.stato=='Confermata',Esito.esito=='ASSENTE',
                  Rilevazione.giorno>=date(anno,1,1),Rilevazione.giorno<=date(anno,12,31)))
        if ditta_id is not None:q=q.where(Esito.ditta_id==int(ditta_id))
        return [dict(ditta_id=e.ditta_id,denominazione=e.denominazione,posto=e.posto,
                     luogo=l.nome,giorno=r.giorno) for e,r,g,l in s.execute(q.order_by(Rilevazione.giorno,Luogo.nome))]


def importa_esiti_mobile(uid, username, payload):
    """Importa SOLO una bozza da Android; rifiuta conflitti e confermate.

    Confronta l'elenco esportato con le assegnazioni attualmente previste,
    inclusi denominazione, posto e ordine. In presenza di modifiche richiede
    una nuova esportazione dal PC.
    """
    from scambio_presenze import leggi_esiti, serialize
    _check(uid, 'mercatino.absence')
    item=leggi_esiti(serialize(payload))
    elenco=item['elenco']
    giorno=data_input(elenco['data'])
    giornata_id=int(elenco['giornata_id'])
    snapshot=anteprima(uid,giorno,giornata_id)
    if snapshot['stato']=='Confermata':
        raise ValueError('Rilevazione già confermata: importazione vietata.')
    by_id=lambda rows:{int(d['assegnazione_id']):(
        int(d['ditta_id']),str(d['denominazione']),str(d['posto']),int(d.get('ordine',0)))
        for d in rows}
    if by_id(snapshot['ditte'])!=by_id(elenco['ditte']):
        raise ValueError('Elenco sul PC modificato rispetto all’esportazione: esportare nuovamente.')
    # Eventuali bozze preesistenti vanno sostituite solo con la conferma dell'utente.
    # Questo import sostituisce gli esiti della bozza corrente, non una confermata.
    ids=set(by_id(snapshot['ditte']))
    presenti=set(item['presenti'])
    salva_rilevazione(uid,username,giorno,giornata_id,presenti,ids,conferma=False,
                     note='Importazione da SIPA Presenze Android, elenco '+elenco['elenco_id'])
    return len(presenti)
