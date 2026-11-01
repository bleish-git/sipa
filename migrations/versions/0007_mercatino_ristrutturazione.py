"""Mercatino 0.60: azzeramento SOLO registro mercatino e nuovo modello storico.

Requires environment variable SIPA_RESET_MERCATINO=CONFERMO_AZZERAMENTO.
This migration MUST be run offline with all SIPA clients stopped after a verified backup.
"""
import os
from alembic import op
import sqlalchemy as sa

revision = '0007_mercatino_ristrutturazione'
down_revision = '0006_mercatino_calendario'
branch_labels = None
depends_on = None

def upgrade():
    if os.environ.get('SIPA_RESET_MERCATINO') != 'CONFERMO_AZZERAMENTO':
        raise RuntimeError('Migrazione distruttiva Mercatino: impostare SIPA_RESET_MERCATINO=CONFERMO_AZZERAMENTO dopo backup verificato.')
    # I dati degli altri moduli, utenti e audit restano intatti.
    for name in ('mercatino_assenze','mercatino_calendario','mercatino_rilevazioni','mercatino_ditte'):
        op.drop_table(name)
    op.create_table('mercatino_ditte',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('denominazione',sa.String(200),nullable=False),
        sa.Column('stato',sa.String(15),nullable=False),
        sa.Column('note',sa.Text(),nullable=False))
    op.create_index('ix_mercatino_ditte_denominazione','mercatino_ditte',['denominazione'])
    op.create_table('mercatino_luoghi',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('nome',sa.String(150),nullable=False,unique=True),
        sa.Column('descrizione',sa.Text(),nullable=False))
    op.create_table('mercatino_giornate',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('luogo_id',sa.Integer(),sa.ForeignKey('mercatino_luoghi.id'),nullable=False),
        sa.Column('giorno_settimana',sa.Integer(),nullable=False),
        sa.UniqueConstraint('luogo_id','giorno_settimana',name='uq_mercatino_giornata'))
    op.create_index('ix_mercatino_giornate_luogo_id','mercatino_giornate',['luogo_id'])
    op.create_table('mercatino_assegnazioni',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('ditta_id',sa.Integer(),sa.ForeignKey('mercatino_ditte.id'),nullable=False),
        sa.Column('giornata_id',sa.Integer(),sa.ForeignKey('mercatino_giornate.id'),nullable=False),
        sa.Column('posto',sa.String(30),nullable=False),
        sa.Column('ordine',sa.Integer(),nullable=False),
        sa.Column('valida_dal',sa.Date()),sa.Column('valida_al',sa.Date()))
    op.create_index('ix_mercatino_assegnazioni_ditta_id','mercatino_assegnazioni',['ditta_id'])
    op.create_index('ix_mercatino_assegnazioni_giornata_id','mercatino_assegnazioni',['giornata_id'])
    op.create_table('mercatino_provvedimenti',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('tipo',sa.String(20),nullable=False),
        sa.Column('numero_atto',sa.String(100),nullable=False),
        sa.Column('data_atto',sa.Date(),nullable=False),
        sa.Column('efficace_dal',sa.Date(),nullable=False),
        sa.Column('efficace_al',sa.Date()),
        sa.Column('motivazione',sa.Text(),nullable=False))
    op.create_table('mercatino_provvedimenti_assegnazioni',
        sa.Column('provvedimento_id',sa.Integer(),sa.ForeignKey('mercatino_provvedimenti.id'),primary_key=True),
        sa.Column('assegnazione_id',sa.Integer(),sa.ForeignKey('mercatino_assegnazioni.id'),primary_key=True))
    op.create_table('mercatino_rilevazioni',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('giorno',sa.Date(),nullable=False),
        sa.Column('giornata_id',sa.Integer(),sa.ForeignKey('mercatino_giornate.id'),nullable=False),
        sa.Column('stato',sa.String(15),nullable=False),
        sa.Column('operatore',sa.String(80),nullable=False),
        sa.Column('confermata_il',sa.DateTime(timezone=True)),
        sa.Column('note',sa.Text(),nullable=False),
        sa.UniqueConstraint('giorno','giornata_id',name='uq_mercatino_rilevazione'))
    op.create_table('mercatino_esiti',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('rilevazione_id',sa.Integer(),sa.ForeignKey('mercatino_rilevazioni.id'),nullable=False),
        sa.Column('assegnazione_id',sa.Integer(),sa.ForeignKey('mercatino_assegnazioni.id'),nullable=False),
        sa.Column('ditta_id',sa.Integer(),sa.ForeignKey('mercatino_ditte.id'),nullable=False),
        sa.Column('denominazione',sa.String(200),nullable=False),
        sa.Column('posto',sa.String(30),nullable=False),
        sa.Column('esito',sa.String(30),nullable=False),
        sa.UniqueConstraint('rilevazione_id','assegnazione_id',name='uq_mercatino_esito'))
    op.create_index('ix_mercatino_esiti_rilevazione_id','mercatino_esiti',['rilevazione_id'])

def downgrade():
    raise RuntimeError('Downgrade vietato: usare il backup precedente alla ristrutturazione Mercatino.')
