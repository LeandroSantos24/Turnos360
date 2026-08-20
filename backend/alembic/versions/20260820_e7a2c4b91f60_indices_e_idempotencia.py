"""Índices que faltaban e idempotencia de la seña.

Sale de la auditoría técnica de agosto 2026 (capítulos 4 y 5).

Qué agrega:

1. Los cuatro índices reales de `pago`. La tabla solo tenía
   (empresa_id) y (empresa_id, origen), y ninguno cubría los accesos que
   el código hace de verdad: por fecha (estadísticas), por turno (agenda y
   webhook), por cliente (ficha) y por movimiento (caja).

   Dos de esos accesos NO filtran por empresa_id, así que un índice que
   empiece por empresa_id no los ayuda: van con la columna a la izquierda.

2. `item_turno` por turno_id, por el mismo motivo.

3. `mensaje` por (empresa_id, turno_id): el pedido de reseña hacía un LIKE
   sobre el contenido y escaneaba la tabla que más rápido crece del sistema
   (~5 filas por turno).

4. Dos índices PARCIALES en `turno` para la tarea de recordatorios, que
   corre cada 15 minutos filtrando por fecha + flag sin empresa_id, y hoy
   escanea la tabla completa dos veces cada cuarto de hora.

5. Un índice ÚNICO PARCIAL sobre `pago(turno_id) WHERE origen = 'sena'`.
   Este no es de rendimiento: es de integridad. El corte de idempotencia
   del webhook es un SELECT seguido de un INSERT, y Mercado Pago reintenta
   las notificaciones EN PARALELO. Dos avisos con 50 ms de diferencia
   pasaban los dos el SELECT y registraban la seña dos veces.

Todo es aditivo: no borra ni altera nada.

Revision ID: e7a2c4b91f60
Revises: d5a71e02c9b4
"""

import sqlalchemy as sa
from alembic import op

revision = "e7a2c4b91f60"
down_revision = "d5a71e02c9b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Antes de nada: el índice único de la seña falla si ya hay duplicados.
    # Mejor detectarlo acá, con un mensaje que se entienda, que dejar que
    # reviente a mitad del deploy con un error de Postgres.
    duplicados = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT turno_id, count(*) AS n
                FROM pago
                WHERE origen = 'sena' AND turno_id IS NOT NULL
                GROUP BY turno_id
                HAVING count(*) > 1
                """
            )
        )
        .fetchall()
    )
    if duplicados:
        detalle = ", ".join(f"turno {t} ({n} señas)" for t, n in duplicados[:10])
        raise RuntimeError(
            "No puedo crear el índice único de señas: ya hay señas duplicadas "
            f"en la base ({len(duplicados)} turno/s afectado/s: {detalle}). "
            "Eso significa que el bug de la doble seña YA ocurrió. Revisá esos "
            "turnos, decidí con cuál pago te quedás, anulá el movimiento del "
            "otro y borrá su fila de `pago`. Después volvé a correr la migración."
        )

    # ── Rendimiento ────────────────────────────────────────────────────────
    op.create_index("ix_pago_empresa_fecha", "pago", ["empresa_id", "fecha"])
    op.create_index("ix_pago_turno", "pago", ["turno_id"])
    op.create_index("ix_pago_empresa_cliente", "pago", ["empresa_id", "cliente_id"])
    op.create_index("ix_pago_movimiento", "pago", ["movimiento_id"])
    op.create_index("ix_item_turno_turno", "item_turno", ["turno_id"])
    op.create_index("ix_mensaje_empresa_turno", "mensaje", ["empresa_id", "turno_id"])

    op.create_index(
        "ix_turno_recordatorio_pendiente",
        "turno",
        ["fecha_inicio"],
        postgresql_where=sa.text("recordatorio_enviado = false"),
    )
    op.create_index(
        "ix_turno_recordatorio_2h_pendiente",
        "turno",
        ["fecha_inicio"],
        postgresql_where=sa.text("recordatorio_2h_enviado = false"),
    )

    # ── Integridad ─────────────────────────────────────────────────────────
    op.create_index(
        "uq_pago_sena_turno",
        "pago",
        ["turno_id"],
        unique=True,
        postgresql_where=sa.text("origen = 'sena'"),
    )


def downgrade() -> None:
    op.drop_index("uq_pago_sena_turno", table_name="pago")
    op.drop_index("ix_turno_recordatorio_2h_pendiente", table_name="turno")
    op.drop_index("ix_turno_recordatorio_pendiente", table_name="turno")
    op.drop_index("ix_mensaje_empresa_turno", table_name="mensaje")
    op.drop_index("ix_item_turno_turno", table_name="item_turno")
    op.drop_index("ix_pago_movimiento", table_name="pago")
    op.drop_index("ix_pago_empresa_cliente", table_name="pago")
    op.drop_index("ix_pago_turno", table_name="pago")
    op.drop_index("ix_pago_empresa_fecha", table_name="pago")
