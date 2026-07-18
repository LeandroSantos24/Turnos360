"""Endpoints del pack salud / nutrición (E13).

Toda ruta exige token válido (vía EmpresaActual). El empresa_id sale del token
y se le pasa al service: el usuario nunca elige sobre qué empresa opera (Regla 1).

La ficha es 1:1 con el paciente, así que un solo PUT hace de crear y actualizar.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DB, EmpresaActual
from app.schemas.salud import (
    AdjuntoCrear,
    AdjuntoOut,
    EntradaCrear,
    EntradaOut,
    FichaGuardar,
    FichaOut,
    MedicionCrear,
    MedicionOut,
)
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


# ============================================================
# Evolución: controles / consultas de seguimiento
# ============================================================


@router.get("/{cliente_id}/entradas", response_model=list[EntradaOut])
def listar_entradas(cliente_id: int, empresa_id: EmpresaActual, db: DB) -> list[EntradaOut]:
    """Controles del paciente, del más reciente al más viejo."""
    return svc.listar_entradas(db, empresa_id, cliente_id)


@router.post("/{cliente_id}/entradas", response_model=EntradaOut, status_code=status.HTTP_201_CREATED)
def crear_entrada(
    cliente_id: int, datos: EntradaCrear, empresa_id: EmpresaActual, db: DB
) -> EntradaOut:
    entrada = svc.crear_entrada(db, empresa_id, cliente_id, datos)
    if entrada is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return entrada


@router.delete("/{cliente_id}/entradas/{entrada_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_entrada(
    cliente_id: int, entrada_id: int, empresa_id: EmpresaActual, db: DB
) -> None:
    if not svc.borrar_entrada(db, empresa_id, cliente_id, entrada_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Control no encontrado")


# ============================================================
# Mediciones antropométricas
# ============================================================


@router.get("/{cliente_id}/mediciones", response_model=list[MedicionOut])
def listar_mediciones(cliente_id: int, empresa_id: EmpresaActual, db: DB) -> list[MedicionOut]:
    """Mediciones en orden cronológico (listas para graficar la evolución)."""
    return svc.listar_mediciones(db, empresa_id, cliente_id)


@router.post("/{cliente_id}/mediciones", response_model=MedicionOut, status_code=status.HTTP_201_CREATED)
def crear_medicion(
    cliente_id: int, datos: MedicionCrear, empresa_id: EmpresaActual, db: DB
) -> MedicionOut:
    """Alta de una medición. IMC y sumatoria de pliegues se calculan si no vienen."""
    medicion = svc.crear_medicion(db, empresa_id, cliente_id, datos)
    if medicion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return medicion


@router.delete("/{cliente_id}/mediciones/{medicion_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_medicion(
    cliente_id: int, medicion_id: int, empresa_id: EmpresaActual, db: DB
) -> None:
    if not svc.borrar_medicion(db, empresa_id, cliente_id, medicion_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Medición no encontrada")


# ============================================================
# Adjuntos del paciente (PDF ISAK, estudios, planes) — por URL
# ============================================================


@router.get("/{cliente_id}/adjuntos", response_model=list[AdjuntoOut])
def listar_adjuntos(cliente_id: int, empresa_id: EmpresaActual, db: DB) -> list[AdjuntoOut]:
    return svc.listar_adjuntos(db, empresa_id, cliente_id)


@router.post("/{cliente_id}/adjuntos", response_model=AdjuntoOut, status_code=status.HTTP_201_CREATED)
def crear_adjunto(
    cliente_id: int, datos: AdjuntoCrear, empresa_id: EmpresaActual, db: DB
) -> AdjuntoOut:
    try:
        adjunto = svc.crear_adjunto(db, empresa_id, cliente_id, datos)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    if adjunto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return adjunto


@router.delete("/{cliente_id}/adjuntos/{adjunto_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_adjunto(
    cliente_id: int, adjunto_id: int, empresa_id: EmpresaActual, db: DB
) -> None:
    if not svc.borrar_adjunto(db, empresa_id, cliente_id, adjunto_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Adjunto no encontrado")
