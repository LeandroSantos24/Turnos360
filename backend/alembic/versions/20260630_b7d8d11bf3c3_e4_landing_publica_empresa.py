"""e4 landing publica empresa

Revision ID: b7d8d11bf3c3
Revises: 90834f6bc23f
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b7d8d11bf3c3'
down_revision: Union[str, None] = '90834f6bc23f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('empresa', sa.Column('descripcion', sa.Text(), nullable=True))
    op.add_column('empresa', sa.Column('direccion', sa.String(length=200), nullable=True))
    op.add_column('empresa', sa.Column('telefono_publico', sa.String(length=40), nullable=True))
    op.add_column('empresa', sa.Column('email_publico', sa.String(length=120), nullable=True))
    op.add_column('empresa', sa.Column('logo_url', sa.String(length=300), nullable=True))
    op.add_column('empresa', sa.Column('color_marca', sa.String(length=7), nullable=True))
    op.add_column('empresa', sa.Column('horarios_atencion', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('empresa', sa.Column('redes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('empresa', 'redes')
    op.drop_column('empresa', 'horarios_atencion')
    op.drop_column('empresa', 'color_marca')
    op.drop_column('empresa', 'logo_url')
    op.drop_column('empresa', 'email_publico')
    op.drop_column('empresa', 'telefono_publico')
    op.drop_column('empresa', 'direccion')
    op.drop_column('empresa', 'descripcion')
