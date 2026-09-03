"""Los cinco métodos de cobro de fábrica, y el arreglo del match de Mercado Pago.

QUÉ AGREGA AL ESQUEMA
─────────────────────
Tres columnas en `metodo_pago`:
  · `clave`         — cuál de los cinco de fábrica es; NULL en los propios.
  · `orden`         — el orden del mostrador, en vez del alfabético.
  · `instrucciones` — lo que el cliente lee al elegir ese medio al reservar.

Y un único parcial sobre (empresa_id, clave): una empresa no puede terminar con
dos «efectivo». Los propios quedan fuera del índice porque ahí el dueño elige
el nombre que quiera y puede repetir si se le antoja.

QUÉ HACE CON LOS DATOS QUE YA ESTÁN
───────────────────────────────────
Dos pasos, y el orden entre ellos es lo importante:

1. ADOPTA los métodos que ya existen. A cada empresa se le buscan sus métodos
   por nombre normalizado —«mercado pago», «MP», «efectivo », «Débito»— y al
   que coincide se le pone la clave que le corresponde. Recién después:

2. SIEMBRA los que falten.

Si se hiciera al revés, una empresa que ya tenía cargado «Mercado Pago» a mano
terminaría con DOS: el suyo con la historia de cobros colgando, y el nuevo con
la clave. Y como el código busca por clave, los cobros nuevos irían al vacío
mientras la caja vieja sigue apuntando al otro. Adoptar primero evita
exactamente eso.

Solo se adopta el PRIMERO que coincide con cada clave (por id, el más viejo).
Si un negocio tiene dos «efectivo» cargados por error, el segundo queda como
método propio: no se borra nada.

POR QUÉ ESTO IMPORTA MÁS DE LO QUE PARECE
─────────────────────────────────────────
`_metodo_mercado_pago()` —el que decide dónde entra la plata de cada seña—
buscaba `lower(nombre) == "mercado pago"`. Si alguien renombraba su método,
ese match fallaba y la función creaba uno nuevo en silencio: dos «Mercado
Pago», la plata de las señas repartida entre los dos, y la caja cuadrando mal
sin que nada tirara un error. Desde acá busca por `clave`, que no se ve ni se
edita desde ninguna pantalla.

Revision ID: 0002_metodos
Revises: 0001_base
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_metodos"
down_revision: Union[str, None] = "0001_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (clave, nombre, comisión %, orden, instrucciones). Espejo de
# app/services/metodos_pago.POR_DEFECTO — duplicado a propósito: una migración
# tiene que seguir corriendo igual dentro de un año, cuando ese módulo haya
# cambiado. Importarlo desde acá haría que el pasado dependiera del presente.
POR_DEFECTO = [
    ("efectivo", "Efectivo", 0.0, 10, "Se abona en el local al momento del turno."),
    ("debito", "Débito", 2.3, 20, None),
    ("credito", "Crédito", 4.2, 30, None),
    (
        "transferencia",
        "Transferencia",
        0.0,
        40,
        "Transferí y mandanos el comprobante por WhatsApp. "
        "Completá acá tu alias y tu CBU.",
    ),
    ("mp_qr", "QR Mercado Pago", 1.6, 50, "Escaneá el QR en el local con la app de Mercado Pago."),
]

# Cómo se llama en la práctica cada uno de los cinco. Todo en minúscula y sin
# espacios de más: así se compara.
ALIAS: dict[str, set[str]] = {
    "efectivo": {"efectivo", "contado", "cash"},
    "debito": {"debito", "débito", "tarjeta de debito", "tarjeta de débito"},
    "credito": {"credito", "crédito", "tarjeta de credito", "tarjeta de crédito"},
    "transferencia": {"transferencia", "transf", "transferencia bancaria", "cbu"},
    "mp_qr": {
        "mercado pago", "mercadopago", "mp", "qr", "qr mercado pago",
        "mercado pago qr", "mp qr",
    },
}


def upgrade() -> None:
    op.add_column("metodo_pago", sa.Column("clave", sa.String(length=20), nullable=True))
    op.add_column(
        "metodo_pago",
        sa.Column("orden", sa.Integer(), server_default=sa.text("100"), nullable=False),
    )
    op.add_column(
        "metodo_pago", sa.Column("instrucciones", sa.String(length=1000), nullable=True)
    )

    conn = op.get_bind()

    # ── Paso 1: adoptar lo que ya existe ────────────────────────────────
    # Se recorre por empresa para poder quedarse con el más viejo de cada
    # clave sin depender de un DISTINCT ON que sería más difícil de leer.
    filas = conn.execute(
        sa.text(
            "SELECT id, empresa_id, lower(btrim(nombre)) AS nombre "
            "FROM metodo_pago ORDER BY empresa_id, id"
        )
    ).fetchall()

    tomadas: set[tuple[int, str]] = set()
    for fila in filas:
        for clave, alias in ALIAS.items():
            if fila.nombre in alias and (fila.empresa_id, clave) not in tomadas:
                conn.execute(
                    sa.text(
                        "UPDATE metodo_pago SET clave = :clave, orden = :orden "
                        "WHERE id = :id"
                    ),
                    {
                        "clave": clave,
                        "orden": next(o for c, _, _, o, _ in POR_DEFECTO if c == clave),
                        "id": fila.id,
                    },
                )
                tomadas.add((fila.empresa_id, clave))
                break

    # ── Paso 2: sembrar lo que falte, empresa por empresa ───────────────
    empresas = [r.id for r in conn.execute(sa.text("SELECT id FROM empresa ORDER BY id"))]
    for empresa_id in empresas:
        for clave, nombre, comision, orden, instrucciones in POR_DEFECTO:
            if (empresa_id, clave) in tomadas:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO metodo_pago "
                    "  (empresa_id, nombre, comision_pct, activo, clave, orden, instrucciones) "
                    "VALUES (:e, :n, :c, true, :k, :o, :i)"
                ),
                {
                    "e": empresa_id, "n": nombre, "c": comision,
                    "k": clave, "o": orden, "i": instrucciones,
                },
            )

    # El único va DESPUÉS del backfill: si fuera antes y algún dato viejo
    # estuviera duplicado, la migración moriría a mitad de camino.
    op.create_index(
        "uq_metodo_pago_clave",
        "metodo_pago",
        ["empresa_id", "clave"],
        unique=True,
        postgresql_where=sa.text("clave IS NOT NULL"),
    )


def downgrade() -> None:
    """Vuelve el esquema atrás. Los métodos sembrados quedan como propios.

    No se borran: para cuando alguien baje esta migración pueden tener cobros
    colgando, y borrarlos rompería la caja. Sin `clave` simplemente pasan a ser
    métodos comunes, que es lo que eran antes.
    """
    op.drop_index(
        "uq_metodo_pago_clave", table_name="metodo_pago",
        postgresql_where=sa.text("clave IS NOT NULL"),
    )
    op.drop_column("metodo_pago", "instrucciones")
    op.drop_column("metodo_pago", "orden")
    op.drop_column("metodo_pago", "clave")
