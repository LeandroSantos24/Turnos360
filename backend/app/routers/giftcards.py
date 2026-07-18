"""Endpoints de gift cards (E11).

- Crear / listar / borrar: dueño + recepción (gate_gestion). Es operación de mostrador.
- Verificar (consulta sin canjear): gate_gestion.
- Canjear (validación única): gate_gestion; registra qué usuario la canjeó.

La genuinidad la garantiza el service (código criptográfico + filtro por
empresa + canje único). Un código de otra empresa devuelve "no existe".
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DB, EmpresaActual, UsuarioActual, gate_gestion
from app.schemas.giftcard import (
    GiftCardCrear,
    GiftCardOut,
    GiftCardVerificacion,
    GiftCardVerificar,
)
from app.services import giftcard as svc

router = APIRouter(prefix="/gift-cards", tags=["gift-cards"])


@router.get("", response_model=list[GiftCardOut], dependencies=[Depends(gate_gestion)])
def listar(empresa_id: EmpresaActual, db: DB) -> list[GiftCardOut]:
    return svc.listar(db, empresa_id)


@router.post(
    "",
    response_model=GiftCardOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def crear(datos: GiftCardCrear, empresa_id: EmpresaActual, db: DB) -> GiftCardOut:
    return svc.crear(db, empresa_id, datos)


@router.post(
    "/verificar",
    response_model=GiftCardVerificacion,
    dependencies=[Depends(gate_gestion)],
)
def verificar(
    datos: GiftCardVerificar, empresa_id: EmpresaActual, db: DB
) -> GiftCardVerificacion:
    """Consulta si un código es válido, SIN canjearlo (para el escáner)."""
    return svc.verificar(db, empresa_id, datos.codigo)


@router.post(
    "/canjear",
    response_model=GiftCardVerificacion,
    dependencies=[Depends(gate_gestion)],
)
def canjear(
    datos: GiftCardVerificar, empresa_id: EmpresaActual, usuario: UsuarioActual, db: DB
) -> GiftCardVerificacion:
    """Canjea el código (una sola vez). El segundo intento devuelve 'ya canjeada'."""
    return svc.canjear(db, empresa_id, datos.codigo, usuario.nombre)


@router.delete(
    "/{gift_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(gate_gestion)],
)
def eliminar(gift_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    if not svc.eliminar(db, empresa_id, gift_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gift card no encontrada")
