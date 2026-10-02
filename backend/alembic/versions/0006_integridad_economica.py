"""Integridad económica (auditoría 2026-10-02). Solo agrega: no borra nada.

- turno.descuento_monto: descuento fijo en pesos. Antes un cupón de $5.000
  sobre $15.000 se guardaba como 33,33 % y el turno quedaba en $10.000,50.
- gift_card.saldo: permite usarla en partes. Se completa con el monto para
  las activas/vencidas y con 0 para las canjeadas/anuladas.
- pago.gift_card_id: el uso de una gift card en un cobro queda atado a la
  tarjeta (origen 'giftcard_uso', sin movimiento de caja: la plata entró al
  venderla).

Revision ID: 0006_integridad_economica
Revises: 0005_ajuste_global
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_integridad_economica"
down_revision = "0005_ajuste_global"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "turno",
        sa.Column("descuento_monto", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column("gift_card", sa.Column("saldo", sa.Numeric(12, 2), nullable=True))
    op.execute(
        "UPDATE gift_card SET saldo = CASE WHEN estado IN ('activa', 'vencida') "
        "THEN monto ELSE 0 END"
    )
    op.add_column("pago", sa.Column("gift_card_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_pago_gift_card", "pago", "gift_card", ["gift_card_id"], ["id"])
    op.create_index("ix_pago_gift_card", "pago", ["gift_card_id"])


def downgrade() -> None:
    op.drop_index("ix_pago_gift_card", table_name="pago")
    op.drop_constraint("fk_pago_gift_card", "pago", type_="foreignkey")
    op.drop_column("pago", "gift_card_id")
    op.drop_column("gift_card", "saldo")
    op.drop_column("turno", "descuento_monto")
