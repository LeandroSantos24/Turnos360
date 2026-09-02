"""Endpoints de servicios: lo que cada negocio ofrece (E2)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.servicio import (
    ServicioCrear,
    ServicioEditar,
    ServicioOut,
    ServiciosPagina,
)
from app.services import servicio as svc

router = APIRouter(prefix="/servicios", tags=["servicios"])


@router.get("", response_model=ServiciosPagina)
def listar_servicios(
    empresa_id: EmpresaActual, db: DB, solo_activos: bool = Query(default=True)
) -> ServiciosPagina:
    total, items = svc.listar(db, empresa_id, solo_activos=solo_activos)
    # Los locales de TODOS los servicios en una sola consulta, no una por fila.
    mapa = svc.mapa_de_sucursales(db, [s.id for s in items])
    return ServiciosPagina(
        total=total,
        items=[ServicioOut.desde_modelo(s, mapa.get(s.id, [])) for s in items],
    )


@router.get("/{servicio_id}", response_model=ServicioOut)
def obtener_servicio(servicio_id: int, empresa_id: EmpresaActual, db: DB) -> ServicioOut:
    servicio = svc.obtener(db, empresa_id, servicio_id)
    if servicio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado")
    return ServicioOut.desde_modelo(servicio, svc.sucursales_de(db, servicio.id))


# Catálogo = configuración del negocio -> solo el dueño.
@router.post(
    "",
    response_model=ServicioOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_dueno)],
)
def crear_servicio(datos: ServicioCrear, empresa_id: EmpresaActual, db: DB) -> ServicioOut:
    servicio = svc.crear(db, empresa_id, datos)
    return ServicioOut.desde_modelo(servicio, svc.sucursales_de(db, servicio.id))


@router.patch(
    "/{servicio_id}",
    response_model=ServicioOut,
    dependencies=[Depends(gate_dueno)],
)
def editar_servicio(
    servicio_id: int, datos: ServicioEditar, empresa_id: EmpresaActual, db: DB
) -> ServicioOut:
    servicio = svc.editar(db, empresa_id, servicio_id, datos)
    if servicio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado")
    return ServicioOut.desde_modelo(servicio, svc.sucursales_de(db, servicio.id))


@router.delete(
    "/{servicio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(gate_dueno)],
)
def desactivar_servicio(servicio_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    if not svc.desactivar(db, empresa_id, servicio_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado")
