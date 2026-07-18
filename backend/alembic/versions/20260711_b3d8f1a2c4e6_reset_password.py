"""Recuperación de contraseña: token de un solo uso en Usuario.

Se guarda el HASH del token (nunca el token plano: si alguien lee la base,
los tokens no le sirven) y su expiración. Al usarse o pisarse, se limpia.

Revision ID: b3d8f1a2c4e6
Revises: a9c4e7f2b1d8
"""

import sqlalchemy as sa
from alembic import op

revision = "b3d8f1a2c4e6"
down_revision = "a9c4e7f2b1d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("reset_token_hash", sa.String(128), nullable=True))
    op.add_column(
        "usuario",
        sa.Column("reset_token_expira", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usuario", "reset_token_expira")
    op.drop_column("usuario", "reset_token_hash")
