"""Lógica de los ítems adicionales de un turno (E10).

Regla 1: todo filtra por empresa_id. Antes de tocar ítems, se valida que el
turno pertenezca a ESTA empresa (no se cargan adicionales a un turno ajeno).
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ItemTurno, Turno
from app.schemas.items import ItemCrear


def _turno_de_empresa(db: Session, empresa_id: int, turno_id: int) -> Turno | None:
    return db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )


def _exigir_editable(db: Session, turno: Turno) -> None:
    """Un turno cobrado no cambia de precio: el turno diría un total y la
    caja otro. Primero se anula el cobro."""
    if turno.cobrado:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El turno ya está cobrado. Para cambiar los adicionales, anulá el cobro primero.",
        )


def listar_items(db: Session, empresa_id: int, turno_id: int) -> list[ItemTurno] | None:
    """Ítems de un turno. None si el turno no es de esta empresa."""
    if _turno_de_empresa(db, empresa_id, turno_id) is None:
        return None
    return list(
        db.scalars(
            select(ItemTurno)
            .where(ItemTurno.turno_id == turno_id, ItemTurno.empresa_id == empresa_id)
            .order_by(ItemTurno.creado_en)
        )
    )


def crear_item(
    db: Session, empresa_id: int, turno_id: int, datos: ItemCrear
) -> ItemTurno | None:
    """Agrega un ítem a un turno. None si el turno no es de esta empresa."""
    turno = _turno_de_empresa(db, empresa_id, turno_id)
    if turno is None:
        return None
    _exigir_editable(db, turno)
    item = ItemTurno(empresa_id=empresa_id, turno_id=turno_id, **datos.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def borrar_item(db: Session, empresa_id: int, turno_id: int, item_id: int) -> bool:
    """Quita un ítem del turno. False si no existe o no es de esta empresa."""
    item = db.scalar(
        select(ItemTurno).where(
            ItemTurno.id == item_id,
            ItemTurno.turno_id == turno_id,
            ItemTurno.empresa_id == empresa_id,
        )
    )
    if item is None:
        return False
    turno = _turno_de_empresa(db, empresa_id, turno_id)
    _exigir_editable(db, turno)
    db.delete(item)
    db.flush()
    # Sacar un adicional no puede dejar el total por debajo de lo ya pagado.
    from app.services.finanzas import total_y_pagado

    total, pagado = total_y_pagado(db, turno)
    if total + 0.009 < pagado:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Sin ese adicional el total (${total:,.2f}) queda por debajo de lo ya pagado (${pagado:,.2f}).",
        )
    db.commit()
    return True