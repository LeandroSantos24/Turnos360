"""Endpoints de los ítems adicionales de un turno (E10).

Sub-recurso de turno: /turnos/{turno_id}/items. El empresa_id sale del token.

Roles: el adicional al cobrar es operación del mostrador -> dueño + recepción
(gate_gestion). Listar queda abierto. NO es lo mismo que el catálogo de
servicios (eso es config del dueño): acá se suma un ítem suelto a ESA venta.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DB, EmpresaActual, gate_gestion
from app.schemas.items import ItemCrear, ItemOut
from app.services import items as svc

router = APIRouter(prefix="/turnos", tags=["items"])


@router.get("/{turno_id}/items", response_model=list[ItemOut])
def listar_items(turno_id: int, empresa_id: EmpresaActual, db: DB) -> list[ItemOut]:
    """Lista los ítems adicionales de un turno."""
    items = svc.listar_items(db, empresa_id, turno_id)
    if items is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado")
    return items


@router.post(
    "/{turno_id}/items",
    response_model=ItemOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def crear_item(
    turno_id: int, datos: ItemCrear, empresa_id: EmpresaActual, db: DB
) -> ItemOut:
    """Agrega un ítem adicional al turno."""
    item = svc.crear_item(db, empresa_id, turno_id, datos)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado")
    return item


@router.delete(
    "/{turno_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(gate_gestion)],
)
def borrar_item(turno_id: int, item_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    """Quita un ítem del turno."""
    if not svc.borrar_item(db, empresa_id, turno_id, item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ítem no encontrado")
