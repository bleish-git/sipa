"""Schema iniziale SIPA: solo tabelle core esistenti nella prima revisione.

Le tabelle dei moduli aggiunti dopo la baseline sono create esclusivamente
nelle rispettive revisioni Alembic, anche durante una nuova installazione.
"""
from alembic import op
from database import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Esplicito anziché 'tutte tranne ...': le nuove classi ORM non devono
# mai produrre in anticipo tabelle appartenenti a revisioni successive.
BASELINE_TABLES = frozenset({
    'users',
    'permissions',
    'role_permissions',
    'audit_events',
    'login_throttle',
})


def upgrade():
    bind = op.get_bind()
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    missing = BASELINE_TABLES - tables.keys()
    if missing:
        raise RuntimeError(f'Modelli delle tabelle iniziali mancanti: {sorted(missing)}')
    Base.metadata.create_all(
        bind=bind,
        tables=[t for t in Base.metadata.sorted_tables if t.name in BASELINE_TABLES],
        checkfirst=True,
    )


def downgrade():
    raise RuntimeError('Downgrade distruttivo non supportato; ripristinare un backup.')
