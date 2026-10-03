"""Suscripciones: cancelación, eventos, intentos de pago y auditoría admin.

Solo agrega columnas y tablas: no borra ni reescribe datos. Lo único que se
completa es `pago_suscripcion.tipo` para las cuotas existentes (todas son
"renovacion" salvo la primera de cada empresa, que es el "alta").

Revision ID: 0007_suscripciones
Revises: 0006_integridad_economica
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_suscripciones"
down_revision = "0006_integridad_economica"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Empresa: cancelación pedida por el negocio ─────────────────────
    op.add_column("empresa", sa.Column("cancela_al_vencer", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("empresa", sa.Column("cancelacion_solicitada_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("empresa", sa.Column("cancelacion_motivo", sa.String(length=300), nullable=True))
    op.add_column("empresa", sa.Column("cancelada_en", sa.DateTime(timezone=True), nullable=True))

    # ── Intentos de pago (conciliación de Mercado Pago) ────────────────
    op.create_table(
        "intento_pago",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("metodo", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default=sa.text("'iniciado'"), nullable=False),
        sa.Column("detalle", sa.String(length=200), nullable=True),
        sa.Column("mp_payment_id", sa.String(length=40), nullable=True),
        sa.Column("pago_id", sa.Integer(), nullable=True),
        sa.Column("iniciado_por", sa.String(length=160), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_intento_pago_empresa_id", "intento_pago", ["empresa_id"])
    op.create_index("ix_intento_pago_empresa", "intento_pago", ["empresa_id", "creado_en"])

    # ── Pago: qué fue, de qué plan, y su clave de idempotencia ─────────
    op.add_column("pago_suscripcion", sa.Column("tipo", sa.String(length=20), nullable=True))
    op.add_column("pago_suscripcion", sa.Column("plan", sa.String(length=20), nullable=True))
    op.add_column("pago_suscripcion", sa.Column("intento_id", sa.Integer(), nullable=True))
    op.add_column("pago_suscripcion", sa.Column("clave_idempotencia", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_pago_suscripcion_intento", "pago_suscripcion", "intento_pago", ["intento_id"], ["id"])
    op.create_index(
        "uq_pago_suscripcion_idem", "pago_suscripcion", ["clave_idempotencia"],
        unique=True, postgresql_where=sa.text("clave_idempotencia is not null"),
    )
    op.execute(
        """
        UPDATE pago_suscripcion p SET tipo = CASE
          WHEN p.id = (SELECT min(q.id) FROM pago_suscripcion q WHERE q.empresa_id = p.empresa_id)
          THEN 'alta' ELSE 'renovacion' END
        """
    )

    # ── Aviso: plan, monto esperado, comprobante y pedido de info ──────
    op.add_column("aviso_pago", sa.Column("plan", sa.String(length=20), nullable=True))
    op.add_column("aviso_pago", sa.Column("tipo", sa.String(length=20), nullable=True))
    op.add_column("aviso_pago", sa.Column("monto_esperado", sa.Numeric(12, 2), nullable=True))
    op.add_column("aviso_pago", sa.Column("comprobante", sa.String(length=200), nullable=True))
    op.add_column("aviso_pago", sa.Column("mensaje_admin", sa.String(length=300), nullable=True))

    # ── Ajuste → registro de eventos de la suscripción ─────────────────
    op.alter_column("ajuste_suscripcion", "tipo", type_=sa.String(length=30), existing_type=sa.String(length=20))
    op.add_column("ajuste_suscripcion", sa.Column("actor_tipo", sa.String(length=20), nullable=True))
    op.add_column("ajuste_suscripcion", sa.Column("estado_antes", sa.String(length=30), nullable=True))
    op.add_column("ajuste_suscripcion", sa.Column("estado_despues", sa.String(length=30), nullable=True))
    op.add_column("ajuste_suscripcion", sa.Column("plan_antes", sa.String(length=20), nullable=True))
    op.add_column("ajuste_suscripcion", sa.Column("plan_despues", sa.String(length=20), nullable=True))
    op.add_column("ajuste_suscripcion", sa.Column("monto", sa.Numeric(12, 2), nullable=True))
    op.add_column("ajuste_suscripcion", sa.Column("aviso_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_ajuste_aviso", "ajuste_suscripcion", "aviso_pago", ["aviso_id"], ["id"])

    # ── Auditoría del super-admin (append-only) ────────────────────────
    op.create_table(
        "auditoria_admin",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("admin_email", sa.String(length=160), nullable=False),
        sa.Column("accion", sa.String(length=40), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresa.id"), nullable=True),
        sa.Column("descripcion", sa.String(length=300), nullable=True),
        sa.Column("antes", postgresql.JSONB(), nullable=True),
        sa.Column("despues", postgresql.JSONB(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auditoria_admin_empresa", "auditoria_admin", ["empresa_id", "creado_en"])
    op.create_index("ix_auditoria_admin_fecha", "auditoria_admin", ["creado_en"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_admin_fecha", table_name="auditoria_admin")
    op.drop_index("ix_auditoria_admin_empresa", table_name="auditoria_admin")
    op.drop_table("auditoria_admin")
    op.drop_constraint("fk_ajuste_aviso", "ajuste_suscripcion", type_="foreignkey")
    for c in ("aviso_id", "monto", "plan_despues", "plan_antes", "estado_despues", "estado_antes", "actor_tipo"):
        op.drop_column("ajuste_suscripcion", c)
    for c in ("mensaje_admin", "comprobante", "monto_esperado", "tipo", "plan"):
        op.drop_column("aviso_pago", c)
    op.drop_index("uq_pago_suscripcion_idem", table_name="pago_suscripcion")
    op.drop_constraint("fk_pago_suscripcion_intento", "pago_suscripcion", type_="foreignkey")
    for c in ("clave_idempotencia", "intento_id", "plan", "tipo"):
        op.drop_column("pago_suscripcion", c)
    op.drop_index("ix_intento_pago_empresa", table_name="intento_pago")
    op.drop_index("ix_intento_pago_empresa_id", table_name="intento_pago")
    op.drop_table("intento_pago")
    for c in ("cancelada_en", "cancelacion_motivo", "cancelacion_solicitada_en", "cancela_al_vencer"):
        op.drop_column("empresa", c)
