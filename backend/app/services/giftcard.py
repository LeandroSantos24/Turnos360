"""Lógica de gift cards: generación del código, verificación y canje.

La genuinidad se resuelve así:
- El código sale de `secrets.token_hex` (criptográfico): no se puede adivinar.
- Toda consulta filtra por empresa_id: un código de otra empresa da "no existe".
- El canje es atómico y de una sola vez: si ya está CANJEADA o VENCIDA, rechaza.
"""

import datetime as dt
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app.models import GiftCard
from app.models.enums import EstadoGiftCard, TipoMovimiento
from app.models.finanzas import MetodoPago, MovimientoFinanciero, Pago
from app.schemas.giftcard import GiftCardCrear


def _generar_codigo() -> str:
    """Código legible tipo GIFT-A1B2-C3D4 (mayúsculas, sin caracteres ambiguos)."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I,O,0,1
    bloques = [
        "".join(secrets.choice(alfabeto) for _ in range(4)),
        "".join(secrets.choice(alfabeto) for _ in range(4)),
    ]
    return f"GIFT-{bloques[0]}-{bloques[1]}"


def _codigo_unico(db: Session, empresa_id: int) -> str:
    """Genera un código y reintenta en el caso improbable de colisión."""
    for _ in range(10):
        codigo = _generar_codigo()
        existe = db.scalar(
            select(GiftCard.id).where(
                GiftCard.empresa_id == empresa_id, GiftCard.codigo == codigo
            )
        )
        if not existe:
            return codigo
    # 10 colisiones seguidas es estadísticamente imposible; si pasa, que explote.
    raise RuntimeError("No se pudo generar un código único de gift card")


def crear(
    db: Session,
    empresa_id: int,
    datos: GiftCardCrear,
    usuario_id: int | None = None,
) -> GiftCard:
    """Crea la gift card y, si se indicó método de pago, cobra la venta.

    Vender una gift card es una venta como cualquier otra: entra plata al
    negocio hoy. Antes solo se guardaba la tarjeta, así que esa plata no
    generaba movimiento: el arqueo del día cerraba con una diferencia sin
    explicación y, como al canjearla el turno queda cubierto, la venta no
    aparecía nunca en la facturación.

    `metodo_pago_id` es opcional a propósito: una gift card también puede ser
    un regalo del negocio (sorteo, compensación por un problema), y ahí no hay
    nada que cobrar.
    """
    from app.services.finanzas import caja_abierta

    metodo = None
    if datos.metodo_pago_id is not None:
        metodo = db.get(MetodoPago, datos.metodo_pago_id)
        if metodo is None or metodo.empresa_id != empresa_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Método de pago inválido"
            )

    gc = GiftCard(
        empresa_id=empresa_id,
        codigo=_codigo_unico(db, empresa_id),
        monto=datos.monto,
        beneficiario=datos.beneficiario,
        de_parte_de=datos.de_parte_de,
        mensaje=datos.mensaje,
        concepto=datos.concepto,
        vence=datos.vence,
        estado=EstadoGiftCard.ACTIVA,
        metodo_pago_id=datos.metodo_pago_id,
    )
    db.add(gc)
    db.flush()  # necesitamos gc.codigo/id para el concepto del movimiento

    if metodo is not None:
        # Mismo criterio que el cobro de un turno: si hay caja abierta se
        # asocia, y si no, el movimiento igual queda registrado.
        caja = caja_abierta(db, empresa_id)
        mov = MovimientoFinanciero(
            empresa_id=empresa_id,
            caja_id=caja.id if caja else None,
            tipo=TipoMovimiento.INGRESO,
            concepto=f"Venta gift card {gc.codigo}",
            monto=datos.monto,
            metodo_pago_id=datos.metodo_pago_id,
            usuario_id=usuario_id,
        )
        db.add(mov)
        db.flush()
        gc.movimiento_id = mov.id

        # El movimiento hace que la venta entre a la CAJA. El Pago hace que
        # entre a ESTADÍSTICAS, que lee de la tabla pago y no de los
        # movimientos. Sin esto, el mismo día cerraba con dos números
        # distintos —la caja con la gift card, la facturación sin ella— y no
        # había nada a la vista que explicara la diferencia.
        # cliente_id va en None: el beneficiario de una gift card es un texto,
        # no una ficha de cliente.
        comision = round(
            float(datos.monto) * float(metodo.comision_pct or 0) / 100, 2
        )
        db.add(
            Pago(
                empresa_id=empresa_id,
                turno_id=None,
                cliente_id=None,
                metodo_pago_id=datos.metodo_pago_id,
                monto=datos.monto,
                comision_aplicada=comision,
                movimiento_id=mov.id,
                origen="giftcard",
            )
        )

    db.commit()
    db.refresh(gc)
    return gc


def listar(db: Session, empresa_id: int) -> list[GiftCard]:
    """Todas las gift cards de la empresa, las más nuevas primero."""
    return list(
        db.scalars(
            select(GiftCard)
            .where(GiftCard.empresa_id == empresa_id)
            .order_by(GiftCard.creada_en.desc(), GiftCard.id.desc())
        )
    )


def _buscar(db: Session, empresa_id: int, codigo: str) -> GiftCard | None:
    """Busca por código normalizado (sin espacios, mayúsculas) dentro de la empresa."""
    codigo = codigo.strip().upper()
    return db.scalar(
        select(GiftCard).where(
            GiftCard.empresa_id == empresa_id,
            func.upper(GiftCard.codigo) == codigo,
        )
    )


def verificar(db: Session, empresa_id: int, codigo: str) -> dict:
    """Consulta sin canjear: ¿esta gift card es válida? Devuelve motivo si no."""
    gc = _buscar(db, empresa_id, codigo)
    if gc is None:
        return {"valida": False, "motivo": "no existe", "gift_card": None}
    if gc.estado == EstadoGiftCard.CANJEADA:
        return {"valida": False, "motivo": "ya canjeada", "gift_card": gc}
    if gc.estado == EstadoGiftCard.VENCIDA or gc.esta_vencida:
        return {"valida": False, "motivo": "vencida", "gift_card": gc}
    return {"valida": True, "motivo": None, "gift_card": gc}


def canjear(db: Session, empresa_id: int, codigo: str, usuario: str | None) -> dict:
    """Canjea la gift card (una sola vez). Devuelve el mismo formato que verificar."""
    gc = _buscar(db, empresa_id, codigo)
    if gc is None:
        return {"valida": False, "motivo": "no existe", "gift_card": None}
    if gc.estado == EstadoGiftCard.CANJEADA:
        return {"valida": False, "motivo": "ya canjeada", "gift_card": gc}
    if gc.estado == EstadoGiftCard.VENCIDA or gc.esta_vencida:
        # Si venció sin canjearse, dejamos el estado consistente.
        if gc.estado != EstadoGiftCard.VENCIDA:
            gc.estado = EstadoGiftCard.VENCIDA
            db.commit()
        return {"valida": False, "motivo": "vencida", "gift_card": gc}

    gc.estado = EstadoGiftCard.CANJEADA
    gc.canjeada_en = dt.datetime.now(dt.timezone.utc)
    gc.canjeada_por = (usuario or "")[:120] or None
    db.commit()
    db.refresh(gc)
    return {"valida": True, "motivo": None, "gift_card": gc}


def eliminar(db: Session, empresa_id: int, gift_id: int) -> bool:
    gc = db.scalar(
        select(GiftCard).where(
            GiftCard.id == gift_id, GiftCard.empresa_id == empresa_id
        )
    )
    if gc is None:
        return False
    db.delete(gc)
    db.commit()
    return True
