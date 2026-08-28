"""Anular una gift card revierte su venta: el pago también se anula.

Revision ID: e9b3c47d1a05
Revises: d3f7a1c9e408

EL PROBLEMA QUE ARREGLA
───────────────────────
Vender una gift card escribe en TRES tablas: `gift_card`, `movimiento_financiero`
(para que entre a la caja) y `pago` (para que entre a Estadísticas, que lee de
`pago` y no de los movimientos). Borrarla escribía en UNA sola: se borraba la
tarjeta y la plata quedaba facturada para siempre. Una gift card de $50.000
creada por error inflaba la facturación del mes sin ninguna forma de sacarla
desde la aplicación.

`movimiento_financiero` ya tenía anulación desde a3d5f81c92e7. `pago` no la
tenía, y por eso ni siquiera anular el movimiento a mano arreglaba el número de
Estadísticas. Estas columnas cierran ese agujero.

Se anula, no se borra: el criterio del proyecto es que la plata que se movió
deja rastro (si no, una diferencia de arqueo es imposible de auditar).
"""

import sqlalchemy as sa
from alembic import op

revision = "e9b3c47d1a05"
down_revision = "d3f7a1c9e408"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pago",
        sa.Column("anulado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("pago", sa.Column("anulado_en", sa.DateTime(timezone=True)))
    op.add_column("pago", sa.Column("anulado_por_id", sa.Integer()))
    op.add_column("pago", sa.Column("motivo_anulacion", sa.String(200)))

    # Estadísticas filtra por este campo en TODAS sus consultas (facturación,
    # por método, por día, por origen, por profesional). Sin índice, cada una
    # de esas suma recorriendo pagos anulados que ya sabe que va a descartar.
    op.create_index(
        "ix_pago_empresa_vigente",
        "pago",
        ["empresa_id", "fecha"],
        postgresql_where=sa.text("anulado = false"),
    )

    # ALTER TYPE ... ADD VALUE necesita salir de la transacción de Alembic: el
    # valor nuevo no se puede usar dentro de la misma transacción que lo crea.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE estado_gift_card ADD VALUE IF NOT EXISTS 'anulada'")


def downgrade() -> None:
    op.drop_index("ix_pago_empresa_vigente", table_name="pago")
    op.drop_column("pago", "motivo_anulacion")
    op.drop_column("pago", "anulado_por_id")
    op.drop_column("pago", "anulado_en")
    op.drop_column("pago", "anulado")
    # El valor 'anulada' del enum NO se saca: PostgreSQL no permite quitar un
    # valor de un enum, y recrearlo obligaría a reescribir la tabla entera.
    # Queda como valor huérfano, que es inofensivo.
