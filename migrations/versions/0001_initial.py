"""Baseline SIPA v0.3 schema (includes all existing tables)."""
from alembic import op
from database import Base
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[table for table in Base.metadata.sorted_tables if table.name not in {'attivita_economiche', 'mercatino_ditte', 'mercatino_assenze'}], checkfirst=True)

def downgrade():
    raise RuntimeError("Downgrade distruttivo non supportato; ripristinare un backup.")
