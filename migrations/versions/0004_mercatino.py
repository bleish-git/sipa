"""Anagrafica mercatino e registro delle assenze per data."""
from alembic import op
import sqlalchemy as sa

revision = '0004_mercatino'
down_revision = '0003_sospensione_tipologia'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('mercatino_ditte',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('denominazione', sa.String(200), nullable=False),
        sa.Column('numero_posto', sa.String(30), nullable=False),
        sa.Column('luogo', sa.String(150), nullable=False),
        sa.Column('stato', sa.String(15), nullable=False, server_default='Attivo'))
    op.create_index('ix_mercatino_ditte_denominazione', 'mercatino_ditte', ['denominazione'])
    op.create_index('ix_mercatino_ditte_luogo', 'mercatino_ditte', ['luogo'])
    op.create_table('mercatino_assenze',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ditta_id', sa.Integer(), sa.ForeignKey('mercatino_ditte.id', ondelete='CASCADE'), nullable=False),
        sa.Column('giorno', sa.Date(), nullable=False),
        sa.UniqueConstraint('ditta_id', 'giorno', name='uq_mercatino_ditta_giorno'))
    op.create_index('ix_mercatino_assenze_ditta_id', 'mercatino_assenze', ['ditta_id'])
    op.create_index('ix_mercatino_assenze_giorno', 'mercatino_assenze', ['giorno'])

def downgrade():
    raise RuntimeError('Downgrade distruttivo non supportato: ripristinare un backup.')
