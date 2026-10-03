"""Un solo aviso de pago abierto por empresa.

Antes de crear el índice único se cierran los duplicados que pudiera haber
(quedan como «rechazada» con motivo, nunca se borran): se conserva el más
nuevo de cada empresa, que es el que tiene los datos más recientes.

Revision ID: 0008_aviso_unico
Revises: 0007_suscripciones
"""

from alembic import op

revision = "0008_aviso_unico"
down_revision = "0007_suscripciones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE aviso_pago a
           SET estado = 'rechazada',
               motivo = 'Duplicado: quedó abierto el aviso más reciente',
               resuelto_en = now(),
               resuelto_por = 'migración 0008'
         WHERE a.estado IN ('pendiente', 'info_solicitada')
           AND EXISTS (
               SELECT 1 FROM aviso_pago b
                WHERE b.empresa_id = a.empresa_id
                  AND b.estado IN ('pendiente', 'info_solicitada')
                  AND (b.creado_en, b.id) > (a.creado_en, a.id)
           )
        """
    )
    op.create_index(
        "uq_aviso_abierto_por_empresa",
        "aviso_pago",
        ["empresa_id"],
        unique=True,
        postgresql_where="estado IN ('pendiente', 'info_solicitada')",
    )


def downgrade() -> None:
    op.drop_index("uq_aviso_abierto_por_empresa", table_name="aviso_pago")
