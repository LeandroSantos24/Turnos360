"""Reglas de reserva configurables por negocio.

Hasta ahora la ventana de la reserva pública estaba HARDCODEADA en
services/publico.py (DIAS_MAXIMOS_A_FUTURO = 180, sin anticipación mínima) e
igual para todos los negocios. Una barbería que quiere cerrar la agenda con 2
horas de anticipación, o aceptar reservas solo a 30 días, no tenía cómo.

Los server_default preservan EXACTAMENTE el comportamiento actual: las
empresas que ya existen no cambian de conducta al migrar. El dueño ajusta
desde la pantalla cuando quiere.

Revision ID: e4b1c93f27a6
Revises: c9e2a7b45d18
Create Date: 2026-08-03

"""

from alembic import op
import sqlalchemy as sa

revision: str = "e4b1c93f27a6"
down_revision: str | None = "c9e2a7b45d18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Minutos mínimos entre "ahora" y el turno. 0 = como hasta ahora (se puede
    # reservar para dentro de cinco minutos).
    op.add_column(
        "empresa",
        sa.Column(
            "reserva_anticipacion_min",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    # Cuántos días hacia adelante se puede reservar. 180 = el valor que estaba
    # hardcodeado.
    op.add_column(
        "empresa",
        sa.Column(
            "reserva_dias_max", sa.Integer(), nullable=False, server_default="180"
        ),
    )
    # Fecha fija de cierre de agenda (ej. "cierro por vacaciones el 20/12").
    # Manda la MÁS RESTRICTIVA entre esta y reserva_dias_max.
    op.add_column(
        "empresa", sa.Column("reserva_fecha_limite", sa.Date(), nullable=True)
    )
    op.add_column(
        "empresa",
        sa.Column(
            "reserva_permite_cancelar",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "empresa",
        sa.Column(
            "reserva_pide_telefono",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    # El cumpleaños alimenta la campaña de saludo que ya existe (E8).
    op.add_column(
        "empresa",
        sa.Column(
            "reserva_pide_nacimiento",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("empresa", "reserva_pide_nacimiento")
    op.drop_column("empresa", "reserva_pide_telefono")
    op.drop_column("empresa", "reserva_permite_cancelar")
    op.drop_column("empresa", "reserva_fecha_limite")
    op.drop_column("empresa", "reserva_dias_max")
    op.drop_column("empresa", "reserva_anticipacion_min")
