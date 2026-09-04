"""El look de la página pública: plantilla, fondo, botones y tipografía.

QUÉ RESUELVE
────────────
Hasta acá lo único configurable de la vidriera era `color_marca`: un acento
sobre fondo blanco, idéntico para todos. Dos barberías de la misma cuadra
tenían la misma página con distinto logo — y esa página es lo que el negocio
comparte en su Instagram, o sea literalmente su cara. Que se parezcan todas
entre sí es el mejor argumento para no usarla.

POR QUÉ UNA COLUMNA JSONB Y NO NUEVE COLUMNAS
─────────────────────────────────────────────
Porque esto no se consulta nunca. Las reglas de reserva son columnas porque se
filtran y se comparan («¿cuántos días de anticipación permite?»); el look se
lee entero, se manda entero al navegador y se pinta. Cada opción nueva —un
patrón de fondo más, otra forma de botón, una tipografía— sería una migración
por algo que ninguna consulta va a mirar jamás.

La forma la valida `TemaVidriera` en schemas/empresa.py, que es donde tiene que
estar: los hex se chequean contra #rrggbb antes de guardarse porque terminan
dentro de una declaración CSS de una página pública, y las opciones son listas
cerradas para que todas las combinaciones se vean bien.

NULL Y {} SIGNIFICAN LO MISMO: el look de siempre. No hace falta backfill —el
schema completa los defaults al leer— así que las vidrieras existentes siguen
viéndose exactamente igual hasta que su dueño entre a cambiarlas.

Revision ID: 0003_tema
Revises: 0002_metodos
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_tema"
down_revision: Union[str, None] = "0002_metodos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column("tema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("empresa", "tema")
