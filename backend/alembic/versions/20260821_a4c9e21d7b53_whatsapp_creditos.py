"""WhatsApp: saldo de mensajes, libro de movimientos y consentimiento.

QUÉ AGREGA
----------
1. `wa_saldo`      — cuántos mensajes le quedan a cada empresa.
2. `wa_movimiento` — el libro: cada carga y cada consumo, con fecha y precio.
3. `mensaje.externo_id` — el id que devuelve Meta (wamid), para poder
   correlacionar el webhook de "entregado"/"leído" con la fila local.
4. `cliente.acepta_whatsapp` — consentimiento.
5. Las dos plantillas de arranque (confirmación y recordatorio de 24 h) para
   cada empresa que ya exista, en estado ACTIVA pero NO aprobada en Meta.

POR QUÉ `acepta_whatsapp` ARRANCA EN TRUE
------------------------------------------
Son mensajes de *utility*: le avisan a alguien sobre un turno que esa misma
persona sacó, en el teléfono que esa misma persona dio para sacarlo. No es
publicidad. Arrancar en false significaría no mandarle recordatorio a nadie
de los que ya están cargados, que es justamente lo que se está comprando.

La contracara es que tiene que haber una forma de decir que no, y la hay: la
columna es editable por cliente y el mensaje lleva la instrucción de baja.
Para campañas de MARKETING no alcanza con esto: eso sigue mirando
`acepta_marketing`, que ya existía y que arranca en false.

POR QUÉ LAS PLANTILLAS NACEN ACTIVAS SIN SALDO
-----------------------------------------------
Porque sin saldo no sale ningún mensaje igual: `enviar_plantilla()` chequea el
crédito antes de tocar la red. Nacen activas para que el circuito se pueda
probar apenas se cargue el primer pack, sin tener que ir a prender nada.
"""

import sqlalchemy as sa
from alembic import op

revision = "a4c9e21d7b53"
down_revision = "f1b8d3e5a927"
branch_labels = None
depends_on = None


# El texto usa {{1}}, {{2}}... igual que las plantillas de Meta, así lo que se
# ve en el modo simulado es exactamente lo que Meta va a mandar el día que se
# conecte de verdad.
PLANTILLAS = [
    (
        "confirmacion",
        "Confirmación de turno",
        "Hola {{1}}! Te confirmamos {{2}} en {{3}} para el {{4}}. "
        "Si no podés venir, avisanos así liberamos el horario. "
        "Respondé BAJA para no recibir más mensajes.",
    ),
    (
        "recordatorio_24h",
        "Recordatorio 24 h antes",
        "Hola {{1}}! Te recordamos {{2}} en {{3}}: {{4}}. "
        "Si no podés venir, avisanos así liberamos el horario. "
        "Respondé BAJA para no recibir más mensajes.",
    ),
]


def upgrade() -> None:
    # ── 1. Saldo ────────────────────────────────────────────────────────────
    op.create_table(
        "wa_saldo",
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("disponible", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumidos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "actualizado",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"], name="fk_wa_saldo_empresa_id_empresa"),
        sa.PrimaryKeyConstraint("empresa_id", name="pk_wa_saldo"),
    )

    # ── 2. Libro de movimientos ─────────────────────────────────────────────
    op.create_table(
        "wa_movimiento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(length=20), nullable=False),
        sa.Column("detalle", sa.String(length=200), nullable=True),
        sa.Column("precio_ars", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("mensaje_id", sa.BigInteger(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column(
            "fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name="fk_wa_movimiento_empresa_id_empresa"
        ),
        sa.ForeignKeyConstraint(
            ["mensaje_id"], ["mensaje.id"], name="fk_wa_movimiento_mensaje_id_mensaje"
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name="fk_wa_movimiento_usuario_id_usuario"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wa_movimiento"),
    )
    op.create_index("ix_wa_movimiento_empresa_id", "wa_movimiento", ["empresa_id"])
    op.create_index("ix_wa_movimiento_empresa_fecha", "wa_movimiento", ["empresa_id", "fecha"])

    # ── 3. El id de Meta en la tabla de mensajes ────────────────────────────
    op.add_column("mensaje", sa.Column("externo_id", sa.String(length=80), nullable=True))
    # El webhook busca por acá y llega de a lotes: sin índice, cada "leído" es
    # un scan de la tabla que más rápido crece del sistema.
    op.create_index("ix_mensaje_externo_id", "mensaje", ["externo_id"], unique=False)

    # ── 4. Consentimiento ───────────────────────────────────────────────────
    op.add_column(
        "cliente",
        sa.Column(
            "acepta_whatsapp", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )

    # ── 5. Plantillas de arranque para las empresas que ya existen ──────────
    conexion = op.get_bind()
    empresas = conexion.execute(sa.text("SELECT id FROM empresa")).scalars().all()
    for empresa_id in empresas:
        for codigo, nombre, cuerpo in PLANTILLAS:
            ya = conexion.execute(
                sa.text(
                    "SELECT 1 FROM plantilla_mensaje "
                    "WHERE empresa_id = :e AND canal = 'whatsapp' AND codigo = :c"
                ),
                {"e": empresa_id, "c": codigo},
            ).first()
            if ya:
                continue
            conexion.execute(
                sa.text(
                    "INSERT INTO plantilla_mensaje "
                    "(empresa_id, canal, codigo, nombre, cuerpo, aprobada_meta, activa) "
                    "VALUES (:e, 'whatsapp', :c, :n, :cuerpo, false, true)"
                ),
                {"e": empresa_id, "c": codigo, "n": nombre, "cuerpo": cuerpo},
            )


def downgrade() -> None:
    conexion = op.get_bind()
    conexion.execute(
        sa.text(
            "DELETE FROM plantilla_mensaje WHERE canal = 'whatsapp' AND codigo IN "
            "('confirmacion', 'recordatorio_24h')"
        )
    )
    op.drop_column("cliente", "acepta_whatsapp")
    op.drop_index("ix_mensaje_externo_id", table_name="mensaje")
    op.drop_column("mensaje", "externo_id")
    op.drop_index("ix_wa_movimiento_empresa_fecha", table_name="wa_movimiento")
    op.drop_index("ix_wa_movimiento_empresa_id", table_name="wa_movimiento")
    op.drop_table("wa_movimiento")
    op.drop_table("wa_saldo")
