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
from app.models.finanzas import MetodoPago, MovimientoFinanciero, Pago
from app.models.modulos.fidelizacion import PlanAbono, Membresia
from app.models.enums import EstadoMembresia, EstadoTurno, TipoMovimiento
from app.services.finanzas import caja_abierta, sucursal_de_usuario


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


def crear_membresia(db: Session, empresa_id: int, datos, usuario_id: int | None = None) -> Membresia:
    """Crea la membresía y COBRA la venta del abono.

    Vender un abono es una venta como cualquier otra: entra plata hoy. Antes
    esta función solo guardaba la membresía, así que el pago del cliente no
    generaba movimiento: no entraba a la caja, no salía en el arqueo ni en la
    facturación. Y como después los turnos de ese cliente salen en $0
    (cubierto_por_abono), el abono quedaba como costo visible e ingreso
    invisible: la pantalla de rentabilidad del plan mostraba pérdida donde
    había ganancia.

    El cobro es OPCIONAL (`metodo_pago_id` en None): una membresía también
    puede ser de cortesía —canje, compensación por un problema, prueba a un
    cliente fiel— y ahí no hay nada que cobrar.
    """
    cliente = db.get(Cliente, datos.cliente_id)
    if not cliente or cliente.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")

    plan = db.get(PlanAbono, datos.plan_id)
    if not plan or plan.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan no encontrado")

    if datos.fecha_hasta < datos.fecha_desde:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La fecha de fin no puede ser anterior a la de inicio",
        )

    # Regla: una membresía activa a la vez
    existente = membresia_activa_de(db, empresa_id, datos.cliente_id)
    if existente:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El cliente ya tiene una membresía activa",
        )

    # El método de pago tiene que ser de esta empresa (Regla 1). Se valida
    # ANTES de crear nada: si el dato viene mal, no queremos una membresía
    # creada a medias y sin cobrar.
    metodo_pago_id = getattr(datos, "metodo_pago_id", None)
    metodo = None
    if metodo_pago_id is not None:
        metodo = db.scalar(
            select(MetodoPago).where(
                MetodoPago.id == metodo_pago_id,
                MetodoPago.empresa_id == empresa_id,
            )
        )
        if metodo is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Método de pago no encontrado"
            )

    # Cuánto se cobra: lo que venga explícito, si no el precio del plan.
    monto = getattr(datos, "monto_cobrado", None)
    monto = float(monto) if monto is not None else float(plan.precio or 0)

    membresia = Membresia(
        empresa_id=empresa_id,
        cliente_id=datos.cliente_id,
        plan_id=datos.plan_id,
        fecha_desde=datos.fecha_desde,
        fecha_hasta=datos.fecha_hasta,
        estado=EstadoMembresia.ACTIVA,
        metodo_pago_id=metodo_pago_id,
        monto_cobrado=monto if metodo is not None else None,
    )
    db.add(membresia)
    db.flush()

    if metodo is not None and monto > 0:
        # Mismo criterio que el cobro de un turno y que la gift card: si hay
        # caja abierta se asocia, y si no, el movimiento igual queda registrado.
        # El abono se vende en un mostrador, no en un turno: entra a la caja
        # del local de quien lo carga.
        sucursal_id = sucursal_de_usuario(db, empresa_id, usuario_id)
        caja = caja_abierta(db, empresa_id, sucursal_id)
        comision = round(monto * float(metodo.comision_pct or 0) / 100, 2)

        mov = MovimientoFinanciero(
            empresa_id=empresa_id,
            caja_id=caja.id if caja else None,
            sucursal_id=sucursal_id,
            tipo=TipoMovimiento.INGRESO,
            concepto=f"Venta abono {plan.nombre}",
            descripcion=f"{cliente.nombre} {cliente.apellido or ''}".strip(),
            monto=monto,
            metodo_pago_id=metodo_pago_id,
            usuario_id=usuario_id,
        )
        db.add(mov)
        db.flush()

        # El Pago es lo que hace que la venta aparezca en Estadísticas: el
        # panel de facturación lee de esta tabla, no de los movimientos.
        # turno_id queda en None (no hay turno) y origen="abono" permite
        # separarlo de la facturación de la atención.
        db.add(
            Pago(
                empresa_id=empresa_id,
                sucursal_id=sucursal_id,
                turno_id=None,
                cliente_id=datos.cliente_id,
                metodo_pago_id=metodo_pago_id,
                monto=monto,
                comision_aplicada=comision,
                movimiento_id=mov.id,
                origen="abono",
            )
        )
        membresia.movimiento_id = mov.id

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
        "metodo_pago_id": membresia.metodo_pago_id,
        "monto_cobrado": (
            float(membresia.monto_cobrado)
            if membresia.monto_cobrado is not None
            else None
        ),
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
    # Lo que se COBRÓ de verdad por cada plan, y cuántas de esas membresías
    # fueron de cortesía. Antes el ingreso se estimaba como precio × abonados,
    # que da mal en los dos casos reales: un abono de cortesía sumaba plata
    # que nunca entró, y un descuento de lanzamiento no se veía.
    cobrado_por_plan: dict[int, float] = {}
    cortesias_por_plan: dict[int, int] = {}
    for m in membresias_activas:
        abonados_por_plan[m.plan_id] = abonados_por_plan.get(m.plan_id, 0) + 1
        cliente_ids_por_plan.setdefault(m.plan_id, []).append(m.cliente_id)
        if m.monto_cobrado is not None:
            cobrado_por_plan[m.plan_id] = cobrado_por_plan.get(
                m.plan_id, 0.0
            ) + float(m.monto_cobrado)
        else:
            cortesias_por_plan[m.plan_id] = cortesias_por_plan.get(m.plan_id, 0) + 1

    detalle = []
    total_abonados = 0
    total_ingreso = 0.0
    total_cortes = 0

    # Cortes cubiertos por abono, agrupados por cliente, en UNA consulta.
    # Antes se preguntaba una vez por plan: con diez planes eran diez viajes
    # a la base para armar una sola pantalla.
    todos_los_clientes = {
        cid for ids in cliente_ids_por_plan.values() for cid in ids
    }
    cortes_por_cliente: dict[int, int] = {}
    if todos_los_clientes:
        cortes_por_cliente = {
            cid: int(n)
            for cid, n in db.execute(
                select(Turno.cliente_id, func.count(Turno.id))
                .where(
                    Turno.empresa_id == empresa_id,
                    Turno.cliente_id.in_(todos_los_clientes),
                    Turno.cubierto_por_abono.is_(True),
                    Turno.estado == EstadoTurno.FINALIZADO,
                )
                .group_by(Turno.cliente_id)
            ).all()
        }

    for plan in planes:
        abonados = abonados_por_plan.get(plan.id, 0)
        clientes_del_plan = cliente_ids_por_plan.get(plan.id, [])

        cortes = sum(cortes_por_cliente.get(cid, 0) for cid in clientes_del_plan)

        # Ingreso REAL cobrado por este plan. Las membresías cargadas antes
        # de que el sistema cobrara no tienen monto_cobrado: para esas se cae
        # al precio de lista, que es la mejor estimación disponible.
        cortesias = cortesias_por_plan.get(plan.id, 0)
        cobrado = cobrado_por_plan.get(plan.id, 0.0)
        con_monto = sum(
            1
            for m in membresias_activas
            if m.plan_id == plan.id and m.monto_cobrado is not None
        )
        historicas = max(abonados - cortesias - con_monto, 0)
        ingreso = round(cobrado + float(plan.precio) * historicas, 2)
        precio_efectivo = (ingreso / cortes) if cortes > 0 else None

        detalle.append({
            "plan_id": plan.id,
            "nombre": plan.nombre,
            "precio": float(plan.precio),
            "abonados_activos": abonados,
            "cortes_realizados": cortes,
            "ingreso": ingreso,
            "precio_efectivo_por_corte": precio_efectivo,
            # Cuántos de esos abonados no pagaron: si el plan "no cierra",
            # lo primero a mirar es si la mitad son regalados.
            "cortesias": cortesias,
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