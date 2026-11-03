"""Tipologia e intervallo sospensione delle attività economiche."""
from alembic import op
import sqlalchemy as sa

revision = '0003_sospensione_tipologia'
down_revision = '0002_attivita_economiche'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('attivita_economiche', sa.Column('data_sospensione_inizio', sa.Date(), nullable=True))
    op.add_column('attivita_economiche', sa.Column('data_sospensione_fine', sa.Date(), nullable=True))
    op.add_column('attivita_economiche', sa.Column('tipologia', sa.String(length=80), nullable=False, server_default='Non specificata'))


def downgrade():
    raise RuntimeError('Downgrade distruttivo non supportato: ripristinare un backup.')
