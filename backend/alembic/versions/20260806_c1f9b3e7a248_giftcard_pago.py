"""La venta de una gift card entra a la caja.

Hasta ahora `giftcard.crear()` guardaba la tarjeta y nada más: la plata que el
cliente pagaba por ella no generaba ningún movimiento. El arqueo del día
cerraba con esa diferencia sin explicación, y como al canjearla el turno queda
cubierto, esa venta no aparecía NUNCA en la facturación.

Revision ID: c1f9b3e7a248
Revises: b8e4c07a5f13
Create Date: 2026-08-06

"""

from alembic import op
import sqlalchemy as sa

revision: str = "c1f9b3e7a248"
down_revision: str | None = "b8e4c07a5f13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gift_card", sa.Column("metodo_pago_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "gift_card", sa.Column("movimiento_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_giftcard_metodo_pago", "gift_card", "metodo_pago",
        ["metodo_pago_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_giftcard_movimiento", "gift_card", "movimiento_financiero",
        ["movimiento_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_giftcard_movimiento", "gift_card", type_="foreignkey")
    op.drop_constraint("fk_giftcard_metodo_pago", "gift_card", type_="foreignkey")
    op.drop_column("gift_card", "movimiento_id")
    op.drop_column("gift_card", "metodo_pago_id")
