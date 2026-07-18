"""Automatizaciones (campañas) por empresa + flags de dedup de envíos.

- empresa.automatizaciones (JSONB): config de cada campaña (switch + campos).
  Vive aparte de config_pack (que es del preset del rubro, no del dueño).
- turno.recordatorio_2h_enviado: dedup del segundo recordatorio.
- cliente.ultimo_cumple_enviado: dedup del saludo de cumpleaños (una vez por año).

Revision ID: a9c4e7f2b1d8
Revises: f1a2b3c4d5e6
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a9c4e7f2b1d8"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("empresa", sa.Column("automatizaciones", JSONB(), nullable=True))
    op.add_column(
        "turno",
        sa.Column(
            "recordatorio_2h_enviado",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column("cliente", sa.Column("ultimo_cumple_enviado", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("cliente", "ultimo_cumple_enviado")
    op.drop_column("turno", "recordatorio_2h_enviado")
    op.drop_column("empresa", "automatizaciones")
