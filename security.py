"""Account management. Never store or log cleartext passwords."""
import getpass
import hashlib
import hmac
import secrets
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database import User, AuditEvent, engine, init_database, log

ROLES = ('admin', 'operatore')
ITERATIONS = 600_000

def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)

def valid_password(password):
    return isinstance(password, str) and len(password) >= 12

def set_password(user, password):
    if not valid_password(password):
        raise ValueError('La password deve contenere almeno 12 caratteri.')
    user.salt = secrets.token_bytes(16)
    user.password_hash = digest(password, user.salt)

def bootstrap():
    init_database()
    with Session(engine) as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            print('Database già inizializzato: nessun account creato.')
            return
        username = input('Nome amministratore: ').strip()
        password = getpass.getpass('Password (almeno 12 caratteri): ')
        confirm = getpass.getpass('Ripeti password: ')
        if not username or len(username) > 80 or password != confirm or not valid_password(password):
            print('Dati non validi; nessun account creato.')
            return
        user = User(username=username, role='admin', active=True)
        set_password(user, password)
        session.add(user)
        log(session, username, 'bootstrap_admin', username)
        session.commit()
        print('Amministratore creato.')

def authenticate(username, password):
    username = (username or '').strip()
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.username == username))
        if user is None or not user.active:
            log(session, username or '(vuoto)', 'login_fallito')
            session.commit()
            return None
        if not hmac.compare_digest(digest(password or '', user.salt), user.password_hash):
            log(session, username, 'login_fallito')
            session.commit()
            return None
        log(session, username, 'login_ok')
        session.commit()
        return {'id': user.id, 'username': user.username, 'role': user.role, 'must_change_password': user.must_change_password}

def list_users():
    with Session(engine) as session:
        return [{'id': u.id, 'username': u.username, 'role': u.role, 'active': u.active,
                 'must_change_password': u.must_change_password} for u in session.scalars(select(User).order_by(User.username))]

def list_events(limit=100):
    with Session(engine) as session:
        return [{'time': e.created_at.strftime('%Y-%m-%d %H:%M:%S') + ' UTC', 'actor': e.actor,
                 'action': e.action, 'target': e.target} for e in session.scalars(
                     select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit))]

def require_admin(session, actor_id):
    actor = session.get(User, actor_id)
    if actor is None or not actor.active or actor.role != 'admin':
        raise PermissionError('Operazione riservata agli amministratori attivi.')
    return actor

def create_user(actor_id, username, password, role):
    username = (username or '').strip()
    if not username or len(username) > 80 or role not in ROLES:
        raise ValueError('Nome utente o ruolo non valido.')
    with Session(engine) as session:
        actor = require_admin(session, actor_id)
        if session.scalar(select(User.id).where(User.username == username)) is not None:
            raise ValueError('Nome utente già utilizzato.')
        user = User(username=username, role=role, active=True, must_change_password=True)
        set_password(user, password)
        session.add(user)
        log(session, actor.username, 'utente_creato', username, role)
        session.commit()

def update_user(actor_id, user_id, role, active):
    if role not in ROLES:
        raise ValueError('Ruolo non valido.')
    with Session(engine) as session:
        actor = require_admin(session, actor_id)
        user = session.get(User, user_id)
        if user is None:
            raise ValueError('Utente non trovato.')
        if user.id == actor.id and (not active or role != 'admin'):
            raise ValueError('Non puoi disattivare o declassare il tuo account.')
        if user.role == 'admin' and (role != 'admin' or not active):
            admins = session.scalar(select(func.count()).select_from(User).where(User.role == 'admin', User.active.is_(True)))
            if admins <= 1:
                raise ValueError('Deve rimanere almeno un amministratore attivo.')
        user.role, user.active = role, bool(active)
        log(session, actor.username, 'utente_modificato', user.username, f'ruolo={role}; attivo={active}')
        session.commit()

def reset_password(actor_id, user_id, new_password):
    with Session(engine) as session:
        actor = require_admin(session, actor_id)
        user = session.get(User, user_id)
        if user is None:
            raise ValueError('Utente non trovato.')
        set_password(user, new_password)
        user.must_change_password = True
        log(session, actor.username, 'password_reimpostata', user.username)
        session.commit()

def change_password(user_id, old_password, new_password):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None or not user.active or not hmac.compare_digest(digest(old_password, user.salt), user.password_hash):
            raise ValueError('Password attuale non corretta.')
        set_password(user, new_password)
        user.must_change_password = False
        log(session, user.username, 'password_modificata', user.username)
        session.commit()
