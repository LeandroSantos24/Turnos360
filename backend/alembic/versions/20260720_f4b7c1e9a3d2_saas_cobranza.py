"""E16 tanda 1: cobranza del SaaS (pago_suscripcion) + datos comerciales de Empresa.

Revision ID: f4b7c1e9a3d2
Revises: e1a4c9d2f6b8
Create Date: 2026-07-20

Agrega lo que el panel de super-admin necesita para la gestión de cobranza:
- Ficha comercial de cada negocio (razón social, CUIT, contacto, notas).
- precio_mensual pactado: base del MRR y del pendiente estimado.
- limite_recursos: tope de profesionales del plan.
- Tabla pago_suscripcion: el historial de cuotas cobradas.
"""

from alembic import op
import sqlalchemy as sa


revision = "f4b7c1e9a3d2"
down_revision = "e1a4c9d2f6b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Ficha comercial en Empresa (todo opcional: las empresas ya existentes
    #    quedan con NULL y el panel las muestra igual) ──────────────────
    op.add_column("empresa", sa.Column("razon_social", sa.String(160), nullable=True))
    op.add_column("empresa", sa.Column("cuit", sa.String(20), nullable=True))
    op.add_column("empresa", sa.Column("contacto_nombre", sa.String(120), nullable=True))
    op.add_column("empresa", sa.Column("contacto_email", sa.String(160), nullable=True))
    op.add_column("empresa", sa.Column("contacto_telefono", sa.String(40), nullable=True))
    op.add_column("empresa", sa.Column("notas_admin", sa.Text(), nullable=True))
    op.add_column("empresa", sa.Column("precio_mensual", sa.Numeric(12, 2), nullable=True))
    op.add_column("empresa", sa.Column("limite_recursos", sa.Integer(), nullable=True))

    # ── Cobranza del SaaS ───────────────────────────────────────────────
    op.create_table(
        "pago_suscripcion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresa.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "metodo",
            sa.String(40),
            nullable=False,
            server_default="transferencia",
        ),
        sa.Column("periodo_desde", sa.Date(), nullable=True),
        sa.Column("periodo_hasta", sa.Date(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("registrado_por", sa.String(160), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_pago_suscripcion_fecha", "pago_suscripcion", ["fecha"])
    op.create_index(
        "ix_pago_suscripcion_empresa_fecha", "pago_suscripcion", ["empresa_id", "fecha"]
    )


def downgrade() -> None:
    op.drop_index("ix_pago_suscripcion_empresa_fecha", table_name="pago_suscripcion")
    op.drop_index("ix_pago_suscripcion_fecha", table_name="pago_suscripcion")
    op.drop_table("pago_suscripcion")
    for col in (
        "limite_recursos",
        "precio_mensual",
        "notas_admin",
        "contacto_telefono",
        "contacto_email",
        "contacto_nombre",
        "cuit",
        "razon_social",
    ):
        op.drop_column("empresa", col)
