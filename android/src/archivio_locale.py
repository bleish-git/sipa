"""Una sola bozza locale; scrittura atomica e nessun database remoto."""
import json
import os
from pathlib import Path
from scambio_presenze import leggi_elenco, serialize


def _folder():
    # Su Android la home Python deve appartenere allo spazio privato dell'app.
    base = Path.home() / '.sipa_presenze'
    base.mkdir(parents=True, exist_ok=True)
    return base


def _path():
    return _folder() / 'bozza.json'


def leggi():
    p = _path()
    if not p.exists():
        return None
    data=json.loads(p.read_text(encoding='utf-8'))
    leggi_elenco(serialize(data['elenco']))
    valid={int(x['assegnazione_id']) for x in data['elenco']['ditte']}
    if not isinstance(data['presenti'],list) or not set(data['presenti']).issubset(valid):
        raise ValueError('Bozza locale non valida.')
    return data


def salva(elenco, presenti):
    leggi_elenco(serialize(elenco))
    valid={int(x['assegnazione_id']) for x in elenco['ditte']}
    if not set(presenti).issubset(valid):
        raise ValueError('Spunte non valide.')
    p=_path()
    tmp=p.with_suffix('.tmp')
    with tmp.open('wb') as f:
        f.write(serialize({'elenco':elenco,'presenti':sorted(set(presenti))}))
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)


def cancella():
    _path().unlink(missing_ok=True)
