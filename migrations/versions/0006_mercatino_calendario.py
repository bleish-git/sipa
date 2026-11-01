"""Luoghi e giorni di mercato per ditta; assenze per luogo."""
from alembic import op
import sqlalchemy as sa
revision = '0006_mercatino_calendario'
down_revision = '0005_presenze_ordine'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('mercatino_calendario',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ditta_id', sa.Integer(), sa.ForeignKey('mercatino_ditte.id', ondelete='CASCADE'), nullable=False),
        sa.Column('luogo', sa.String(150), nullable=False),
        sa.Column('giorno_settimana', sa.Integer(), nullable=False),
        sa.UniqueConstraint('ditta_id', 'luogo', 'giorno_settimana', name='uq_mercatino_calendario'))
    op.create_index('ix_mercatino_calendario_ditta_id', 'mercatino_calendario', ['ditta_id'])
    with op.batch_alter_table('mercatino_assenze') as batch:
        batch.add_column(sa.Column('luogo', sa.String(150), nullable=False, server_default=''))
    connection = op.get_bind()
    connection.execute(sa.text('UPDATE mercatino_assenze SET luogo = (SELECT luogo FROM mercatino_ditte WHERE mercatino_ditte.id = mercatino_assenze.ditta_id)'))
    with op.batch_alter_table('mercatino_assenze') as batch:
        batch.drop_constraint('uq_mercatino_ditta_giorno', type_='unique')
        batch.create_unique_constraint('uq_mercatino_ditta_giorno_luogo', ['ditta_id', 'giorno', 'luogo'])

def downgrade():
    raise RuntimeError('Downgrade distruttivo non supportato: ripristinare un backup.')
