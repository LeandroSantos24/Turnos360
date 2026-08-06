"""Período de prueba de 14 días.

Hasta ahora el semáforo de cobranza solo distinguía "al día", "por vencer",
"vencido" y "sin fecha". Con la venta a 14 días de prueba hacía falta un
estado propio: un negocio en prueba NO es un moroso ni un cliente al día, y
mezclarlo con cualquiera de los dos rompe el MRR y la deuda vencida.

`prueba_hasta` es la fecha en que termina la prueba. NULL = cliente normal
(todas las empresas que ya existen).

Revision ID: b8e4c07a5f13
Revises: a3d5f81c92e7
Create Date: 2026-08-03

"""

from alembic import op
import sqlalchemy as sa

revision: str = "b8e4c07a5f13"
down_revision: str | None = "a3d5f81c92e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("empresa", sa.Column("prueba_hasta", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("empresa", "prueba_hasta")
