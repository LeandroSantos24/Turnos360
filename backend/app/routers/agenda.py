"""Endpoints de horarios y excepciones de agenda (E2).

Horarios anidados bajo el recurso (/recursos/{id}/horarios).
Excepciones en ruta propia (/excepciones) porque pueden ser de toda la empresa.
"""

import datetime as dt

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DB, EmpresaActual
from app.schemas.agenda import (
    ExcepcionCrear,
    ExcepcionOut,
    HorarioCrear,
    HorarioOut,
)
from app.services import agenda as svc

# Router 1: horarios anidados bajo recursos
horarios_router = APIRouter(prefix="/recursos/{recurso_id}/horarios", tags=["agenda"])


@horarios_router.get("", response_model=list[HorarioOut])
def listar_horarios(recurso_id: int, empresa_id: EmpresaActual, db: DB) -> list[HorarioOut]:
    """Lista las franjas horarias de un recurso. 404 si el recurso no es de esta empresa."""
    horarios = svc.listar_horarios(db, empresa_id, recurso_id)
    if horarios is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return horarios


@horarios_router.post("", response_model=HorarioOut, status_code=status.HTTP_201_CREATED)
def agregar_horario(
    recurso_id: int, datos: HorarioCrear, empresa_id: EmpresaActual, db: DB
) -> HorarioOut:
    """Agrega una franja horaria a un recurso."""
    horario = svc.agregar_horario(db, empresa_id, recurso_id, datos)
    if horario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return horario


@horarios_router.delete("/{horario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_horario(
    recurso_id: int, horario_id: int, empresa_id: EmpresaActual, db: DB
) -> None:
    """Elimina una franja horaria."""
    if not svc.eliminar_horario(db, empresa_id, horario_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado")


# Router 2: excepciones (pueden ser de toda la empresa)
excepciones_router = APIRouter(prefix="/excepciones", tags=["agenda"])


@excepciones_router.get("", response_model=list[ExcepcionOut])
def listar_excepciones(
    empresa_id: EmpresaActual,
    db: DB,
    desde: dt.date | None = Query(default=None, description="Solo las vigentes desde esta fecha"),
) -> list[ExcepcionOut]:
    """Lista las excepciones de la empresa (de todos los recursos + las generales)."""
    return svc.listar_excepciones(db, empresa_id, desde=desde)


@excepciones_router.post("", response_model=ExcepcionOut, status_code=status.HTTP_201_CREATED)
def agregar_excepcion(
    datos: ExcepcionCrear, empresa_id: EmpresaActual, db: DB
) -> ExcepcionOut:
    """Agrega un bloqueo. recurso_id NULL = toda la empresa (feriado)."""
    excepcion = svc.agregar_excepcion(db, empresa_id, datos)
    if excepcion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El recurso indicado no pertenece a esta empresa",
        )
    return excepcion


@excepciones_router.delete("/{excepcion_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_excepcion(excepcion_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    """Elimina una excepción."""
    if not svc.eliminar_excepcion(db, empresa_id, excepcion_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excepción no encontrada")