"""Lógica de membresías / abonos (E11).

La función clave es `membresia_activa_de`: dado un cliente, devuelve su
membresía vigente (si tiene una). 'Vigente' = estado ACTIVA y hoy dentro
del rango fecha_desde..fecha_hasta.
"""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Cliente, Turno
from app.models.modulos.fidelizacion import PlanAbono, Membresia
from app.models.enums import EstadoMembresia, EstadoTurno


# ===== PLANES =====

def crear_plan(db: Session, empresa_id: int, datos) -> PlanAbono:
    plan = PlanAbono(empresa_id=empresa_id, **datos.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def listar_planes(db: Session, empresa_id: int) -> list[PlanAbono]:
    return list(
        db.scalars(
            select(PlanAbono).where(
                PlanAbono.empresa_id == empresa_id,
                PlanAbono.activo == True,  # noqa: E712
            )
        )
    )


def editar_plan(db: Session, empresa_id: int, plan_id: int, datos) -> PlanAbono:
    plan = db.get(PlanAbono, plan_id)
    if not plan or plan.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(plan, campo, valor)
    db.commit()
    db.refresh(plan)
    return plan


def borrar_plan(db: Session, empresa_id: int, plan_id: int) -> None:
    plan = db.get(PlanAbono, plan_id)
    if not plan or plan.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")
    plan.activo = False  # baja lógica
    db.commit()


# ===== MEMBRESÍAS =====

def membresia_activa_de(db: Session, empresa_id: int, cliente_id: int) -> Membresia | None:
    """Devuelve la membresía VIGENTE del cliente, o None si no tiene.

    Vigente = estado ACTIVA y hoy dentro del rango de fechas.
    """
    hoy = dt.date.today()
    return db.scalar(
        select(Membresia).where(
            Membresia.empresa_id == empresa_id,
            Membresia.cliente_id == cliente_id,
            Membresia.estado == EstadoMembresia.ACTIVA,
            Membresia.fecha_desde <= hoy,
            Membresia.fecha_hasta >= hoy,
        )
    )


def crear_membresia(db: Session, empresa_id: int, datos) -> Membresia:
    """Crea una membresía para un cliente. Valida que el cliente y el plan existan,
    y que el cliente no tenga ya una membresía activa (regla: una a la vez)."""
    cliente = db.get(Cliente, datos.cliente_id)
    if not cliente or cliente.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")

    plan = db.get(PlanAbono, datos.plan_id)
    if not plan or plan.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")

    # Regla: una membresía activa a la vez
    existente = membresia_activa_de(db, empresa_id, datos.cliente_id)
    if existente:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El cliente ya tiene una membresía activa",
        )

    membresia = Membresia(
        empresa_id=empresa_id,
        cliente_id=datos.cliente_id,
        plan_id=datos.plan_id,
        fecha_desde=datos.fecha_desde,
        fecha_hasta=datos.fecha_hasta,
        estado=EstadoMembresia.ACTIVA,
    )
    db.add(membresia)
    db.commit()
    db.refresh(membresia)
    return membresia


def cancelar_membresia(db: Session, empresa_id: int, membresia_id: int) -> None:
    membresia = db.get(Membresia, membresia_id)
    if not membresia or membresia.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membresía no encontrada")
    membresia.estado = EstadoMembresia.VENCIDA
    db.commit()


def resolver_salida(membresia: Membresia) -> dict:
    """Arma el dict de salida con los datos del plan resueltos y si está vigente."""
    hoy = dt.date.today()
    vigente = (
        membresia.estado == EstadoMembresia.ACTIVA
        and membresia.fecha_desde <= hoy <= membresia.fecha_hasta
    )
    return {
        "id": membresia.id,
        "empresa_id": membresia.empresa_id,
        "cliente_id": membresia.cliente_id,
        "plan_id": membresia.plan_id,
        "fecha_desde": membresia.fecha_desde,
        "fecha_hasta": membresia.fecha_hasta,
        "estado": membresia.estado,
        "cupos_usados": membresia.cupos_usados,
        "plan_nombre": membresia.plan.nombre if membresia.plan else None,
        "plan_precio": float(membresia.plan.precio) if membresia.plan else None,
        "plan_ilimitado": membresia.plan.ilimitado if membresia.plan else None,
        "vigente": vigente,
    }

def estadisticas_planes(db: Session, empresa_id: int) -> dict:
    """Calcula la rentabilidad de cada plan de abono y un resumen general.

    Por cada plan: abonados activos, cortes finalizados cubiertos por ese abono,
    ingreso (precio × abonados) y precio efectivo por corte (ingreso ÷ cortes).
    El "precio efectivo" es la métrica clave: cuánto te queda por corte realmente.
    """
    hoy = dt.date.today()
    planes = listar_planes(db, empresa_id)

    # Membresías activas (vigentes hoy) con su plan
    membresias_activas = list(
        db.scalars(
            select(Membresia).where(
                Membresia.empresa_id == empresa_id,
                Membresia.estado == EstadoMembresia.ACTIVA,
                Membresia.fecha_desde <= hoy,
                Membresia.fecha_hasta >= hoy,
            )
        )
    )

    # Contar abonados activos por plan
    abonados_por_plan: dict[int, int] = {}
    cliente_ids_por_plan: dict[int, list[int]] = {}
    for m in membresias_activas:
        abonados_por_plan[m.plan_id] = abonados_por_plan.get(m.plan_id, 0) + 1
        cliente_ids_por_plan.setdefault(m.plan_id, []).append(m.cliente_id)

    detalle = []
    total_abonados = 0
    total_ingreso = 0.0
    total_cortes = 0

    for plan in planes:
        abonados = abonados_por_plan.get(plan.id, 0)
        clientes_del_plan = cliente_ids_por_plan.get(plan.id, [])

        # Cortes finalizados cubiertos por abono, de los clientes de este plan
        cortes = 0
        if clientes_del_plan:
            cortes = (
                db.scalar(
                    select(func.count(Turno.id)).where(
                        Turno.empresa_id == empresa_id,
                        Turno.cliente_id.in_(clientes_del_plan),
                        Turno.cubierto_por_abono == True,  # noqa: E712
                        Turno.estado == EstadoTurno.FINALIZADO,
                    )
                )
                or 0
            )

        ingreso = float(plan.precio) * abonados
        precio_efectivo = (ingreso / cortes) if cortes > 0 else None

        detalle.append({
            "plan_id": plan.id,
            "nombre": plan.nombre,
            "precio": float(plan.precio),
            "abonados_activos": abonados,
            "cortes_realizados": cortes,
            "ingreso": ingreso,
            "precio_efectivo_por_corte": precio_efectivo,
        })

        total_abonados += abonados
        total_ingreso += ingreso
        total_cortes += cortes

    return {
        "planes": detalle,
        "resumen": {
            "total_abonados": total_abonados,
            "total_ingreso": total_ingreso,
            "total_cortes": total_cortes,
            "precio_efectivo_promedio": (
                total_ingreso / total_cortes if total_cortes > 0 else None
            ),
        },
    }