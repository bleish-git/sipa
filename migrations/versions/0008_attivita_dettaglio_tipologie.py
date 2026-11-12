"""Sezioni attività economiche e catalogo tipologie (non distruttivo)."""
from alembic import op
import sqlalchemy as sa

revision = '0008_attivita_dettaglio_tipologie'
down_revision = '0007_mercatino_ristrutturazione'
branch_labels = None
depends_on = None


def upgrade():
    colonne = {
        'numero_fascicolo': 60, 'indirizzo': 300,
        'protocollo_inizio': 120, 'protocollo_cessazione': 120,
    }
    with op.batch_alter_table('attivita_economiche') as batch:
        for nome, lunghezza in colonne.items():
            batch.add_column(sa.Column(nome, sa.String(lunghezza), nullable=False, server_default=''))
        for nome in ('riscontro_inizio', 'riscontro_cessazione', 'note_provvedimenti', 'altri_dati'):
            batch.add_column(sa.Column(nome, sa.Text(), nullable=False, server_default=''))
    op.create_table('attivita_tipologie',
        sa.Column('nome', sa.String(80), primary_key=True),
        sa.Column('descrizione', sa.Text(), nullable=False, server_default=''))
    # Mantiene sia le tipologie predefinite sia quelle già presenti nei registri.
    conn = op.get_bind()
    tab = sa.table('attivita_tipologie', sa.column('nome', sa.String(80)), sa.column('descrizione', sa.Text()))
    result = conn.execute(sa.text('SELECT DISTINCT tipologia FROM attivita_economiche WHERE tipologia IS NOT NULL'))
    nomi = ['Non specificata', 'Commercio', 'Somministrazione', 'Artigianato', 'Servizi', 'Altro']
    nomi.extend(row[0] for row in result if row[0] and row[0] not in nomi)
    for nome in dict.fromkeys(nomi):
        conn.execute(tab.insert().values(nome=nome, descrizione=''))


def downgrade():
    raise RuntimeError('Downgrade non supportato: ripristinare il backup precedente alla migrazione.')
