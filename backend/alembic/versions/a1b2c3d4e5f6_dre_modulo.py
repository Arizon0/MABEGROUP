"""dre: cmv congelado nas vendas, campos de produto e despesas da DRE

Revision ID: a1b2c3d4e5f6
Revises: 61fe44397e90
Create Date: 2026-08-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '61fe44397e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Produtos: gestão simples (ativo / observações).
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False)
        )
        batch_op.add_column(
            sa.Column('observacoes', sa.String(length=2048), nullable=True)
        )

    # Vendas: custo unitário e CMV congelados no momento da importação.
    with op.batch_alter_table('vendas', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('custo_unitario', sa.Numeric(precision=12, scale=4),
                      server_default='0', nullable=False)
        )
        batch_op.add_column(
            sa.Column('cmv', sa.Numeric(precision=12, scale=2),
                      server_default='0', nullable=False)
        )

    # Despesas editáveis da DRE mensal.
    op.create_table(
        'dre_despesas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('grupo', sa.String(length=30), nullable=False),
        sa.Column('categoria', sa.String(length=80), nullable=False),
        sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True),
                  server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ano', 'mes', 'grupo', 'categoria', name='uq_dre_despesa'),
    )
    with op.batch_alter_table('dre_despesas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dre_despesas_ano'), ['ano'], unique=False)
        batch_op.create_index(batch_op.f('ix_dre_despesas_mes'), ['mes'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('dre_despesas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dre_despesas_mes'))
        batch_op.drop_index(batch_op.f('ix_dre_despesas_ano'))
    op.drop_table('dre_despesas')

    with op.batch_alter_table('vendas', schema=None) as batch_op:
        batch_op.drop_column('cmv')
        batch_op.drop_column('custo_unitario')

    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.drop_column('observacoes')
        batch_op.drop_column('ativo')
