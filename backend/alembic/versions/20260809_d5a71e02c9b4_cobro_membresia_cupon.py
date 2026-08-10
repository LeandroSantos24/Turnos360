"""Cobro de membresías, trazabilidad de cupones y pagos sin turno.

Tres agujeros de negocio que se arreglan juntos porque tocan la misma cadena
(plata que entra -> caja -> estadísticas):

1. VENDER UN ABONO NO COBRABA NADA. `crear_membresia` guardaba la membresía y
   listo. El cliente pagaba $50.000, el negocio los tenía en el bolsillo y el
   sistema no se enteraba: no entraban a la caja, no aparecían en el arqueo ni
   en la facturación. Peor: después esos cortes salen en $0 (cubierto_por_abono),
   así que el abono era ingreso invisible y costo visible. La rentabilidad del
   plan daba negativa contra la realidad.

2. NO SE PODÍA SABER QUÉ CUPÓN USÓ CADA TURNO. El cupón se aplicaba escribiendo
   `turno.descuento_pct` y sumando 1 a un contador global. Con eso no hay forma
   de responder "¿cuántas personas usaron INAUGURACION20 y cuánto facturaron?",
   que es justo lo que decide si la promoción sirvió.

3. `pago.cliente_id` ERA OBLIGATORIO. Eso impedía registrar como pago la venta
   de una gift card (que tiene beneficiario de texto, no ficha de cliente), y
   por eso las gift cards entraban a la caja pero NO a Estadísticas: los dos
   números del mismo día no coincidían y no había explicación a la vista.

Revision ID: d5a71e02c9b4
Revises: c1f9b3e7a248
Create Date: 2026-08-09

"""

from alembic import op
import sqlalchemy as sa

revision: str = "d5a71e02c9b4"
down_revision: str | None = "c1f9b3e7a248"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Cobro de la membresía ──────────────────────────────────────────
    op.add_column("membresia", sa.Column("metodo_pago_id", sa.Integer(), nullable=True))
    op.add_column("membresia", sa.Column("movimiento_id", sa.Integer(), nullable=True))
    op.add_column(
        "membresia", sa.Column("monto_cobrado", sa.Numeric(12, 2), nullable=True)
    )
    op.create_foreign_key(
        "fk_membresia_metodo_pago", "membresia", "metodo_pago",
        ["metodo_pago_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_membresia_movimiento", "membresia", "movimiento_financiero",
        ["movimiento_id"], ["id"],
    )

    # ── 2. Qué cupón usó cada turno ───────────────────────────────────────
    op.add_column("turno", sa.Column("cupon_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_turno_cupon", "turno", "cupon_descuento", ["cupon_id"], ["id"],
    )
    # Índice para el informe por cupón: "todos los turnos de este código".
    op.create_index(
        "ix_turno_empresa_cupon", "turno", ["empresa_id", "cupon_id"]
    )

    # ── 3. Un pago puede no tener cliente (venta de gift card al mostrador) ──
    op.alter_column("pago", "cliente_id", existing_type=sa.Integer(), nullable=True)

    # Concepto del pago, para distinguir en Estadísticas de dónde salió la
    # plata: turno, abono o gift card. Sin esto, sumar los abonos a la
    # facturación mezclaría peras con manzanas y el ticket promedio mentiría.
    op.add_column("pago", sa.Column("origen", sa.String(20), nullable=True))
    op.execute("UPDATE pago SET origen = 'turno' WHERE origen IS NULL")
    op.create_index("ix_pago_empresa_origen", "pago", ["empresa_id", "origen"])


def downgrade() -> None:
    op.drop_index("ix_pago_empresa_origen", table_name="pago")
    op.drop_column("pago", "origen")
    # OJO: volver cliente_id a NOT NULL falla si quedaron pagos de gift card
    # sin cliente. Se borran primero, que es lo único coherente al revertir.
    op.execute("DELETE FROM pago WHERE cliente_id IS NULL")
    op.alter_column("pago", "cliente_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_turno_empresa_cupon", table_name="turno")
    op.drop_constraint("fk_turno_cupon", "turno", type_="foreignkey")
    op.drop_column("turno", "cupon_id")

    op.drop_constraint("fk_membresia_movimiento", "membresia", type_="foreignkey")
    op.drop_constraint("fk_membresia_metodo_pago", "membresia", type_="foreignkey")
    op.drop_column("membresia", "monto_cobrado")
    op.drop_column("membresia", "movimiento_id")
    op.drop_column("membresia", "metodo_pago_id")
