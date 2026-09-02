"""Caja por sucursal: cada local cuenta su plata y firma su arqueo.

Paso 5 de multisucursal (E16). El más delicado de los ocho: toca dinero y
arqueos ya cerrados.

Hasta acá había UNA caja abierta por empresa. Con varios locales tiene que
haber una por local: la plata del centro y la del barrio no se cuentan juntas,
y cada encargado firma lo suyo.

Qué hace esta migración:

1. `movimiento_financiero.sucursal_id` y `pago.sucursal_id`, con backfill.

   Se guardan en las dos tablas y no se deducen de la caja a propósito.
   `caja_id` es NULLABLE —un cobro con la caja cerrada igual se registra— así
   que esa plata quedaría sin local. Y estadísticas lee de `pago`, no de los
   movimientos: sin la columna no habría con qué comparar dos locales.

   El backfill toma el local de la caja cuando el movimiento tiene una, y si
   no, el local principal de la empresa. Para los datos de hoy son lo mismo
   (una empresa, un local), así que ninguna plata cambia de lugar.

2. Índice único parcial: UNA caja abierta por local, garantizado por la base.

   Antes ni siquiera estaba garantizado "una por empresa": era un SELECT
   seguido de un INSERT, y dos pestañas abriendo caja al mismo tiempo pasaban
   las dos. El negocio terminaba con dos cajas abiertas y el día repartido
   entre ambas, sin ninguna señal.

Revision ID: d7e2a3b48c15
Revises: c4a81f2e6b93
"""

from alembic import op
import sqlalchemy as sa

revision = "d7e2a3b48c15"
down_revision = "c4a81f2e6b93"
branch_labels = None
depends_on = None

TABLAS = ["movimiento_financiero", "pago"]


def upgrade() -> None:
    conn = op.get_bind()

    for tabla in TABLAS:
        op.add_column(tabla, sa.Column("sucursal_id", sa.Integer(), nullable=True))

    # El movimiento hereda el local de SU caja…
    conn.execute(
        sa.text(
            """
            UPDATE movimiento_financiero t
               SET sucursal_id = c.sucursal_id
              FROM caja c
             WHERE c.id = t.caja_id
               AND t.sucursal_id IS NULL
            """
        )
    )

    # …y el pago, el de su movimiento. `pago` no tiene caja_id: se asocia a la
    # caja a través del movimiento que lo acompaña.
    conn.execute(
        sa.text(
            """
            UPDATE pago p
               SET sucursal_id = m.sucursal_id
              FROM movimiento_financiero m
             WHERE m.id = p.movimiento_id
               AND p.sucursal_id IS NULL
            """
        )
    )

    # Un pago sin movimiento (una seña de Mercado Pago, por ejemplo) toma el
    # local de su turno, que es donde realmente se atendió.
    conn.execute(
        sa.text(
            """
            UPDATE pago p
               SET sucursal_id = t.sucursal_id
              FROM turno t
             WHERE t.id = p.turno_id
               AND p.sucursal_id IS NULL
            """
        )
    )

    # Lo que quede (registrado sin caja abierta y sin turno) va al principal.
    for tabla in TABLAS:
        conn.execute(
            sa.text(
                f"""
                UPDATE {tabla} t
                   SET sucursal_id = (
                       SELECT s.id FROM sucursal s
                        WHERE s.empresa_id = t.empresa_id
                        ORDER BY s.id
                        LIMIT 1
                   )
                 WHERE t.sucursal_id IS NULL
                """
            )
        )

        faltan = conn.execute(
            sa.text(f"SELECT count(*) FROM {tabla} WHERE sucursal_id IS NULL")
        ).scalar_one()
        if faltan:
            raise RuntimeError(
                f"Quedaron {faltan} filas de '{tabla}' sin local. Casi seguro "
                f"son filas cuyo empresa_id no existe en la tabla empresa."
            )

        op.alter_column(tabla, "sucursal_id", nullable=False)
        op.create_foreign_key(
            f"fk_{'movfin' if tabla == 'movimiento_financiero' else tabla}_sucursal",
            tabla,
            "sucursal",
            ["empresa_id", "sucursal_id"],
            ["empresa_id", "id"],
        )

    # Antes de poner el índice único hay que resolver el caso de una empresa
    # que ya tenga dos cajas abiertas (posible por la carrera que este índice
    # justamente viene a cerrar). Se deja la más vieja abierta y las demás se
    # cierran, para no perder ningún movimiento: los que estaban asociados
    # siguen asociados.
    conn.execute(
        sa.text(
            """
            UPDATE caja SET estado = 'cerrada', fecha_cierre = now()
             WHERE estado = 'abierta'
               AND id NOT IN (
                   SELECT MIN(id) FROM caja
                    WHERE estado = 'abierta'
                    GROUP BY empresa_id, sucursal_id
               )
            """
        )
    )

    op.create_index(
        "uq_caja_abierta_por_sucursal",
        "caja",
        ["empresa_id", "sucursal_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'abierta'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_caja_abierta_por_sucursal",
        table_name="caja",
        postgresql_where=sa.text("estado = 'abierta'"),
    )
    for tabla in TABLAS:
        op.drop_constraint(
            f"fk_{'movfin' if tabla == 'movimiento_financiero' else tabla}_sucursal",
            tabla,
            type_="foreignkey",
        )
        op.drop_column(tabla, "sucursal_id")
