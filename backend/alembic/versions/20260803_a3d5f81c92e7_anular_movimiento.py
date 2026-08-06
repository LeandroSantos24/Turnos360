"""Anulación auditada de movimientos de caja.

Hasta ahora un movimiento mal cargado solo se podía borrar, y con eso se
perdía el rastro de que existió: el arqueo del día dejaba de poder auditarse
("cerré con $20.000 de diferencia y no sé de dónde salía"). Ahora el
movimiento queda, marcado como anulado, con quién lo anuló, cuándo y por qué,
y deja de sumar a cualquier total.

Revision ID: a3d5f81c92e7
Revises: f7c2a91d64b8
Create Date: 2026-08-03

"""

from alembic import op
import sqlalchemy as sa

revision: str = "a3d5f81c92e7"
down_revision: str | None = "f7c2a91d64b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movimiento_financiero",
        sa.Column("anulado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "movimiento_financiero",
        sa.Column("anulado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "movimiento_financiero",
        sa.Column("anulado_por_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "movimiento_financiero",
        sa.Column("motivo_anulacion", sa.String(length=200), nullable=True),
    )
    op.create_foreign_key(
        "fk_movfin_anulado_por",
        "movimiento_financiero",
        "usuario",
        ["anulado_por_id"],
        ["id"],
    )
    # Los totales de caja filtran SIEMPRE por anulado = false. Sin este índice,
    # cada arqueo hace un scan de toda la tabla de movimientos del negocio.
    op.create_index(
        "ix_movfin_caja_activos",
        "movimiento_financiero",
        ["empresa_id", "caja_id", "anulado"],
    )


def downgrade() -> None:
    op.drop_index("ix_movfin_caja_activos", table_name="movimiento_financiero")
    op.drop_constraint(
        "fk_movfin_anulado_por", "movimiento_financiero", type_="foreignkey"
    )
    op.drop_column("movimiento_financiero", "motivo_anulacion")
    op.drop_column("movimiento_financiero", "anulado_por_id")
    op.drop_column("movimiento_financiero", "anulado_en")
    op.drop_column("movimiento_financiero", "anulado")
