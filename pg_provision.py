"""Preflight e creazione esplicita database PostgreSQL (non crea mai tabelle)."""
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL


def _url(cfg, database):
    secret = os.environ.get(cfg['password_env'])
    if not secret:
        raise ValueError('Impostare la variabile ambiente ' + cfg['password_env'])
    return URL.create('postgresql+psycopg', username=cfg['username'], password=secret,
                      host=cfg['host'], port=int(cfg['port']), database=database,
                      query={'sslmode': cfg['sslmode'], 'connect_timeout': '5'})


def check_database(cfg):
    """Individua un DB esistente; se assente, controlla CREATEDB senza modifiche."""
    if cfg['driver'] != 'postgresql':
        raise ValueError('Richiesto PostgreSQL')
    name = str(cfg['database']).strip()
    if not name or len(name.encode('utf-8')) > 63 or name in ('postgres', 'template0', 'template1'):
        raise ValueError('Nome database PostgreSQL non consentito per una nuova installazione.')
    admin = create_engine(_url(cfg, 'postgres'), pool_pre_ping=True)
    try:
        with admin.connect() as c:
            exists = bool(c.execute(text('SELECT 1 FROM pg_database WHERE datname=:n'), {'n': name}).scalar())
            role = c.execute(text('SELECT rolcreatedb, rolsuper FROM pg_roles WHERE rolname=current_user')).first()
            authorized = bool(role and (role[0] or role[1]))
    finally:
        admin.dispose()
    if exists:
        target = create_engine(_url(cfg, name), pool_pre_ping=True)
        try:
            with target.connect() as conn:
                # Include all user-defined schemas; don't accidentally initialize over existing data.
                count = conn.execute(text('''
                    SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%'
                      AND n.nspname NOT LIKE 'pg_temp_%'
                      AND c.relkind IN ('r','p','v','m','S','f')
                ''' )).scalar_one()
                if count:
                    raise ValueError('Il database PostgreSQL esiste ma non è vuoto: usare Collegamento esistente.')
                if not conn.execute(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")).scalar_one():
                    raise PermissionError('Database vuoto ma utente senza permesso CREATE sullo schema public. Contattare l’amministratore PostgreSQL.')
        finally:
            target.dispose()
        return {'exists': True, 'can_create': authorized}
    return {'exists': False, 'can_create': authorized}


def create_database(cfg):
    """Dopo esplicita conferma UI/CLI: create database sul database 'postgres'."""
    status = check_database(cfg)
    if status['exists']:
        return False
    if not status['can_create']:
        raise PermissionError('L’utente PostgreSQL non dispone del privilegio CREATEDB. Contattare l’amministratore PostgreSQL.')
    name = str(cfg['database']).strip()
    from psycopg import sql
    engine = create_engine(_url(cfg, 'postgres'), isolation_level='AUTOCOMMIT')
    try:
        with engine.connect() as c:
            # psycopg SQL Identifier quotes names safely. Database CREATE is not transactional.
            driver_conn = c.connection.driver_connection
            with driver_conn.cursor() as cur:
                cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    finally:
        engine.dispose()
    return True
