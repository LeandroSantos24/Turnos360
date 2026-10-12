"""Link de autogestión del turno (el cliente cambia o cancela desde el email).

Dos columnas en turno, sin tocar datos existentes:

- gestion_version: se suma 1 para revocar el link (deja de servir el viejo).
- gestion_token_hash: SHA-256 del token, para encontrarlo sin guardar el token
  en claro. Índice único parcial: solo las filas que ya tienen link.

Revision ID: 0009_autogestion_turno
Revises: 0008_aviso_unico
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_autogestion_turno"
down_revision = "0008_aviso_unico"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "turno",
        sa.Column("gestion_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("turno", sa.Column("gestion_token_hash", sa.String(64), nullable=True))
    op.create_index(
        "uq_turno_gestion_token",
        "turno",
        ["gestion_token_hash"],
        unique=True,
        postgresql_where=sa.text("gestion_token_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_turno_gestion_token", table_name="turno")
    op.drop_column("turno", "gestion_token_hash")
    op.drop_column("turno", "gestion_version")
