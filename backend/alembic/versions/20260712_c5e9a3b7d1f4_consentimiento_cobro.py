"""Consentimiento de marketing, dedup de inactivos y modo de cobro anticipado.

- cliente.acepta_marketing: tilde legal (Ley 25.326). Las campañas promocionales
  (cumpleaños, inactivos) SOLO salen si está en True. Los emails transaccionales
  (confirmación, recordatorio, cancelación) no lo necesitan: son del servicio
  que el cliente pidió.
- cliente.ultimo_inactivo_enviado: para no repetirle el "te extrañamos".
- empresa.cobro_modo: 'ninguno' | 'sena' | 'total'. Reemplaza al sena_activa
  booleano (que solo permitía seña sí/no).

Revision ID: c5e9a3b7d1f4
Revises: b3d8f1a2c4e6
"""

import sqlalchemy as sa
from alembic import op

revision = "c5e9a3b7d1f4"
down_revision = "b3d8f1a2c4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cliente",
        sa.Column(
            "acepta_marketing",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column("cliente", sa.Column("ultimo_inactivo_enviado", sa.Date(), nullable=True))
    op.add_column(
        "empresa",
        sa.Column(
            "cobro_modo",
            sa.String(10),
            nullable=False,
            server_default="ninguno",
        ),
    )
    # Los que ya tenían la seña prendida quedan en modo 'sena'.
    op.execute("UPDATE empresa SET cobro_modo = 'sena' WHERE sena_activa = true")


def downgrade() -> None:
    op.drop_column("empresa", "cobro_modo")
    op.drop_column("cliente", "ultimo_inactivo_enviado")
    op.drop_column("cliente", "acepta_marketing")
