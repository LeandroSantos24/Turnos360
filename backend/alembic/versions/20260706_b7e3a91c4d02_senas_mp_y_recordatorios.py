"""Señas con Mercado Pago (opcional por empresa) + recordatorios por email.

- empresa: credenciales MP encriptadas (Fernet, Regla 7), switch de señas y monto.
- turno: estado y monto de la seña, id del pago de MP, y marca de recordatorio
  enviado (dedup del beat de Celery).

Revision ID: b7e3a91c4d02
Revises: c2e94a7f51b8
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA

revision = "b7e3a91c4d02"
down_revision = "c2e94a7f51b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Empresa: configuración de señas ---
    op.add_column("empresa", sa.Column("mp_credenciales", BYTEA(), nullable=True))
    op.add_column(
        "empresa",
        sa.Column("sena_activa", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("empresa", sa.Column("sena_monto", sa.Numeric(12, 2), nullable=True))

    # --- Turno: seguimiento de la seña + recordatorio ---
    op.add_column("turno", sa.Column("sena_estado", sa.String(20), nullable=True))
    op.add_column("turno", sa.Column("sena_monto", sa.Numeric(12, 2), nullable=True))
    op.add_column("turno", sa.Column("mp_payment_id", sa.String(60), nullable=True))
    op.add_column(
        "turno",
        sa.Column(
            "recordatorio_enviado", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("turno", "recordatorio_enviado")
    op.drop_column("turno", "mp_payment_id")
    op.drop_column("turno", "sena_monto")
    op.drop_column("turno", "sena_estado")
    op.drop_column("empresa", "sena_monto")
    op.drop_column("empresa", "sena_activa")
    op.drop_column("empresa", "mp_credenciales")
