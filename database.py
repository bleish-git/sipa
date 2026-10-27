"""Persistence layer: SQLAlchemy, SQLite for development, PostgreSQL-ready."""
import os
from datetime import date, datetime, timezone
from pathlib import Path
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, create_engine, select, event, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

BASE_DIR = Path(__file__).resolve().parent
from db_settings import database_url
DATABASE_URL = database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    password_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    role: Mapped[str] = mapped_column(String(30), default='operatore', nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AttivitaEconomica(Base):
    __tablename__ = 'attivita_economiche'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    titolare: Mapped[str] = mapped_column(String(200), default='', nullable=False)
    pec: Mapped[str] = mapped_column(String(254), default='', nullable=False)
    descrizione: Mapped[str] = mapped_column(Text, default='', nullable=False)
    note: Mapped[str] = mapped_column(Text, default='', nullable=False)
    data_inizio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_cessazione: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_sospensione_inizio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_sospensione_fine: Mapped[date | None] = mapped_column(Date, nullable=True)
    tipologia: Mapped[str] = mapped_column(String(80), nullable=False, default='Non specificata')

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(String(80), default='', nullable=False)
    details: Mapped[str] = mapped_column(String(300), default='', nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)

class Permission(Base):
    __tablename__ = 'permissions'
    code: Mapped[str] = mapped_column(String(90), primary_key=True)
    description: Mapped[str] = mapped_column(String(180), nullable=False)

class RolePermission(Base):
    __tablename__ = 'role_permissions'
    role: Mapped[str] = mapped_column(String(30), primary_key=True)
    permission_code: Mapped[str] = mapped_column(String(90), ForeignKey('permissions.code'), primary_key=True)

class LoginThrottle(Base):
    __tablename__ = 'login_throttle'
    identifier: Mapped[str] = mapped_column(String(130), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

PERMISSIONS = {
    'dashboard.view':'Consultare dashboard',
    'attivita.read':'Consultare attività', 'attivita.create':'Inserire attività',
    'attivita.update':'Modificare attività', 'attivita.void':'Annullare attività',
    'verbali.read':'Consultare verbali', 'verbali.create':'Inserire verbali',
    'verbali.update':'Modificare verbali', 'verbali.void':'Annullare verbali',
    'accertamenti.read':'Consultare accertamenti', 'accertamenti.create':'Inserire accertamenti',
    'documenti.read':'Consultare documenti', 'documenti.export':'Esportare documenti',
    'users.manage':'Gestire utenti', 'permissions.manage':'Gestire permessi',
    'audit.read':'Consultare audit', 'backup.manage':'Gestire backup',
}
DEFAULT_ROLES = {
    'admin': set(PERMISSIONS),
    'responsabile': set(PERMISSIONS)-{'users.manage','permissions.manage','backup.manage'},
    'operatore': {'dashboard.view','attivita.read','attivita.create','attivita.update',
                 'verbali.read','verbali.create','verbali.update',
                 'accertamenti.read','accertamenti.create','documenti.read'},
    'consultazione': {'dashboard.view','attivita.read','verbali.read','accertamenti.read','documenti.read'},
}

def init_database():
    from schema import check_current
    check_current()
    with Session(engine) as session:
        for code, description in PERMISSIONS.items():
            if session.get(Permission, code) is None:
                session.add(Permission(code=code, description=description))
        for role, codes in DEFAULT_ROLES.items():
            for code in codes:
                if session.get(RolePermission, (role,code)) is None:
                    session.add(RolePermission(role=role, permission_code=code))
        session.commit()


def log(session: Session, actor: str, action: str, target: str = '', details: str = ''):
    # Hash chain: detects accidental or unauthorized changes unless attacker also controls the key.
    import hashlib, hmac, json
    from datetime import timezone
    from pathlib import Path
    key_path = BASE_DIR / '.sipa_audit_key'
    if not key_path.exists():
        import secrets
        try:
            with key_path.open('xb') as f:
                f.write(secrets.token_bytes(32))
            os.chmod(key_path, 0o600)
        except FileExistsError:
            pass
    key = key_path.read_bytes()
    session.flush()
    previous = session.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
    previous_hash = previous.entry_hash if previous else 'GENESIS'
    created = datetime.now(timezone.utc)
    entry = AuditEvent(created_at=created, actor=actor, action=action, target=target,
                       details=details[:300], previous_hash=previous_hash)
    payload = json.dumps([created.isoformat(), actor, action, target, details[:300], previous_hash], ensure_ascii=False)
    entry.entry_hash = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    session.add(entry)
