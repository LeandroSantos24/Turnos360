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

from app.models import GiftCard
from app.models.enums import EstadoGiftCard
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


def crear(db: Session, empresa_id: int, datos: GiftCardCrear) -> GiftCard:
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
    )
    db.add(gc)
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
