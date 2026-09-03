"""Los métodos de cobro con los que nace toda empresa.

POR QUÉ SE SIEMBRAN Y NO SE PIDEN
─────────────────────────────────
La tabla arrancaba vacía y la pantalla saludaba con «Todavía no cargaste
métodos. Empezá con Efectivo, Débito, Transferencia…». Es pedirle a alguien que
recién entra que escriba de memoria los mismos cinco nombres que escribe todo
el mundo y que además adivine la comisión de cada uno. Y hasta que no los
cargaba no podía registrar un solo cobro, que es exactamente lo primero que
quiere hacer un negocio con un sistema de turnos.

Son los cinco que usa cualquier mostrador en Argentina. El que no use alguno lo
apaga con un clic; el que cobre de otra forma agrega el suyo.

DE DÓNDE SALEN LAS COMISIONES
─────────────────────────────
Las de Mercado Pago son las publicadas para dinero en cuenta (1,6 %), débito
(2,3 %) y crédito (4,2 %), sin el IVA, que es como las piensa el comerciante.
Son un PUNTO DE PARTIDA editable, no una verdad: cada negocio tiene la suya
negociada, la de su posnet o la de su banco, y cambian seguido. Por eso se
guardan por empresa y se editan desde la pantalla — no son una constante del
sistema.

Efectivo y transferencia van en cero: no las cobra nadie.

QUÉ PASA SI YA EXISTEN
──────────────────────
Nada. `sembrar` es idempotente por `clave`: se puede llamar en el alta, en una
migración de datos y en el seed sin duplicar nada ni pisar la comisión que el
dueño haya ajustado. Eso importa porque el día que agreguemos un sexto medio
(MODO, una billetera nueva) lo vamos a querer sumar a las empresas que ya
existen sin tocarles lo que configuraron.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finanzas import MetodoPago

# (clave, nombre, comisión %, orden, instrucciones para el cliente)
#
# El orden es el del mostrador, no el alfabético: efectivo primero porque es
# el que más se toca, y el QR último porque es el más nuevo.
POR_DEFECTO: list[tuple[str, str, float, int, str | None]] = [
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
    (
        "mp_qr",
        "QR Mercado Pago",
        1.6,
        50,
        "Escaneá el QR en el local con la app de Mercado Pago.",
    ),
]

CLAVES = {clave for clave, *_ in POR_DEFECTO}


def sembrar(db: Session, empresa_id: int) -> list[MetodoPago]:
    """Deja los cinco métodos de fábrica en esta empresa. Idempotente.

    NO hace commit: se llama dentro del alta, que commitea una sola vez al
    final. Si esto commiteara por su cuenta, un error posterior en el alta
    dejaría una empresa a medio crear pero con sus métodos de pago — el
    registro huérfano que el resto del alta se cuida de no dejar.
    """
    ya_estan = set(
        db.scalars(
            select(MetodoPago.clave).where(
                MetodoPago.empresa_id == empresa_id,
                MetodoPago.clave.is_not(None),
            )
        )
    )

    nuevos: list[MetodoPago] = []
    for clave, nombre, comision, orden, instrucciones in POR_DEFECTO:
        if clave in ya_estan:
            continue
        metodo = MetodoPago(
            empresa_id=empresa_id,
            clave=clave,
            nombre=nombre,
            comision_pct=comision,
            orden=orden,
            instrucciones=instrucciones,
            activo=True,
        )
        db.add(metodo)
        nuevos.append(metodo)

    if nuevos:
        db.flush()
    return nuevos


def por_clave(db: Session, empresa_id: int, clave: str) -> MetodoPago | None:
    """El método de fábrica de esta empresa, buscado por clave y no por nombre.

    Buscar «Mercado Pago» por nombre —que es lo que se hacía— se rompe en
    cuanto alguien lo renombra «MP», le saca la mayúscula o le agrega
    « (QR)». La clave no la ve ni la toca nadie.
    """
    return db.scalars(
        select(MetodoPago).where(
            MetodoPago.empresa_id == empresa_id, MetodoPago.clave == clave
        )
    ).first()
