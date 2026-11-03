"""Ordine numerico ditte e giornate di rilevazione presenze per luogo."""
from alembic import op
import sqlalchemy as sa

revision = '0005_presenze_ordine'
down_revision = '0004_mercatino'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('mercatino_ditte') as batch:
        batch.add_column(sa.Column('ordine_rilevazione', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('mercatino_rilevazioni',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('giorno', sa.Date(), nullable=False),
        sa.Column('luogo', sa.String(150), nullable=False),
        sa.UniqueConstraint('giorno', 'luogo', name='uq_mercatino_rilevazione_giorno_luogo'))

def downgrade():
    raise RuntimeError('Downgrade distruttivo non supportato; ripristinare un backup.')
