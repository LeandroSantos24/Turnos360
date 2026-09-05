"""En qué quedó cada aviso de transferencia, y por qué.

Antes el aviso tenía un `resuelto` booleano y el resto se DEDUCÍA: resuelto con
pago_id = confirmada, resuelto sin pago_id = descartada. Deducir el estado de
la ausencia de otro dato es frágil —cualquier camino que resuelva sin registrar
la cuota queda indistinguible de un rechazo— y sobre todo no dejaba lugar para
el POR QUÉ: un aviso descartado desaparecía de la bandeja sin explicación, así
que si el negocio reclamaba a la semana siguiente no había nada que mirar.

`resuelto` se ELIMINA en vez de quedar al lado de `estado`. Dos columnas que
dicen lo mismo se desincronizan el día que un camino toca una y no la otra, y
entonces la bandeja muestra un aviso que ya se cobró (o esconde uno que no).
El booleano sigue disponible como propiedad derivada en el modelo.

Revision ID: 0005_estado_aviso
Revises: 0004_plan
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_estado_aviso"
down_revision = "0004_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "aviso_pago",
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
    )
    op.add_column("aviso_pago", sa.Column("motivo", sa.String(length=200), nullable=True))

    # El backfill respeta la semántica vieja al pie de la letra: lo resuelto
    # CON cuota registrada se confirmó; lo resuelto SIN cuota se descartó.
    op.execute(
        """
        UPDATE aviso_pago
           SET estado = CASE
                 WHEN resuelto IS NOT TRUE THEN 'pendiente'
                 WHEN pago_id IS NOT NULL  THEN 'confirmada'
                 ELSE 'rechazada'
               END
        """
    )

    # El índice parcial apuntaba a `resuelto`: hay que rehacerlo ANTES de
    # borrar la columna, o el DROP falla porque el índice depende de ella.
    op.drop_index("ix_aviso_pago_pendiente", table_name="aviso_pago")
    op.create_index(
        "ix_aviso_pago_pendiente",
        "aviso_pago",
        ["creado_en"],
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.drop_column("aviso_pago", "resuelto")


def downgrade() -> None:
    op.add_column(
        "aviso_pago",
        sa.Column(
            "resuelto",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute("UPDATE aviso_pago SET resuelto = (estado <> 'pendiente')")
    op.drop_index("ix_aviso_pago_pendiente", table_name="aviso_pago")
    op.create_index(
        "ix_aviso_pago_pendiente",
        "aviso_pago",
        ["creado_en"],
        postgresql_where=sa.text("resuelto = false"),
    )
    op.drop_column("aviso_pago", "motivo")
    op.drop_column("aviso_pago", "estado")
