"""e4 galeria de empresa y foto del recurso

Revision ID: c2e94a7f51b8
Revises: b7d8d11bf3c3
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c2e94a7f51b8'
down_revision: Union[str, None] = 'b7d8d11bf3c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Galería de fotos de la landing pública: lista de URLs (JSONB).
    op.add_column('empresa', sa.Column('galeria', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # Foto del profesional para la sección "Equipo" de la landing.
    op.add_column('recurso', sa.Column('foto_url', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('recurso', 'foto_url')
    op.drop_column('empresa', 'galeria')
