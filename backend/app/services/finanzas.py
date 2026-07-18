"""Lógica de finanzas (E10): métodos de pago, cobros, caja, gastos.

Regla 1: todo filtra por empresa_id. Los cobros y gastos generan
MovimientoFinanciero (el libro mayor) y, si hay una caja abierta, se asocian
a ella para poder cerrarla con cifras reales.
"""

import datetime as dt

from sqlalchemy import or_ as sa_or, func, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoCaja, TipoMovimiento
from app.models.finanzas import (
    Caja,
    CategoriaFinanciera,
    MetodoPago,
    MovimientoFinanciero,
    Pago,
)
from app.models.turno import Turno
from app.schemas.finanzas import (
    CajaAbrir,
    CajaCerrar,
    CategoriaCrear,
    CobroCrear,
    GastoCrear,
    MetodoPagoCrear,
    MetodoPagoEditar,
)


# ─────────────────────────── Métodos de pago ────────────────────────────────

def listar_metodos(db: Session, empresa_id: int) -> list[MetodoPago]:
    return list(
        db.scalars(
            select(MetodoPago)
            .where(MetodoPago.empresa_id == empresa_id)
            .order_by(MetodoPago.nombre)
        )
    )


def crear_metodo(db: Session, empresa_id: int, datos: MetodoPagoCrear) -> MetodoPago:
    m = MetodoPago(empresa_id=empresa_id, **datos.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def editar_metodo(
    db: Session, empresa_id: int, metodo_id: int, datos: MetodoPagoEditar
) -> MetodoPago | None:
    m = db.scalar(
        select(MetodoPago).where(
            MetodoPago.id == metodo_id, MetodoPago.empresa_id == empresa_id
        )
    )
    if m is None:
        return None
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(m, campo, valor)
    db.commit()
    db.refresh(m)
    return m


def borrar_metodo(db: Session, empresa_id: int, metodo_id: int) -> bool:
    m = db.scalar(
        select(MetodoPago).where(
            MetodoPago.id == metodo_id, MetodoPago.empresa_id == empresa_id
        )
    )
    if m is None:
        return False
    db.delete(m)
    db.commit()
    return True


# ─────────────────────────── Categorías ─────────────────────────────────────

def listar_categorias(db: Session, empresa_id: int) -> list[CategoriaFinanciera]:
    return list(
        db.scalars(
            select(CategoriaFinanciera)
            .where(CategoriaFinanciera.empresa_id == empresa_id)
            .order_by(CategoriaFinanciera.nombre)
        )
    )


def crear_categoria(
    db: Session, empresa_id: int, datos: CategoriaCrear
) -> CategoriaFinanciera:
    c = CategoriaFinanciera(empresa_id=empresa_id, **datos.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ─────────────────────────── Caja ───────────────────────────────────────────

def caja_abierta(db: Session, empresa_id: int) -> Caja | None:
    return db.scalar(
        select(Caja).where(
            Caja.empresa_id == empresa_id, Caja.estado == EstadoCaja.ABIERTA
        )
    )


def abrir_caja(
    db: Session, empresa_id: int, datos: CajaAbrir, usuario_id: int
) -> Caja | None:
    """Abre una caja. None si ya hay una abierta (el router responde 409)."""
    if caja_abierta(db, empresa_id) is not None:
        return None
    c = Caja(
        empresa_id=empresa_id,
        saldo_inicial=datos.saldo_inicial,
        abierta_por=usuario_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _totales_caja(
    db: Session, empresa_id: int, caja_id: int
) -> tuple[float, float, int]:
    def _suma(tipo: TipoMovimiento) -> float:
        v = db.scalar(
            select(func.coalesce(func.sum(MovimientoFinanciero.monto), 0)).where(
                MovimientoFinanciero.empresa_id == empresa_id,
                MovimientoFinanciero.caja_id == caja_id,
                MovimientoFinanciero.tipo == tipo,
            )
        )
        return float(v or 0)

    cantidad = db.scalar(
        select(func.count(MovimientoFinanciero.id)).where(
            MovimientoFinanciero.empresa_id == empresa_id,
            MovimientoFinanciero.caja_id == caja_id,
        )
    )
    return _suma(TipoMovimiento.INGRESO), _suma(TipoMovimiento.EGRESO), int(cantidad or 0)


def resumen_caja(db: Session, empresa_id: int, caja: Caja) -> dict:
    ingresos, egresos, cantidad = _totales_caja(db, empresa_id, caja.id)
    esperado = float(caja.saldo_inicial) + ingresos - egresos
    real = float(caja.saldo_final) if caja.saldo_final is not None else None

    # Por método: cantidad de cobros, bruto, comisión (ya guardada en cada
    # movimiento al cobrar) y neto. El arqueo responde dos preguntas: dónde
    # está la plata y cuánto se come cada método.
    # La comisión vive en Pago (1 a 1 con su movimiento vía movimiento_id).
    filas_metodo = db.execute(
        select(
            MetodoPago.nombre,
            func.count(MovimientoFinanciero.id),
            func.coalesce(func.sum(MovimientoFinanciero.monto), 0),
            func.coalesce(func.sum(Pago.comision_aplicada), 0),
        )
        .select_from(MovimientoFinanciero)
        .join(Pago, Pago.movimiento_id == MovimientoFinanciero.id, isouter=True)
        .join(
            MetodoPago,
            MovimientoFinanciero.metodo_pago_id == MetodoPago.id,
            isouter=True,
        )
        .where(
            MovimientoFinanciero.empresa_id == empresa_id,
            MovimientoFinanciero.caja_id == caja.id,
            MovimientoFinanciero.tipo == TipoMovimiento.INGRESO,
        )
        .group_by(MetodoPago.nombre)
        .order_by(func.sum(MovimientoFinanciero.monto).desc())
    ).all()
    por_metodo = [
        {
            "metodo": nombre or "Sin método",
            "cantidad": int(cant),
            "total": float(bruto),
            "comision": float(comision),
            "neto": round(float(bruto) - float(comision), 2),
        }
        for nombre, cant, bruto, comision in filas_metodo
    ]
    total_comisiones = round(sum(m["comision"] for m in por_metodo), 2)

    # Gastos por método: sin comisión. En un egreso pagamos el monto completo;
    # la comisión solo existe cuando cobramos, no cuando gastamos.
    filas_egreso = db.execute(
        select(
            MetodoPago.nombre,
            func.count(MovimientoFinanciero.id),
            func.coalesce(func.sum(MovimientoFinanciero.monto), 0),
        )
        .select_from(MovimientoFinanciero)
        .join(
            MetodoPago,
            MovimientoFinanciero.metodo_pago_id == MetodoPago.id,
            isouter=True,
        )
        .where(
            MovimientoFinanciero.empresa_id == empresa_id,
            MovimientoFinanciero.caja_id == caja.id,
            MovimientoFinanciero.tipo == TipoMovimiento.EGRESO,
        )
        .group_by(MetodoPago.nombre)
        .order_by(func.sum(MovimientoFinanciero.monto).desc())
    ).all()
    egresos_por_metodo = [
        {
            "metodo": nombre or "Sin método",
            "cantidad": int(cant),
            "total": float(monto),
        }
        for nombre, cant, monto in filas_egreso
    ]

    # Efectivo esperado en el cajón: saldo inicial + entradas en efectivo −
    # salidas en efectivo. "Efectivo" = el método llamado así, más los
    # movimientos sin método (los gastos de caja chica suelen cargarse sin
    # método y salen de los billetes).
    def _suma_efectivo(tipo: TipoMovimiento) -> float:
        v = db.scalar(
            select(func.coalesce(func.sum(MovimientoFinanciero.monto), 0))
            .select_from(MovimientoFinanciero)
            .join(
                MetodoPago,
                MovimientoFinanciero.metodo_pago_id == MetodoPago.id,
                isouter=True,
            )
            .where(
                MovimientoFinanciero.empresa_id == empresa_id,
                MovimientoFinanciero.caja_id == caja.id,
                MovimientoFinanciero.tipo == tipo,
                sa_or(
                    func.lower(MetodoPago.nombre) == "efectivo",
                    MovimientoFinanciero.metodo_pago_id.is_(None),
                ),
            )
        )
        return float(v or 0)

    efectivo_esperado = round(
        float(caja.saldo_inicial)
        + _suma_efectivo(TipoMovimiento.INGRESO)
        - _suma_efectivo(TipoMovimiento.EGRESO),
        2,
    )

    return {
        "caja": caja,
        "total_ingresos": ingresos,
        "total_egresos": egresos,
        "saldo_esperado": esperado,
        "saldo_real": real,
        # El arqueo cuadra el CAJÓN: lo contado vs el efectivo esperado.
        # (Las transferencias y tarjetas no están en el cajón.)
        "diferencia": (real - efectivo_esperado) if real is not None else None,
        "cantidad_movimientos": cantidad,
        "por_metodo": por_metodo,
        "egresos_por_metodo": egresos_por_metodo,
        "total_comisiones": total_comisiones,
        "total_neto": round(ingresos - total_comisiones, 2),
        "efectivo_esperado": efectivo_esperado,
    }


def cerrar_caja(
    db: Session, empresa_id: int, datos: CajaCerrar, usuario_id: int
) -> dict | None:
    """Cierra la caja abierta y devuelve el resumen con la diferencia."""
    caja = caja_abierta(db, empresa_id)
    if caja is None:
        return None
    caja.estado = EstadoCaja.CERRADA
    caja.saldo_final = datos.saldo_real
    caja.fecha_cierre = dt.datetime.now(dt.timezone.utc)
    caja.cerrada_por = usuario_id
    db.commit()
    db.refresh(caja)
    return resumen_caja(db, empresa_id, caja)


# ─────────────────────────── Cobro de un turno ──────────────────────────────

def registrar_cobro(
    db: Session, empresa_id: int, turno_id: int, datos: CobroCrear, usuario_id: int
) -> dict | None:
    """Registra el cobro de un turno (una o varias líneas = pago dividido).

    Por cada línea: calcula la comisión del método, crea el movimiento de
    ingreso y el pago. Si hay caja abierta, asocia los movimientos a ella.
    """
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None

    caja = caja_abierta(db, empresa_id)
    caja_id = caja.id if caja else None

    pagos_creados: list[Pago] = []
    total_cobrado = 0.0
    total_comision = 0.0

    for linea in datos.pagos:
        metodo = None
        if linea.metodo_pago_id is not None:
            metodo = db.scalar(
                select(MetodoPago).where(
                    MetodoPago.id == linea.metodo_pago_id,
                    MetodoPago.empresa_id == empresa_id,
                )
            )
        comision = 0.0
        if metodo and metodo.comision_pct:
            comision = round(linea.monto * float(metodo.comision_pct) / 100, 2)

        mov = MovimientoFinanciero(
            empresa_id=empresa_id,
            caja_id=caja_id,
            tipo=TipoMovimiento.INGRESO,
            concepto="Cobro de turno",
            monto=linea.monto,
            metodo_pago_id=linea.metodo_pago_id,
            usuario_id=usuario_id,
        )
        db.add(mov)
        db.flush()  # necesitamos mov.id para enlazar el pago

        pago = Pago(
            empresa_id=empresa_id,
            turno_id=turno_id,
            cliente_id=turno.cliente_id,
            metodo_pago_id=linea.metodo_pago_id,
            monto=linea.monto,
            comision_aplicada=comision,
            movimiento_id=mov.id,
        )
        db.add(pago)
        pagos_creados.append(pago)
        total_cobrado += float(linea.monto)
        total_comision += comision

    turno.cobrado = True
    db.commit()
    for p in pagos_creados:
        db.refresh(p)

    return {
        "turno_id": turno_id,
        "total_cobrado": round(total_cobrado, 2),
        "total_comision": round(total_comision, 2),
        "neto": round(total_cobrado - total_comision, 2),
        "pagos": pagos_creados,
    }


def pagos_de_turno(db: Session, empresa_id: int, turno_id: int) -> list[Pago]:
    return list(
        db.scalars(
            select(Pago)
            .where(Pago.empresa_id == empresa_id, Pago.turno_id == turno_id)
            .order_by(Pago.fecha)
        )
    )


# ─────────────────────────── Gastos / movimientos ───────────────────────────

def registrar_gasto(
    db: Session, empresa_id: int, datos: GastoCrear, usuario_id: int
) -> MovimientoFinanciero:
    caja = caja_abierta(db, empresa_id)
    mov = MovimientoFinanciero(
        empresa_id=empresa_id,
        caja_id=caja.id if caja else None,
        tipo=TipoMovimiento.EGRESO,
        concepto=datos.concepto,
        descripcion=datos.descripcion,
        monto=datos.monto,
        metodo_pago_id=datos.metodo_pago_id,
        categoria_id=datos.categoria_id,
        usuario_id=usuario_id,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


def _resolver_metodos(db: Session, movs: list[MovimientoFinanciero]) -> None:
    """Adjunta el nombre del método de pago a cada movimiento (para mostrarlo)."""
    ids = {m.metodo_pago_id for m in movs if m.metodo_pago_id}
    if not ids:
        return
    nombres = dict(
        db.execute(
            select(MetodoPago.id, MetodoPago.nombre).where(MetodoPago.id.in_(ids))
        ).all()
    )
    for m in movs:
        m.metodo_pago = nombres.get(m.metodo_pago_id)


def listar_movimientos(
    db: Session, empresa_id: int, tipo: TipoMovimiento | None = None
) -> list[MovimientoFinanciero]:
    q = select(MovimientoFinanciero).where(
        MovimientoFinanciero.empresa_id == empresa_id
    )
    if tipo is not None:
        q = q.where(MovimientoFinanciero.tipo == tipo)
    movs = list(db.scalars(q.order_by(MovimientoFinanciero.fecha.desc())))
    _resolver_metodos(db, movs)
    return movs


# ─────────────────────────── Historial comercial ───────────────────────────

def total_cobrado_cliente(db: Session, empresa_id: int, cliente_id: int) -> dict:
    """Suma de lo realmente cobrado a un cliente (todos sus pagos)."""
    total = db.scalar(
        select(func.coalesce(func.sum(Pago.monto), 0)).where(
            Pago.empresa_id == empresa_id, Pago.cliente_id == cliente_id
        )
    )
    cantidad = db.scalar(
        select(func.count(Pago.id)).where(
            Pago.empresa_id == empresa_id, Pago.cliente_id == cliente_id
        )
    )
    return {"total_cobrado": float(total or 0), "cantidad_pagos": int(cantidad or 0)}


def listar_cajas(db: Session, empresa_id: int, limit: int = 60) -> list[Caja]:
    """Historial de cajas (abiertas y cerradas), de la más reciente a la más vieja."""
    return list(
        db.scalars(
            select(Caja)
            .where(Caja.empresa_id == empresa_id)
            .order_by(Caja.fecha_apertura.desc())
            .limit(limit)
        )
    )


def detalle_caja(db: Session, empresa_id: int, caja_id: int) -> dict | None:
    """Resumen + movimientos de una caja puntual (para imprimir su cierre)."""
    caja = db.scalar(
        select(Caja).where(Caja.id == caja_id, Caja.empresa_id == empresa_id)
    )
    if caja is None:
        return None
    movimientos = list(
        db.scalars(
            select(MovimientoFinanciero)
            .where(
                MovimientoFinanciero.empresa_id == empresa_id,
                MovimientoFinanciero.caja_id == caja_id,
            )
            .order_by(MovimientoFinanciero.fecha)
        )
    )
    _resolver_metodos(db, movimientos)
    return {"resumen": resumen_caja(db, empresa_id, caja), "movimientos": movimientos}