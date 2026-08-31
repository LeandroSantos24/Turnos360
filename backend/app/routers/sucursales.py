"""Sucursales del negocio (E16, paso 2).

Todo el router va con gate_dueno: abrir o cerrar un local es una decisión
comercial, del mismo orden que cambiar de plan.

La pantalla que consume esto solo aparece en el menú cuando el plan permite
más de un local. El endpoint igual responde siempre: un negocio de un solo
local tiene una sucursal real, y el día que pase al plan Multi la ve sin que
haya que migrar nada.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.sucursal import (
    SucursalCrear,
    SucursalEditar,
    SucursalOut,
    SucursalesOut,
)
from app.services import sucursal as svc

router = APIRouter(
    prefix="/sucursales", tags=["sucursales"], dependencies=[Depends(gate_dueno)]
)


@router.get("", response_model=SucursalesOut)
def listar(empresa_id: EmpresaActual, db: DB) -> SucursalesOut:
    """Los locales del negocio, con el cupo que da el plan."""
    return svc.listar(db, empresa_id)


@router.post("", response_model=SucursalOut, status_code=status.HTTP_201_CREATED)
def crear(datos: SucursalCrear, empresa_id: EmpresaActual, db: DB) -> SucursalOut:
    """Abre un local nuevo. 409 con el nombre del plan si no queda cupo."""
    return svc.crear(db, empresa_id, datos)


@router.patch("/{sucursal_id}", response_model=SucursalOut)
def editar(
    sucursal_id: int, datos: SucursalEditar, empresa_id: EmpresaActual, db: DB
) -> SucursalOut:
    """Cambia nombre, dirección, teléfono o si el local sigue abierto.

    No hay DELETE a propósito: un local tiene turnos, caja y arqueos colgando.
    Se cierra (`activa=false`) y su historia queda.
    """
    return svc.editar(db, empresa_id, sucursal_id, datos)
