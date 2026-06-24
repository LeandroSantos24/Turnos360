"""Endpoints del pack salud / nutrición (E13).

Toda ruta exige token válido (vía EmpresaActual). El empresa_id sale del token
y se le pasa al service: el usuario nunca elige sobre qué empresa opera (Regla 1).

La ficha es 1:1 con el paciente, así que un solo PUT hace de crear y actualizar.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DB, EmpresaActual
from app.schemas.salud import FichaGuardar, FichaOut
from app.services import salud as svc

router = APIRouter(prefix="/pacientes", tags=["salud"])


@router.get("/{cliente_id}/ficha", response_model=FichaOut)
def obtener_ficha(cliente_id: int, empresa_id: EmpresaActual, db: DB) -> FichaOut:
    """Devuelve la ficha del paciente. 404 si todavía no tiene o es de otra empresa."""
    ficha = svc.obtener_ficha(db, empresa_id, cliente_id)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El paciente no tiene ficha todavía",
        )
    return ficha


@router.put("/{cliente_id}/ficha", response_model=FichaOut)
def guardar_ficha(
    cliente_id: int, datos: FichaGuardar, empresa_id: EmpresaActual, db: DB
) -> FichaOut:
    """Crea o actualiza la ficha del paciente (upsert). 404 si el paciente no es de esta empresa."""
    ficha = svc.guardar_ficha(db, empresa_id, cliente_id, datos)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado",
        )
    return ficha