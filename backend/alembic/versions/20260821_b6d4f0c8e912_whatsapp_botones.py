"""WhatsApp: botones en el recordatorio y mensajes entrantes.

QUÉ AGREGA
----------
1. `plantilla_mensaje.con_botones` — si esa plantilla lleva los botones
   "Confirmo" / "No puedo ir".
2. `empresa.wa_phone_number_id` — el número de WhatsApp del negocio, EN CLARO.
3. Reescribe el cuerpo del recordatorio de 24 h para que pida confirmación, y
   le prende los botones.

POR QUÉ EL phone_number_id VA EN CLARO
--------------------------------------
No es un secreto: es un identificador público de un número de teléfono
comercial. El secreto es el token, que sigue cifrado con Fernet al lado.

Va suelto y con índice porque es la llave por la que entra CADA mensaje del
webhook: sin él habría que desencriptar las credenciales de todas las empresas
en cada mensaje que llega para saber a quién le escribieron. Con cien negocios
eso son cien desencriptados de Fernet por mensaje.

POR QUÉ SE RESETEA `aprobada_meta`
-----------------------------------
Porque el mensaje cambió. Meta aprueba un texto concreto, y esta migración lo
reescribe y le suma botones. Dejar la plantilla marcada como aprobada sería
mentirle al código: intentaría mandar componentes de botón contra una
plantilla aprobada que no los tiene, y Meta rechazaría el envío.

Se resetea SOLO la de recordatorio_24h, que es la que cambia.
"""

import sqlalchemy as sa
from alembic import op

revision = "b6d4f0c8e912"
down_revision = "a4c9e21d7b53"
branch_labels = None
depends_on = None


# El cuerpo pide confirmación porque ahora hay botones para contestarla. El
# "Respondé BAJA" se queda igual: los botones son una comodidad, la baja es un
# derecho y tiene que estar escrita.
CUERPO_NUEVO = (
    "Hola {{1}}! Te recordamos {{2}} en {{3}}: {{4}}. "
    "¿Nos confirmás que venís? Si no podés, tocá «No puedo ir» y liberamos "
    "el horario. Respondé BAJA para no recibir más mensajes."
)

CUERPO_VIEJO = (
    "Hola {{1}}! Te recordamos {{2}} en {{3}}: {{4}}. "
    "Si no podés venir, avisanos así liberamos el horario. "
    "Respondé BAJA para no recibir más mensajes."
)


def upgrade() -> None:
    op.add_column(
        "plantilla_mensaje",
        sa.Column("con_botones", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column("empresa", sa.Column("wa_phone_number_id", sa.String(length=40), nullable=True))
    op.create_index("ix_empresa_wa_phone_number_id", "empresa", ["wa_phone_number_id"])

    op.get_bind().execute(
        sa.text(
            "UPDATE plantilla_mensaje "
            "SET cuerpo = :cuerpo, con_botones = true, aprobada_meta = false "
            "WHERE canal = 'whatsapp' AND codigo = 'recordatorio_24h'"
        ),
        {"cuerpo": CUERPO_NUEVO},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE plantilla_mensaje SET cuerpo = :cuerpo, aprobada_meta = false "
            "WHERE canal = 'whatsapp' AND codigo = 'recordatorio_24h'"
        ),
        {"cuerpo": CUERPO_VIEJO},
    )
    op.drop_index("ix_empresa_wa_phone_number_id", table_name="empresa")
    op.drop_column("empresa", "wa_phone_number_id")
    op.drop_column("plantilla_mensaje", "con_botones")
