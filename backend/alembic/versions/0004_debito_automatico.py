"""La tabla del débito automático de Mercado Pago.

Una fila por suscripción (`preapproval`) creada en la cuenta de Turnos360.
Ver el docstring de `models/saas.py::DebitoAutomatico` para el porqué de la
tabla —en resumen: los preapprovals cancelados siguen mandando notificaciones
y hay que poder distinguirlos del vivo—.

EL ÍNDICE PARCIAL ES LA PARTE QUE IMPORTA
─────────────────────────────────────────
`uq_debito_vivo_por_empresa` es único solo sobre las filas cuyo estado no es
'cancelled'. Es lo que garantiza que una empresa no pueda terminar con dos
débitos automáticos vivos —dos autorizaciones sobre la misma tarjeta, dos
cargos por mes—. Un doble click en «Activar» alcanza para provocarlo, y no se
puede confiar en que el código lo evite: entre el SELECT que comprueba y el
INSERT que crea hay una ventana, y ahí es donde entra el segundo click.

Revision ID: 0004_debito
Revises: 0003_precio_pactado
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_debito"
down_revision = "0003_precio_pactado"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debito_automatico",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("preapproval_id", sa.String(length=64), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("plan", sa.String(length=20), nullable=True),
        sa.Column("monto", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("proximo_cobro", sa.Date(), nullable=True),
        sa.Column(
            "cobros_fallidos", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("ultimo_error", sa.String(length=200), nullable=True),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelada_por", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("preapproval_id", name="uq_debito_preapproval"),
    )
    op.create_index(
        "ix_debito_automatico_empresa_id", "debito_automatico", ["empresa_id"]
    )
    op.create_index(
        "uq_debito_vivo_por_empresa",
        "debito_automatico",
        ["empresa_id"],
        unique=True,
        postgresql_where=sa.text("estado <> 'cancelled'"),
    )


def downgrade() -> None:
    op.drop_index("uq_debito_vivo_por_empresa", table_name="debito_automatico")
    op.drop_index("ix_debito_automatico_empresa_id", table_name="debito_automatico")
    op.drop_table("debito_automatico")
