"""Ajustes de Turnos360 que se cambian sin un deploy.

Tabla clave/valor. Hoy la usa una sola cosa: la URL del logo de la marca, para
poder ponerle un gorrito en Navidad sin tocar el repo.

Ver el docstring de `models/saas.py::AjusteGlobal` para qué entra acá y —sobre
todo— qué NO: los precios de los planes no, y el motivo está explicado ahí.

Revision ID: 0005_ajuste_global
Revises: 0004_debito
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_ajuste_global"
down_revision = "0004_debito"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ajuste_global",
        sa.Column("clave", sa.String(length=60), nullable=False),
        sa.Column("valor", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.String(length=160), nullable=True),
        sa.PrimaryKeyConstraint("clave"),
    )


def downgrade() -> None:
    op.drop_table("ajuste_global")
