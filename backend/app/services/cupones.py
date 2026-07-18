"""Cupones de descuento: CRUD del panel + validación de la reserva pública.

La validación devuelve SIEMPRE un motivo claro cuando el cupón no corre:
"no existe", "vencido", "agotado", "no aplica a este servicio". El cliente
que tipea un código merece saber por qué no le funcionó.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cupon import CuponDescuento
from app.models.agenda import Servicio
from app.schemas.cupon import CuponCrear, CuponEditar


def listar_cupones(db: Session, empresa_id: int) -> list[CuponDescuento]:
    return list(
        db.scalars(
            select(CuponDescuento)
            .where(CuponDescuento.empresa_id == empresa_id)
            .order_by(CuponDescuento.activo.desc(), CuponDescuento.id.desc())
        )
    )


def crear_cupon(
    db: Session, empresa_id: int, datos: CuponCrear
) -> CuponDescuento | None:
    """Crea el cupón. None si el código ya existe en la empresa."""
    repetido = db.scalar(
        select(CuponDescuento.id).where(
            CuponDescuento.empresa_id == empresa_id,
            CuponDescuento.codigo == datos.codigo,
        )
    )
    if repetido:
        return None
    cupon = CuponDescuento(empresa_id=empresa_id, **datos.model_dump())
    db.add(cupon)
    db.commit()
    db.refresh(cupon)
    return cupon


def editar_cupon(
    db: Session, empresa_id: int, cupon_id: int, datos: CuponEditar
) -> CuponDescuento | None:
    cupon = db.scalar(
        select(CuponDescuento).where(
            CuponDescuento.id == cupon_id,
            CuponDescuento.empresa_id == empresa_id,
        )
    )
    if cupon is None:
        return None
    # Si cambia el código, que no pise otro existente.
    if datos.codigo != cupon.codigo:
        repetido = db.scalar(
            select(CuponDescuento.id).where(
                CuponDescuento.empresa_id == empresa_id,
                CuponDescuento.codigo == datos.codigo,
                CuponDescuento.id != cupon_id,
            )
        )
        if repetido:
            return None
    for campo, valor in datos.model_dump().items():
        setattr(cupon, campo, valor)
    db.commit()
    db.refresh(cupon)
    return cupon


def borrar_cupon(db: Session, empresa_id: int, cupon_id: int) -> bool:
    cupon = db.scalar(
        select(CuponDescuento).where(
            CuponDescuento.id == cupon_id,
            CuponDescuento.empresa_id == empresa_id,
        )
    )
    if cupon is None:
        return False
    db.delete(cupon)
    db.commit()
    return True


# ── Validación (la usan la reserva pública y el propio panel) ────────────────

def validar_cupon(
    db: Session, empresa_id: int, codigo: str, servicio_id: int
) -> tuple[CuponDescuento | None, float, str]:
    """Valida un código contra un servicio.

    Devuelve (cupon, descuento_en_pesos, mensaje). Si el cupón no corre,
    cupon=None y el mensaje explica el motivo exacto.
    """
    codigo = (codigo or "").strip().upper().replace(" ", "")
    if not codigo:
        return None, 0.0, "Escribí un código"

    cupon = db.scalar(
        select(CuponDescuento).where(
            CuponDescuento.empresa_id == empresa_id,
            CuponDescuento.codigo == codigo,
        )
    )
    if cupon is None or not cupon.activo:
        return None, 0.0, "El código no existe o ya no está vigente"

    if cupon.vence_el is not None and dt.date.today() > cupon.vence_el:
        return None, 0.0, "El código venció"

    if cupon.max_usos is not None and cupon.usos >= cupon.max_usos:
        return None, 0.0, "El código ya alcanzó su límite de usos"

    servicios = list(cupon.servicios_ids or [])
    if servicios and servicio_id not in servicios:
        return None, 0.0, "El código no aplica a este servicio"

    servicio = db.scalar(
        select(Servicio).where(
            Servicio.id == servicio_id, Servicio.empresa_id == empresa_id
        )
    )
    precio = float(servicio.precio) if servicio and servicio.precio else 0.0
    if precio <= 0:
        return None, 0.0, "Este servicio no tiene precio para descontar"

    if cupon.tipo == "porcentaje":
        descuento = round(precio * float(cupon.valor) / 100, 2)
    else:  # monto fijo: nunca más que el precio
        descuento = round(min(float(cupon.valor), precio), 2)

    return cupon, descuento, "Código aplicado"


def pct_equivalente(descuento: float, precio: float) -> float:
    """Traduce un descuento en pesos al % sobre el precio (para descuento_pct).

    El sistema de totales del turno trabaja en porcentaje: un cupón de $2.000
    sobre un servicio de $10.000 se guarda como 20%.
    """
    if precio <= 0:
        return 0.0
    return round(min(descuento / precio * 100, 100), 2)
