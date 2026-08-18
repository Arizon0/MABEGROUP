"""analise venda a venda: NF, aliquota de imposto e investimento em ads

Revision ID: b7c1e2f30a44
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1e2f30a44'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nota fiscal da venda (nullable: a maioria dos exports não traz).
    with op.batch_alter_table('vendas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('numero_nf', sa.String(length=30), nullable=True))

    # Alíquota efetiva de imposto por competência, com vigência.
    op.create_table(
        'aliquotas_imposto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('aliquota_pct', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('observacao', sa.String(length=255), nullable=True),
        sa.Column(
            'atualizado_em',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ano', 'mes', name='uq_aliquota_competencia'),
    )
    op.create_index('ix_aliquotas_imposto_ano', 'aliquotas_imposto', ['ano'])
    op.create_index('ix_aliquotas_imposto_mes', 'aliquotas_imposto', ['mes'])

    # Investimento em publicidade por competência e escopo.
    op.create_table(
        'ads_investimento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('canal', sa.String(length=20), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('escopo', sa.String(length=10), nullable=False),
        # '' e não NULL: em Postgres dois NULL não colidem no UNIQUE, o que
        # deixaria duplicar o lançamento do canal e dobrar o rateio.
        sa.Column('referencia', sa.String(length=60), nullable=False, server_default=''),
        sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('receita_ads', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            'atualizado_em',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canal', 'ano', 'mes', 'escopo', 'referencia', name='uq_ads_escopo'),
    )
    op.create_index('ix_ads_investimento_canal', 'ads_investimento', ['canal'])
    op.create_index('ix_ads_investimento_ano', 'ads_investimento', ['ano'])
    op.create_index('ix_ads_investimento_mes', 'ads_investimento', ['mes'])


def downgrade() -> None:
    op.drop_index('ix_ads_investimento_mes', table_name='ads_investimento')
    op.drop_index('ix_ads_investimento_ano', table_name='ads_investimento')
    op.drop_index('ix_ads_investimento_canal', table_name='ads_investimento')
    op.drop_table('ads_investimento')

    op.drop_index('ix_aliquotas_imposto_mes', table_name='aliquotas_imposto')
    op.drop_index('ix_aliquotas_imposto_ano', table_name='aliquotas_imposto')
    op.drop_table('aliquotas_imposto')

    with op.batch_alter_table('vendas', schema=None) as batch_op:
        batch_op.drop_column('numero_nf')
