"""Registro attività economiche."""
from alembic import op
import sqlalchemy as sa
revision = '0002_attivita_economiche'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('attivita_economiche',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(200), nullable=False),
        sa.Column('titolare', sa.String(200), nullable=False, server_default=''),
        sa.Column('pec', sa.String(254), nullable=False, server_default=''),
        sa.Column('descrizione', sa.Text(), nullable=False, server_default=''),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('data_inizio', sa.Date(), nullable=True),
        sa.Column('data_cessazione', sa.Date(), nullable=True))
    op.create_index('ix_attivita_economiche_nome', 'attivita_economiche', ['nome'])

def downgrade():
    raise RuntimeError('Downgrade distruttivo non supportato; ripristinare un backup.')
