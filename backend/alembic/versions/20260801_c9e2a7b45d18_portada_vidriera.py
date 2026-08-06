"""Foto de portada de la vidriera (fondo del hero).

Agrega empresa.portada_url: la imagen que se muestra de fondo en la cabecera
de la página pública del negocio. Nullable a propósito: las empresas que ya
existen siguen viendo el hero blanco de siempre hasta que el dueño cargue una.

Mismo criterio que logo_url y galeria: guardamos la URL, no el archivo. El
hosting de imágenes es externo (Cloudinary).

Revision ID: c9e2a7b45d18
Revises: b6d3f8a2c517
Create Date: 2026-08-01

"""

from alembic import op
import sqlalchemy as sa

revision: str = "c9e2a7b45d18"
down_revision: str | None = "b6d3f8a2c517"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column("portada_url", sa.String(length=300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("empresa", "portada_url")
