"""Servicios por sucursal, con precio propio por local.

Paso 3b de multisucursal (E16).

El mismo "Corte" puede ofrecerse en dos locales y no en el tercero, y costar
distinto en cada uno. Es la primera pregunta que hace cualquier dueño de dos
locales, y hasta ahora el precio era uno solo por servicio.

`precio` en NULL significa "el del servicio". No se copia el precio base a cada
fila a propósito: si se copiara, subir el precio general obligaría a tocar cada
local uno por uno, y el que se olvidara quedaría vendiendo al precio viejo.

Backfill: cada servicio queda ofrecido en TODOS los locales que su empresa
tenga hoy. Es lo que preserva el comportamiento actual —el servicio se ofrece
en todos lados— y el dueño lo achica después si quiere.

Revision ID: c4a81f2e6b93
Revises: b1d4e7a92f3c
"""

from alembic import op
import sqlalchemy as sa

revision = "c4a81f2e6b93"
down_revision = "b1d4e7a92f3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Destino de la FK compuesta: Postgres exige unique en ese orden exacto.
    op.create_unique_constraint(
        "uq_servicio_empresa", "servicio", ["empresa_id", "id"]
    )

    op.create_table(
        "servicio_sucursal",
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("servicio_id", sa.Integer(), nullable=False),
        sa.Column("sucursal_id", sa.Integer(), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        # Las dos FKs llevan empresa_id adentro: la base rechaza cruzar el
        # servicio de una empresa con el local de otra, sin depender de que
        # ningún servicio se acuerde de validarlo.
        sa.ForeignKeyConstraint(
            ["empresa_id", "servicio_id"],
            ["servicio.empresa_id", "servicio.id"],
            name="fk_servicio_sucursal_servicio",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id", "sucursal_id"],
            ["sucursal.empresa_id", "sucursal.id"],
            name="fk_servicio_sucursal_sucursal",
        ),
        sa.PrimaryKeyConstraint("servicio_id", "sucursal_id"),
    )
    op.create_index(
        "ix_servicio_sucursal_empresa_id", "servicio_sucursal", ["empresa_id"]
    )

    # Backfill: producto cartesiano servicio × sucursal, dentro de cada empresa.
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO servicio_sucursal (empresa_id, servicio_id, sucursal_id)
            SELECT sv.empresa_id, sv.id, su.id
              FROM servicio sv
              JOIN sucursal su ON su.empresa_id = sv.empresa_id
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_servicio_sucursal_empresa_id", table_name="servicio_sucursal")
    op.drop_table("servicio_sucursal")
    op.drop_constraint("uq_servicio_empresa", "servicio", type_="unique")
