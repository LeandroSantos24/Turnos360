"""CRUD de cupones de descuento (solo el dueño)."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.cupon import CuponCrear, CuponEditar, CuponOut
from app.services import cupones as svc

router = APIRouter(
    prefix="/cupones", tags=["cupones"], dependencies=[Depends(gate_dueno)]
)


@router.get("", response_model=list[CuponOut])
def listar(empresa_id: EmpresaActual, db: DB) -> list[CuponOut]:
    return [CuponOut.model_validate(c) for c in svc.listar_cupones(db, empresa_id)]


@router.post("", response_model=CuponOut, status_code=201)
def crear(datos: CuponCrear, empresa_id: EmpresaActual, db: DB) -> CuponOut:
    cupon = svc.crear_cupon(db, empresa_id, datos)
    if cupon is None:
        raise HTTPException(status_code=409, detail="Ya existe un cupón con ese código")
    return CuponOut.model_validate(cupon)


@router.put("/{cupon_id}", response_model=CuponOut)
def editar(cupon_id: int, datos: CuponEditar, empresa_id: EmpresaActual, db: DB) -> CuponOut:
    cupon = svc.editar_cupon(db, empresa_id, cupon_id, datos)
    if cupon is None:
        raise HTTPException(
            status_code=404, detail="Cupón inexistente o código repetido"
        )
    return CuponOut.model_validate(cupon)


@router.delete("/{cupon_id}", status_code=204)
def borrar(cupon_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    if not svc.borrar_cupon(db, empresa_id, cupon_id):
        raise HTTPException(status_code=404, detail="Cupón inexistente")
