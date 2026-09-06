"""Cuántas veces se abre la página pública de cada negocio, por día.

Se preguntó mirando el panel de admin: «¿se puede medir tráfico de su
landing?». No se medía. Y es de los datos que hay que empezar a juntar ANTES de
necesitarlos: un contador recién dice algo cuando acumuló semanas, así que cada
día sin contar es un día que después no se recupera.

Guarda un número por empresa y por día. NADA del visitante: ni IP, ni cookie,
ni user-agent, ni referrer. No hace falta para responder la única pregunta que
importa —«¿a esta vidriera la mira alguien?»— y todo lo que se guarde de más es
algo que después hay que cuidar, explicar y borrar.

Revision ID: 0002_visitas
Revises: 0001_base
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_visitas"
down_revision = "0001_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visita_vidriera",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("visitas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name="fk_visita_vidriera_empresa_id_empresa"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_visita_vidriera"),
        # El contador se incrementa con un UPSERT sobre este único. Sin él, dos
        # visitas simultáneas crean dos filas del mismo día y el total queda
        # partido en dos sin que nadie se entere.
        sa.UniqueConstraint("empresa_id", "dia", name="uq_visita_empresa_dia"),
    )
    op.create_index("ix_visita_vidriera_empresa_id", "visita_vidriera", ["empresa_id"])
    op.create_index("ix_visita_vidriera_dia", "visita_vidriera", ["dia"])


def downgrade() -> None:
    op.drop_index("ix_visita_vidriera_dia", table_name="visita_vidriera")
    op.drop_index("ix_visita_vidriera_empresa_id", table_name="visita_vidriera")
    op.drop_table("visita_vidriera")
