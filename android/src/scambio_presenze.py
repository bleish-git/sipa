"""Protocollo JSON SIPA Desktop <-> SIPA Presenze Android, versione 1.

Il digest controlla corrispondenza/alterazioni accidentali, NON autentica il mittente.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from uuid import uuid4

FORMAT = 1
MAX_BYTES = 2_000_000


def _bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(obj):
    return hashlib.sha256(_bytes(obj)).hexdigest()


def parse(raw):
    if isinstance(raw, str):
        raw = raw.encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('File troppo grande.')
    try:
        item = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError('File JSON non valido.') from exc
    if not isinstance(item, dict) or item.get('versione_formato') != FORMAT:
        raise ValueError('Formato di scambio SIPA non supportato.')
    return item


def interpreta_data(raw):
    """Accetta GG/MM/AAAA (attuale), AAAA-MM-GG e AAAA/MM/GG (file legacy).

    La data del documento non viene mai riscritta durante la lettura:
    cambiare la rappresentazione modificherebbe l'impronta SHA-256.
    """
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        raise ValueError('Data assente o non valida.')
    raw = raw.strip()
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, formato).date()
        except ValueError:
            pass
    raise ValueError('Data non valida: usare GG/MM/AAAA.')


def data_visibile(raw):
    return interpreta_data(raw).strftime('%d/%m/%Y')


def _check_list(item, avvisi=None):
    if item.get('tipo') != 'sipa_elenco_presenze' or not isinstance(item.get('elenco_id'), str):
        raise ValueError('Il file non è un elenco SIPA.')
    try:
        interpreta_data(item['data'])
        giornata = int(item['giornata_id'])
        ditte = item['ditte']
        if not isinstance(ditte, list) or not ditte or len(ditte) > 10000:
            raise ValueError()
        ids = [int(x['assegnazione_id']) for x in ditte]
        if len(set(ids)) != len(ids) or any(x <= 0 for x in ids) or giornata <= 0:
            raise ValueError()
        for x in ditte:
            if not isinstance(x['denominazione'], str) or not isinstance(x['posto'], str):
                raise ValueError()
            int(x['ordine'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Elenco SIPA incompleto o non valido.') from exc
    if digest({k:v for k,v in item.items() if k!='impronta'}) != item.get('impronta'):
        if avvisi is None:
            raise ValueError('Impronta dell’elenco non valida.')
        avvisi.append('Impronta dell’elenco originale non corrispondente.')
    return item


def leggi_elenco(raw, avvisi=None):
    return _check_list(parse(raw), avvisi=avvisi)


def crea_elenco(giorno, giornata_id, luogo, descrizione_giornata, ditte):
    item = dict(tipo='sipa_elenco_presenze', versione_formato=FORMAT,
                elenco_id=str(uuid4()), data=data_visibile(giorno), giornata_id=int(giornata_id),
                luogo=str(luogo), giornata=str(descrizione_giornata),
                generato_il=datetime.now(timezone.utc).isoformat(), ditte=[
                    dict(assegnazione_id=int(d['assegnazione_id']), ditta_id=int(d['ditta_id']),
                         denominazione=str(d['denominazione']), posto=str(d['posto']),
                         ordine=int(d.get('ordine',0))) for d in ditte])
    item['impronta'] = digest(item)
    return item


def crea_esiti(elenco, presenti):
    elenco = leggi_elenco(_bytes(elenco))
    ids={int(d['assegnazione_id']) for d in elenco['ditte']}
    presenti={int(x) for x in presenti}
    if not presenti.issubset(ids):
        raise ValueError('Spunte estranee all’elenco.')
    item=dict(tipo='sipa_esiti_presenze', versione_formato=FORMAT,
              elenco_id=elenco['elenco_id'], impronta_elenco=elenco['impronta'],
              elenco=elenco, presenti=sorted(presenti),
              esportato_il=datetime.now(timezone.utc).isoformat())
    item['impronta'] = digest(item)
    return item


def leggi_esiti(raw, *, accetta_impronte_diverse=False, avvisi=None):
    """Valida gli esiti. La deroga alle sole impronte richiede consenso esplicito.

    Gli ID, i tipi, le presenze, la data e la corrispondenza con il DB
    sono sempre controllati; non si modifica mai il JSON ricevuto.
    """
    rilievi = []
    item=parse(raw)
    if item.get('tipo') != 'sipa_esiti_presenze':
        raise ValueError('Il file non contiene esiti di presenza.')
    elenco=leggi_elenco(_bytes(item.get('elenco')), avvisi=rilievi if accetta_impronte_diverse else None)
    if item.get('elenco_id') != elenco['elenco_id']:
        raise ValueError('Identificativo degli esiti diverso da quello dell’elenco: importazione vietata.')
    if item.get('impronta_elenco') != elenco['impronta']:
        rilievi.append('Riferimento all’impronta dell’elenco diverso da quello incorporato.')
    if digest({k:v for k,v in item.items() if k!='impronta'})!=item.get('impronta'):
        rilievi.append('Impronta SHA-256 del file esiti non corrispondente.')
    try:
        presenti=item['presenti']
        if not isinstance(presenti,list) or len(set(presenti))!=len(presenti):
            raise ValueError()
        ids={d['assegnazione_id'] for d in elenco['ditte']}
        if any(type(x) is not int or x not in ids for x in presenti):
            raise ValueError()
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError('Elenco presenze non valido.') from exc
    if rilievi and not accetta_impronte_diverse:
        raise ValueError('Impronta non riconosciuta: importazione annullata.')
    if avvisi is not None:
        avvisi.extend(rilievi)
    return item


def serialize(item):
    return json.dumps(item, ensure_ascii=False, indent=2).encode('utf-8')
