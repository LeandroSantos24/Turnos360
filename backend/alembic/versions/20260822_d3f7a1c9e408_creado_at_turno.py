"""Cuándo se creó cada turno.

PARA QUÉ
--------
Para poder soltar los horarios que quedaron tomados por una seña que nunca se
pagó. Una reserva con seña queda en PENDIENTE y ocupa la agenda desde el
segundo cero; si el cliente cierra Mercado Pago sin pagar, ese horario queda
tomado para siempre porque no había nada que lo liberara.

Para saber "hace cuánto que está esperando" hace falta saber cuándo se creó, y
la tabla `turno` no guardaba esa fecha en ningún lado.

SOBRE EL RELOJ (importante)
---------------------------
Esta columna la escribe Postgres con `now()`: es un INSTANTE REAL en UTC.

NO es la "hora de pared etiquetada UTC" que usa `fecha_inicio`. Son dos
convenciones distintas conviviendo en la misma tabla, y mezclarlas da tres
horas de error. Regla: `creado_at` se compara contra
`datetime.now(timezone.utc)`; `fecha_inicio` contra `ahora_de_pared()`.

SOBRE LAS FILAS QUE YA EXISTEN
-------------------------------
Toman `now()` al correr la migración, o sea que arrancan "recién creadas".
Eso es lo que conviene: si alguna quedó colgada de antes, se le da el mismo
plazo que a una nueva en vez de cancelarla de golpe al primer barrido.
"""

import sqlalchemy as sa
from alembic import op

revision = "d3f7a1c9e408"
down_revision = "c7e5a91b4d02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "turno",
        sa.Column(
            "creado_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Índice parcial: el barrido busca SOLO las señas impagas, que son un
    # puñado entre todos los turnos. Un índice completo sobre creado_at
    # ocuparía lugar y se actualizaría en cada alta para nada.
    op.create_index(
        "ix_turno_sena_pendiente",
        "turno",
        ["creado_at"],
        postgresql_where=sa.text("sena_estado = 'pendiente'"),
    )


def downgrade() -> None:
    op.drop_index("ix_turno_sena_pendiente", table_name="turno")
    op.drop_column("turno", "creado_at")
