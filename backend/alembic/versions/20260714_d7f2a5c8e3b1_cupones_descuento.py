"""Cupones de descuento para la reserva online.

Revision ID: d7f2a5c8e3b1
Revises: c5e9a3b7d1f4
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d7f2a5c8e3b1"
down_revision = "c5e9a3b7d1f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cupon_descuento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False, server_default="porcentaje"),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("vence_el", sa.Date(), nullable=True),
        sa.Column("max_usos", sa.Integer(), nullable=True),
        sa.Column("usos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("servicios_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_cupon_empresa_codigo"),
    )
    op.create_index(
        "ix_cupon_empresa_codigo", "cupon_descuento", ["empresa_id", "codigo"]
    )


def downgrade() -> None:
    op.drop_index("ix_cupon_empresa_codigo", table_name="cupon_descuento")
    op.drop_table("cupon_descuento")
