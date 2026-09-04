"""El plan al que cae una empresa cuando vence el ciclo que ya pagó.

QUÉ RESUELVE
────────────
Cambiar de plan dependía del super-admin: el dueño tenía que escribir y
esperar. Con el cobro por Mercado Pago ya automatizado, ese era el último
trámite manual del circuito de venta.

Subir se resuelve pagando —el webhook activa el plan que viene en el
external_reference— y no necesita ninguna columna. Bajar sí, y es el motivo de
este archivo: una baja NO puede aplicarse en el momento, porque el mes en
curso ya está pagado. Quitarle Multi a alguien que lo pagó hasta fin de mes es
exactamente el tipo de cosa por la que uno deja de bajar de plan y directamente
da de baja la cuenta.

Entonces la baja se ANOTA acá, el ciclo se respeta entero, y el barrido diario
de cobranza la aplica cuando el vencimiento pasa.

POR QUÉ NO ALCANZABA CON UNA FECHA
──────────────────────────────────
La fecha ya existe: es `suscripcion_vence`. Guardar una segunda sería tener dos
fechas que pueden separarse — y el día que se separen, nadie sabría cuál manda.
Con una sola columna de texto, la regla se lee sola: «cuando venza, pasás a
esto».

NULL = sigue en su plan. Se limpia sola en cuanto la empresa paga: si pagó,
volvió a elegir, y lo que eligió gana sobre lo que había anotado antes.

Revision ID: 0004_plan
Revises: 0003_tema
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_plan"
down_revision: Union[str, None] = "0003_tema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "empresa", sa.Column("plan_programado", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    """Se pierden las bajas anotadas y todos siguen en su plan actual.

    Es lo correcto: sin la columna no hay forma de aplicarlas, y dejar a
    alguien en un plan MÁS alto del que pidió no le hace daño a nadie —al
    revés que la alternativa.
    """
    op.drop_column("empresa", "plan_programado")
