"""Revocación de sesiones: token_version en usuario.

Cambiar o restablecer la contraseña incrementa esta columna. El número viaja
dentro del JWT (claim 'tv') y se compara en cada request, así que todos los
tokens emitidos antes del cambio dejan de valer al instante — incluido el
refresh de 7 días que pudiera tener un atacante en otro dispositivo.

Revision ID: a1c8e5f3b724
Revises: f4b7c1e9a3d2
Create Date: 2026-07-21

"""

from alembic import op
import sqlalchemy as sa

revision: str = "a1c8e5f3b724"
down_revision: str | None = "f4b7c1e9a3d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "token_version")
