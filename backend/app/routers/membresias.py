"""Endpoints de membresías / abonos (E11).

Dos recursos:
- /planes-abono : el molde que define el dueño (CRUD)
- /membresias   : asignar/cancelar membresías a clientes + ver la activa
"""

from fastapi import APIRouter, status

from app.api.deps import DB, EmpresaActual
from app.schemas.membresia import (
    PlanAbonoCrear,
    PlanAbonoEditar,
    PlanAbonoOut,
    MembresiaCrear,
    MembresiaOut,
)
from app.services import membresia as svc

router = APIRouter(tags=["membresias"])


# ===== PLANES DE ABONO =====

@router.get("/planes-abono", response_model=list[PlanAbonoOut])
def listar_planes(empresa_id: EmpresaActual, db: DB) -> list[PlanAbonoOut]:
    return svc.listar_planes(db, empresa_id)


@router.post("/planes-abono", response_model=PlanAbonoOut, status_code=status.HTTP_201_CREATED)
def crear_plan(datos: PlanAbonoCrear, empresa_id: EmpresaActual, db: DB) -> PlanAbonoOut:
    return svc.crear_plan(db, empresa_id, datos)


@router.patch("/planes-abono/{plan_id}", response_model=PlanAbonoOut)
def editar_plan(
    plan_id: int, datos: PlanAbonoEditar, empresa_id: EmpresaActual, db: DB
) -> PlanAbonoOut:
    return svc.editar_plan(db, empresa_id, plan_id, datos)


@router.delete("/planes-abono/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_plan(plan_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    svc.borrar_plan(db, empresa_id, plan_id)


# ===== MEMBRESÍAS =====

# OJO: esta ruta va ANTES de las que usan /membresias/{id} para que
# FastAPI no confunda "estadisticas" con un id de membresía.
@router.get("/membresias/estadisticas")
def estadisticas(empresa_id: EmpresaActual, db: DB) -> dict:
    """Estadísticas de rentabilidad de los planes de abono."""
    return svc.estadisticas_planes(db, empresa_id)


@router.post("/membresias", response_model=MembresiaOut, status_code=status.HTTP_201_CREATED)
def crear_membresia(datos: MembresiaCrear, empresa_id: EmpresaActual, db: DB) -> MembresiaOut:
    membresia = svc.crear_membresia(db, empresa_id, datos)
    return svc.resolver_salida(membresia)


@router.get("/clientes/{cliente_id}/membresia", response_model=MembresiaOut | None)
def membresia_del_cliente(
    cliente_id: int, empresa_id: EmpresaActual, db: DB
) -> MembresiaOut | None:
    """Devuelve la membresía VIGENTE del cliente, o null si no tiene."""
    membresia = svc.membresia_activa_de(db, empresa_id, cliente_id)
    if not membresia:
        return None
    return svc.resolver_salida(membresia)


@router.delete("/membresias/{membresia_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_membresia(membresia_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    svc.cancelar_membresia(db, empresa_id, membresia_id)