"""Alinea la base con los modelos (drift detectado en la auditoría).

Tres diferencias entre lo que declaran los modelos y lo que quedó en la base
porque algunas migraciones se escribieron a mano:

1. cupon_descuento: había un índice ix_cupon_empresa_codigo que duplica lo que
   ya garantiza la constraint única uq_cupon_empresa_codigo. Se reemplaza por
   el índice simple sobre empresa_id que declara el TenantMixin.
2. gift_card.creada_en: el modelo la declara NOT NULL y la base la dejó
   nullable. Tiene server_default now(), así que en la práctica nunca hubo un
   NULL, pero el ORM asumía una garantía que la base no daba.
3. gift_card.empresa_id: le faltaba el índice simple del TenantMixin.

Nada de esto cambia el comportamiento. Sirve para que `alembic revision
--autogenerate` vuelva a salir vacío y un cambio real no quede escondido
entre ruido.

Revision ID: b6d3f8a2c517
Revises: a1c8e5f3b724
Create Date: 2026-07-21

"""

from alembic import op
import sqlalchemy as sa

revision: str = "b6d3f8a2c517"
down_revision: str | None = "a1c8e5f3b724"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Índice redundante de cupones -> índice de tenant
    op.drop_index("ix_cupon_empresa_codigo", table_name="cupon_descuento")
    op.create_index(
        "ix_cupon_descuento_empresa_id", "cupon_descuento", ["empresa_id"]
    )

    # 2. gift_card.creada_en: rellenar por las dudas y ponerla NOT NULL
    op.execute("UPDATE gift_card SET creada_en = now() WHERE creada_en IS NULL")
    op.alter_column(
        "gift_card",
        "creada_en",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # 3. Índice de tenant que faltaba en gift_card
    op.create_index("ix_gift_card_empresa_id", "gift_card", ["empresa_id"])


def downgrade() -> None:
    op.drop_index("ix_gift_card_empresa_id", table_name="gift_card")
    op.alter_column(
        "gift_card",
        "creada_en",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )
    op.drop_index("ix_cupon_descuento_empresa_id", table_name="cupon_descuento")
    op.create_index(
        "ix_cupon_empresa_codigo", "cupon_descuento", ["empresa_id", "codigo"]
    )
