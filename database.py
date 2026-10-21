"""Persistence layer: SQLAlchemy, SQLite for development, PostgreSQL-ready."""
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get('SIPA_DB_URL', os.environ.get('GESTIONALE_DB_URL', f'sqlite:///{BASE_DIR / "sipa.db"}'))
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

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(String(80), default='', nullable=False)
    details: Mapped[str] = mapped_column(String(300), default='', nullable=False)

def init_database():
    Base.metadata.create_all(engine)

def log(session: Session, actor: str, action: str, target: str = '', details: str = ''):
    session.add(AuditEvent(actor=actor, action=action, target=target, details=details[:300]))
