"""Etiqueta de conversión de Google Ads.

EL PROBLEMA
-----------
La pantalla de Seguimiento invita a pegar un tag de Google Ads —dice textual
«AW-XXXXXXXXX (Ads)»— y el evento que se dispara al confirmar una reserva es
`generate_lead`. Ese evento va a Google ANALYTICS, no a Google ADS.

Para que Google Ads cuente una conversión hace falta, según su propia
documentación:

    gtag('event', 'conversion', {
      'send_to': 'AW-123456789/AbC-D_efG-h12_34-567',
      ...
    })

Los dos pedazos: el ID de conversión Y LA ETIQUETA. La etiqueta no se pedía en
ningún lado, así que no había forma de armar ese `send_to`.

POR QUÉ ES PEOR QUE NO MEDIR
-----------------------------
Un negocio que conecta su AW- ve las visitas subir y las conversiones en CERO.
La conclusión que saca es «la publicidad no me rinde» y corta la campaña — con
un dato falso. Medir mal es peor que no medir: no medir te deja sin
información, medir mal te da información equivocada y actuás sobre ella.

POR QUÉ LA COLUMNA ES CHICA Y VALIDADA
---------------------------------------
Esta etiqueta termina DENTRO de un <script> en la vidriera pública, igual que
el pixel ID. Mismo riesgo de XSS y misma defensa: lista blanca cerrada en el
schema. Ver `backend/app/schemas/empresa.py`.
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e5a91b4d02"
down_revision = "b6d4f0c8e912"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column("google_conversion_label", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("empresa", "google_conversion_label")
