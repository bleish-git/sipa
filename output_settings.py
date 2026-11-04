"""Configurazione locale del percorso di esportazione (indipendente dal DB)."""
import json
import os
from pathlib import Path

BASE=Path(__file__).resolve().parent
SETTINGS=BASE/'sipa_export_settings.json'
DEFAULT=Path.home()/'SIPA_Stampe'


def get_output_directory():
    if not SETTINGS.exists():
        return DEFAULT
    try:
        raw=json.loads(SETTINGS.read_text(encoding='utf-8'))
        path=str(raw.get('output_directory','')).strip()
        return Path(path).expanduser() if path else DEFAULT
    except (OSError,ValueError,TypeError,AttributeError):
        return DEFAULT


def set_output_directory(value):
    if not str(value or '').strip():
        raise ValueError('Indicare una cartella di destinazione.')
    path=Path(str(value).strip()).expanduser().resolve()
    if not path.is_dir():
        raise ValueError('La cartella indicata non esiste: '+str(path))
    if not os.access(path,os.W_OK):
        raise PermissionError('Non è possibile scrivere nella cartella indicata.')
    tmp=SETTINGS.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps({'output_directory':str(path)},ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,SETTINGS)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def export_path(prefix, extension):
    from datetime import datetime
    folder=get_output_directory()
    if not folder.is_dir():
        raise FileNotFoundError('Cartella esportazioni non disponibile: '+str(folder))
    filename=f'{prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}.{extension.lstrip(".")}'
    return folder/filename
