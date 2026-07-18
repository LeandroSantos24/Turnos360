"""Suscripción por empresa: plan + fecha de vencimiento.

Revision ID: e1a4c9d2f6b8
Revises: d7f2a5c8e3b1
"""

import sqlalchemy as sa
from alembic import op

revision = "e1a4c9d2f6b8"
down_revision = "d7f2a5c8e3b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column("plan", sa.String(20), nullable=False, server_default="gratuito"),
    )
    op.add_column("empresa", sa.Column("suscripcion_vence", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("empresa", "suscripcion_vence")
    op.drop_column("empresa", "plan")
