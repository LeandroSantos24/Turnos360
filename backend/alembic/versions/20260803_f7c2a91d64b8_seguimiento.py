"""Seguimiento publicitario por negocio: Meta Pixel y Google Tag.

Cada negocio conecta SU pixel para medir las visitas y las reservas de SU
vidriera en sus propias campañas. Los IDs son públicos por naturaleza (viajan
en el HTML de cualquier sitio que los usa), así que no van encriptados.

Lo que SÍ importa es validar el formato antes de escribirlos en un <script>:
ver la validación en schemas/empresa.py.

Revision ID: f7c2a91d64b8
Revises: e4b1c93f27a6
Create Date: 2026-08-03

"""

from alembic import op
import sqlalchemy as sa

revision: str = "f7c2a91d64b8"
down_revision: str | None = "e4b1c93f27a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "empresa", sa.Column("meta_pixel_id", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "empresa", sa.Column("google_tag_id", sa.String(length=40), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("empresa", "google_tag_id")
    op.drop_column("empresa", "meta_pixel_id")
