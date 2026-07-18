"""Gift cards: tabla gift_card con código único por empresa.

Revision ID: f1a2b3c4d5e6
Revises: b7e3a91c4d02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "b7e3a91c4d02"
branch_labels = None
depends_on = None

# create_type=False: el tipo lo creamos explícitamente abajo (una sola vez),
# así la columna NO intenta volver a crearlo (evita "type already exists").
ESTADO = postgresql.ENUM(
    "activa", "canjeada", "vencida", name="estado_gift_card", create_type=False
)


def upgrade() -> None:
    # Crea el tipo solo si no existe (por si SQLAlchemy ya lo había creado).
    ESTADO.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "gift_card",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("beneficiario", sa.String(120), nullable=True),
        sa.Column("de_parte_de", sa.String(120), nullable=True),
        sa.Column("mensaje", sa.String(300), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("concepto", sa.String(120), nullable=True),
        sa.Column("estado", ESTADO, nullable=False, server_default="activa"),
        sa.Column("vence", sa.Date(), nullable=True),
        sa.Column("canjeada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canjeada_por", sa.String(120), nullable=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_gift_card_empresa_codigo", "gift_card", ["empresa_id", "codigo"], unique=True
    )
    op.create_index(
        "ix_gift_card_empresa_estado", "gift_card", ["empresa_id", "estado"]
    )


def downgrade() -> None:
    op.drop_index("ix_gift_card_empresa_estado", table_name="gift_card")
    op.drop_index("ix_gift_card_empresa_codigo", table_name="gift_card")
    op.drop_table("gift_card")
    ESTADO.drop(op.get_bind(), checkfirst=True)
