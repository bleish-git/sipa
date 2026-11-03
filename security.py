"""Account management. Never store or log cleartext passwords."""
import getpass
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database import User, AuditEvent, LoginThrottle, RolePermission, PERMISSIONS, engine, init_database, log

ROLES = ('admin', 'responsabile', 'operatore', 'consultazione')
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

def _utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def _throttle_key(username):
    # Account-scoped throttling works across all clients using the same central DB.
    # Do not rely on client-supplied IPs, which can be spoofed.
    return 'account:' + (username or '').strip().casefold()[:110]

def authenticate(username, password):
    username = (username or '').strip()
    now = datetime.now(timezone.utc)
    key = _throttle_key(username)
    with Session(engine) as session:
        # SQLite BEGIN IMMEDIATE serializes writers, preventing parallel attempts bypassing the counter.
        if engine.dialect.name == 'sqlite':
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
        throttle = session.get(LoginThrottle, key)
        if throttle is None:
            throttle = LoginThrottle(identifier=key, failures=0)
            session.add(throttle)
            session.flush()
        user = session.scalar(select(User).where(User.username == username))
        blocked = throttle.blocked_until and _utc(throttle.blocked_until) > now
        # Always calculate a hash, including unknown accounts, to reduce timing differences.
        candidate = digest(password or '', user.salt if user else bytes(16))
        valid = bool(user and user.active and hmac.compare_digest(candidate, user.password_hash))
        if blocked or not valid:
            if not blocked:
                throttle.failures += 1
                if throttle.failures >= 5:
                    throttle.blocked_until = now + timedelta(minutes=15)
                    throttle.failures = 0
            log(session, username or '(vuoto)', 'login_rifiutato', details='credenziali o limitazione')
            session.commit()
            return None
        throttle.failures = 0
        throttle.blocked_until = None
        log(session, username, 'login_ok')
        session.commit()
        return {'id': user.id, 'username': user.username, 'role': user.role,
                'must_change_password': user.must_change_password}

def has_permission(user_id, code):
    with Session(engine) as session:
        user = session.get(User, user_id)
        return bool(user and user.active and session.get(RolePermission, (user.role, code)))

def require_permission(session, actor_id, code):
    actor = session.get(User, actor_id)
    if not actor or not actor.active or session.get(RolePermission, (actor.role, code)) is None:
        raise PermissionError('Permesso non concesso: ' + code)
    return actor

def role_permissions():
    with Session(engine) as session:
        return {role: [r.permission_code for r in session.scalars(
            select(RolePermission).where(RolePermission.role == role).order_by(RolePermission.permission_code))]
            for role in ROLES}

def set_role_permissions(actor_id, role, codes):
    if role not in ROLES or not set(codes).issubset(PERMISSIONS):
        raise ValueError('Ruolo o permessi non validi.')
    if role == 'admin' and set(codes) != set(PERMISSIONS):
        raise ValueError('I permessi amministratore sono fissi per evitare blocchi di gestione.')
    with Session(engine) as session:
        actor = require_permission(session, actor_id, 'permissions.manage')
        for r in list(session.scalars(select(RolePermission).where(RolePermission.role == role))):
            session.delete(r)
        session.flush()
        for code in sorted(set(codes)):
            session.add(RolePermission(role=role, permission_code=code))
        log(session, actor.username, 'permessi_ruolo_modificati', role, ','.join(sorted(codes)))
        session.commit()

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
    if actor is None or not actor.active or session.get(RolePermission, (actor.role, 'users.manage')) is None:
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
