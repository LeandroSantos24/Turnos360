"""El medidor de WhatsApp: saldo, packs y el libro de movimientos.

Regla de oro de este módulo: **no se manda un mensaje sin descontar el crédito
primero.** Meta cobra por mensaje entregado y la factura llega a fin de mes;
si el descuento fuera después del envío, un error entre medio manda mensajes
gratis y el agujero recién aparece cuando llega la factura.

Por eso `consumir()` toma el saldo con FOR UPDATE, lo baja, y recién ahí el
llamador manda. Si el envío falla, `devolver()` repone el crédito. Es más
trabajo que descontar después, pero el error cae del lado que no cuesta plata.
"""

import math

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.whatsapp import MovimientoWhatsapp, SaldoWhatsapp

# Cantidades de los packs que se venden. El precio sale del precio unitario:
# un solo número para tocar cuando se mueve el dólar o cuando sepamos la
# tarifa real de Meta para Argentina.
CANTIDADES_PACK = (250, 500, 1000, 2500)


class SinSaldo(RuntimeError):
    """La empresa se quedó sin mensajes. No es un error del sistema."""


def precio_mensaje_ars() -> float:
    """Precio de venta de UN mensaje, en pesos.

    El default está calculado sobre el PEOR escenario a propósito:

        tarifa utility más cara que encontré para Argentina  USD 0,0260
        dólar oficial venta                                  ARS 1.520
        + percepción RG 5617 30 % + IVA 21 % + IIBB 2 %
        = ARS 60,47 de desembolso por mensaje
        + 20 % de rentabilidad                               ARS 72,57  ->  73

    Se toma el DESEMBOLSO y no el costo neto porque la percepción del 30 % se
    recupera recién en la declaración del año siguiente: durante doce meses esa
    plata está puesta, y el precio tiene que bancarla.

    Cuando sepamos la tarifa real (WhatsApp Manager -> Insights -> Pricing) esto
    va a bajar bastante: si el utility argentino resulta ser USD 0,0034, el
    número honesto es ARS 10. Se cambia con WA_PRECIO_MENSAJE_ARS en el .env,
    sin tocar código.
    """
    return float(settings.wa_precio_mensaje_ars)


def packs() -> list[dict]:
    """Los packs a la venta, con el precio del día."""
    unitario = precio_mensaje_ars()
    salida = []
    for cantidad in CANTIDADES_PACK:
        # Redondeo hacia ARRIBA al siguiente múltiplo de 100: nunca vender
        # por debajo del costo por una cuestión de estética del precio.
        precio = math.ceil(cantidad * unitario / 100) * 100
        salida.append(
            {
                "cantidad": cantidad,
                "precio_ars": precio,
                "precio_por_mensaje": round(precio / cantidad, 2),
            }
        )
    return salida


def _fila_saldo(db: Session, empresa_id: int, bloquear: bool = False) -> SaldoWhatsapp:
    """Devuelve el renglón de saldo, creándolo si es la primera vez.

    El INSERT ... ON CONFLICT DO NOTHING evita la carrera clásica de dos
    envíos simultáneos de una empresa nueva: los dos ven que no existe, los
    dos insertan, y uno explota por clave duplicada.
    """
    db.execute(
        pg_insert(SaldoWhatsapp)
        .values(empresa_id=empresa_id, disponible=0, consumidos=0)
        .on_conflict_do_nothing(index_elements=["empresa_id"])
    )
    consulta = select(SaldoWhatsapp).where(SaldoWhatsapp.empresa_id == empresa_id)
    if bloquear:
        consulta = consulta.with_for_update()
    return db.scalars(consulta).one()


def saldo_de(db: Session, empresa_id: int) -> int:
    return _fila_saldo(db, empresa_id).disponible


def acreditar(
    db: Session,
    empresa_id: int,
    cantidad: int,
    motivo: str = "pack",
    precio_ars: float | None = None,
    usuario_id: int | None = None,
    detalle: str | None = None,
) -> int:
    """Suma mensajes. Devuelve el saldo nuevo.

    `precio_ars` es lo que el negocio PAGÓ, guardado tal cual: el precio de
    lista cambia con el dólar y sin esto no se puede reconstruir la facturación
    de un mes ya cerrado.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad a acreditar tiene que ser mayor que cero.")
    fila = _fila_saldo(db, empresa_id, bloquear=True)
    fila.disponible += cantidad
    db.add(
        MovimientoWhatsapp(
            empresa_id=empresa_id,
            cantidad=cantidad,
            motivo=motivo,
            detalle=detalle,
            precio_ars=precio_ars,
            usuario_id=usuario_id,
        )
    )
    db.flush()
    return fila.disponible


def consumir(
    db: Session,
    empresa_id: int,
    mensaje_id: int | None = None,
    detalle: str | None = None,
) -> int:
    """Descuenta UN mensaje. Levanta SinSaldo si no queda. Devuelve el saldo nuevo."""
    fila = _fila_saldo(db, empresa_id, bloquear=True)
    if fila.disponible < 1:
        raise SinSaldo("La empresa no tiene mensajes de WhatsApp disponibles.")
    fila.disponible -= 1
    fila.consumidos += 1
    db.add(
        MovimientoWhatsapp(
            empresa_id=empresa_id,
            cantidad=-1,
            motivo="envio",
            detalle=detalle,
            mensaje_id=mensaje_id,
        )
    )
    db.flush()
    return fila.disponible


def devolver(
    db: Session,
    empresa_id: int,
    mensaje_id: int | None = None,
    detalle: str | None = None,
) -> int:
    """Repone un crédito de un envío que falló. Nunca sube `consumidos`."""
    fila = _fila_saldo(db, empresa_id, bloquear=True)
    fila.disponible += 1
    fila.consumidos = max(0, fila.consumidos - 1)
    db.add(
        MovimientoWhatsapp(
            empresa_id=empresa_id,
            cantidad=1,
            motivo="devolucion",
            detalle=detalle,
            mensaje_id=mensaje_id,
        )
    )
    db.flush()
    return fila.disponible


def movimientos(db: Session, empresa_id: int, limite: int = 50) -> list[MovimientoWhatsapp]:
    return list(
        db.scalars(
            select(MovimientoWhatsapp)
            .where(MovimientoWhatsapp.empresa_id == empresa_id)
            .order_by(MovimientoWhatsapp.fecha.desc(), MovimientoWhatsapp.id.desc())
            .limit(limite)
        )
    )


def recalcular(db: Session, empresa_id: int) -> int:
    """Reconstruye el saldo sumando el libro. El libro manda.

    Existe para el día en que el contador y el libro no coincidan —un bug, una
    transacción a medias, una restauración de backup—. Sin esto, la única
    salida sería un UPDATE a mano contra producción.
    """
    total = sum(
        m.cantidad
        for m in db.scalars(
            select(MovimientoWhatsapp).where(MovimientoWhatsapp.empresa_id == empresa_id)
        )
    )
    fila = _fila_saldo(db, empresa_id, bloquear=True)
    fila.disponible = max(0, total)
    db.flush()
    return fila.disponible


def resumen(db: Session, empresa_id: int) -> dict:
    fila = _fila_saldo(db, empresa_id)
    return {
        "disponible": fila.disponible,
        "consumidos": fila.consumidos,
        "precio_mensaje_ars": precio_mensaje_ars(),
        "packs": packs(),
    }
