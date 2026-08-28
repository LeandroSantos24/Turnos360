"""Lógica de finanzas (E10): métodos de pago, cobros, caja, gastos.

Regla 1: todo filtra por empresa_id. Los cobros y gastos generan
MovimientoFinanciero (el libro mayor) y, si hay una caja abierta, se asocian
a ella para poder cerrarla con cifras reales.
"""

import datetime as dt

from fastapi import HTTPException, status
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
                MovimientoFinanciero.anulado.is_(False),
            )
        )
        return float(v or 0)

    cantidad = db.scalar(
        select(func.count(MovimientoFinanciero.id)).where(
            MovimientoFinanciero.empresa_id == empresa_id,
            MovimientoFinanciero.caja_id == caja_id,
            MovimientoFinanciero.anulado.is_(False),
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
            MovimientoFinanciero.anulado.is_(False),
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
            MovimientoFinanciero.anulado.is_(False),
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
                MovimientoFinanciero.anulado.is_(False),
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

    # Idempotencia. El flag `cobrado` se escribía y no se leía nunca, así
    # que un reintento (red que corta, dos pestañas, el proxy que devuelve
    # timeout mientras el backend sí procesó) dejaba DOS movimientos y DOS
    # pagos por la misma atención. La caja cerraba con el doble, y el
    # duplicado no se puede anular desde la app: anular_movimiento rechaza
    # los movimientos con pago asociado. La única salida era entrar a psql.
    if turno.cobrado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este turno ya fue cobrado.",
        )

    caja = caja_abierta(db, empresa_id)
    caja_id = caja.id if caja else None

    # Los métodos de pago se traen de una sola vez, no uno por línea. En un
    # pago dividido (mitad efectivo, mitad transferencia) eran dos consultas;
    # ahora es una, y sirve igual para cualquier cantidad de líneas.
    ids_metodos = {
        linea.metodo_pago_id for linea in datos.pagos if linea.metodo_pago_id is not None
    }
    metodos: dict[int, MetodoPago] = {}
    if ids_metodos:
        metodos = {
            m.id: m
            for m in db.scalars(
                select(MetodoPago).where(
                    MetodoPago.id.in_(ids_metodos),
                    MetodoPago.empresa_id == empresa_id,
                )
            )
        }

    pagos_creados: list[Pago] = []
    total_cobrado = 0.0
    total_comision = 0.0

    # Un id que no resolvió es de otra empresa (o no existe). Antes se
    # guardaba igual: quedaba un pago apuntando a un método ajeno y con
    # comisión 0, lo que además permitía maquillar el neto del arqueo.
    faltantes = ids_metodos - set(metodos)
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alguno de los métodos de pago no existe en este negocio.",
        )

    for linea in datos.pagos:
        metodo = metodos.get(linea.metodo_pago_id) if linea.metodo_pago_id else None
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
            origen="turno",
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

    # Regla 1: los ids vienen del body, así que hay que verificar que sean
    # de ESTA empresa. Sin esto se podía apuntar a un método de otro tenant
    # (el listado devolvía su nombre) y de paso esquivar la comisión.
    if datos.metodo_pago_id is not None:
        existe = db.scalar(
            select(MetodoPago.id).where(
                MetodoPago.id == datos.metodo_pago_id,
                MetodoPago.empresa_id == empresa_id,
            )
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ese método de pago no existe en este negocio.",
            )
    if datos.categoria_id is not None:
        existe = db.scalar(
            select(CategoriaFinanciera.id).where(
                CategoriaFinanciera.id == datos.categoria_id,
                CategoriaFinanciera.empresa_id == empresa_id,
            )
        )
        if existe is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esa categoría no existe en este negocio.",
            )

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


def _resolver_metodos(
    db: Session, movs: list[MovimientoFinanciero], empresa_id: int | None = None
) -> None:
    """Adjunta el nombre del método de pago a cada movimiento (para mostrarlo).

    Filtra por empresa: sin eso, un id de otro tenant devolvía el nombre de
    ESE tenant, y se podían enumerar los métodos de pago de todo el sistema.
    """
    ids = {m.metodo_pago_id for m in movs if m.metodo_pago_id}
    if not ids:
        return
    if empresa_id is None and movs:
        empresa_id = movs[0].empresa_id
    condiciones = [MetodoPago.id.in_(ids)]
    if empresa_id is not None:
        condiciones.append(MetodoPago.empresa_id == empresa_id)
    nombres = dict(
        db.execute(select(MetodoPago.id, MetodoPago.nombre).where(*condiciones)).all()
    )
    for m in movs:
        m.metodo_pago = nombres.get(m.metodo_pago_id)


def listar_movimientos(
    db: Session,
    empresa_id: int,
    tipo: TipoMovimiento | None = None,
    *,
    offset: int = 0,
    limite: int = 30,
) -> tuple[int, list[MovimientoFinanciero]]:
    """Devuelve (total, página) de movimientos, del más nuevo al más viejo.

    Antes traía TODOS los movimientos de la empresa desde el principio de los
    tiempos. Es la tabla que más rápido crece del sistema: un cobro por turno
    más los gastos. Una barbería con 20 turnos por día llega a ~7.000 filas en
    el primer año, y las devolvía todas en cada carga de la pantalla de caja,
    resolviendo además el método de pago de cada una.

    El orden es por fecha descendente y desempata por id: sin el desempate,
    dos movimientos con la misma fecha pueden cambiar de orden entre página y
    página, y en un listado paginado eso significa filas duplicadas o
    salteadas.
    """
    condiciones = [MovimientoFinanciero.empresa_id == empresa_id]
    if tipo is not None:
        condiciones.append(MovimientoFinanciero.tipo == tipo)

    total = db.scalar(
        select(func.count(MovimientoFinanciero.id)).where(*condiciones)
    ) or 0

    movs = list(
        db.scalars(
            select(MovimientoFinanciero)
            .where(*condiciones)
            .order_by(
                MovimientoFinanciero.fecha.desc(),
                MovimientoFinanciero.id.desc(),
            )
            .offset(offset)
            .limit(limite)
        )
    )
    _resolver_metodos(db, movs)
    return int(total), movs


def anular_movimiento(
    db: Session,
    empresa_id: int,
    movimiento_id: int,
    usuario_id: int,
    motivo: str | None,
) -> MovimientoFinanciero:
    """Anula un movimiento: queda registrado pero deja de sumar a los totales.

    NO se borra a propósito. Borrarlo hacía imposible auditar una diferencia
    de arqueo, porque no quedaba rastro de que el movimiento hubiera existido.

    Dos cosas que NO se pueden anular por acá, y el motivo:

    1. Un movimiento con un Pago asociado (el cobro de un turno). Anularlo
       dejaría el turno cobrado pero la plata fuera de la caja: dos fuentes de
       verdad en desacuerdo. Esos se revierten reabriendo el turno, que es el
       flujo que ya existe y que sí ajusta las dos puntas.
    2. Un movimiento de una caja YA CERRADA. El arqueo de ese día quedó
       firmado con una diferencia contada a mano; cambiarle los números
       después convierte un cierre auditado en uno que no cuadra con nada.
    """
    mov = db.get(MovimientoFinanciero, movimiento_id)
    if mov is None or mov.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimiento no encontrado")

    if mov.anulado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese movimiento ya está anulado")

    pago = db.scalar(
        select(Pago).where(
            Pago.movimiento_id == mov.id, Pago.empresa_id == empresa_id
        )
    )
    # Solo se frena si el pago es el cobro de un TURNO. La condición anterior
    # era "existe un pago", y eso dejaba sin salida a las ventas de gift card:
    # su movimiento siempre tiene un pago asociado y no tienen ningún turno que
    # reabrir, así que no había manera de revertirlas desde la aplicación.
    if pago is not None and pago.turno_id is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este movimiento es el cobro de un turno. Para revertirlo, reabrí "
            "el turno desde la agenda: así se ajustan el turno y la caja juntos.",
        )

    if mov.caja_id is not None:
        caja = db.get(Caja, mov.caja_id)
        if caja is not None and caja.estado == EstadoCaja.CERRADA:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La caja de ese día ya está cerrada. Cargá un movimiento de "
                "ajuste en la caja actual en vez de tocar un arqueo firmado.",
            )

    ahora = dt.datetime.now(dt.timezone.utc)
    mov.anulado = True
    mov.anulado_en = ahora
    mov.anulado_por_id = usuario_id
    mov.motivo_anulacion = (motivo or "").strip()[:200] or None

    # Si el movimiento tenía un pago (venta de gift card o de abono), el pago
    # se anula con él. Si no, la caja bajaría pero Estadísticas seguiría
    # facturando el mismo importe: dos números distintos para el mismo día.
    if pago is not None and not pago.anulado:
        pago.anulado = True
        pago.anulado_en = ahora
        pago.anulado_por_id = usuario_id
        pago.motivo_anulacion = mov.motivo_anulacion

    db.commit()
    db.refresh(mov)
    return mov


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

# ============================================================
# Señas de reserva (Mercado Pago)
# ============================================================

METODO_MP = "Mercado Pago"


def _metodo_mercado_pago(db: Session, empresa_id: int) -> MetodoPago:
    """Devuelve (o crea) el método de pago con el que se acreditan las señas.

    La seña entra SIEMPRE por Mercado Pago: es la única pasarela integrada.
    Se busca por nombre y, si el negocio todavía no lo tiene cargado, se crea
    solo. Sin esto, el primer negocio que active señas sin haber pasado por
    Finanzas → Métodos vería el cobro rebotar, y perder el registro de una
    seña ya cobrada es peor que crear un método de más.

    La comisión arranca en 0: la que MP retiene depende del plazo de
    acreditación que eligió cada negocio, y adivinarla daría un neto falso.
    El dueño la ajusta en Finanzas → Métodos y desde ahí se aplica sola.
    """
    metodo = db.scalar(
        select(MetodoPago).where(
            MetodoPago.empresa_id == empresa_id,
            func.lower(MetodoPago.nombre) == METODO_MP.lower(),
        )
    )
    if metodo is None:
        metodo = MetodoPago(empresa_id=empresa_id, nombre=METODO_MP, comision_pct=0)
        db.add(metodo)
        db.flush()
    return metodo


def registrar_sena_cobrada(
    db: Session, turno: Turno, monto: float, mp_payment_id: str | None = None
) -> Pago | None:
    """Mete en caja y en estadísticas una seña que el cliente ya pagó.

    Antes el webhook de Mercado Pago solo marcaba `sena_estado = "pagada"` y
    confirmaba el turno. La plata estaba de verdad en la cuenta de MP del
    negocio, pero para el sistema no existía: no entraba a la caja, no salía
    en el arqueo ni en la facturación.

    Se registra el día en que MP acreditó el pago, NO el día del turno. El
    cliente reserva el martes y se atiende el sábado: la plata entró el
    martes, y la caja tiene que decir lo que pasó cuando pasó. Si algún día
    se prefiere lo contrario (que impacte el día de la atención, para que el
    arqueo diario sea más fácil de leer), el cambio es la fecha del
    movimiento — nada más.

    Devuelve None si la seña ya estaba registrada: MP reintenta la misma
    notificación varias veces y no puede sumar plata dos veces.
    """
    if monto <= 0:
        return None

    # Idempotencia real: aunque el webhook ya corta por mp_payment_id, esta
    # función se protege sola. Un reintento que llegue por otro camino no
    # puede duplicar el ingreso.
    ya = db.scalar(
        select(Pago).where(
            Pago.turno_id == turno.id,
            Pago.origen == "sena",
        )
    )
    if ya is not None:
        return None

    metodo = _metodo_mercado_pago(db, turno.empresa_id)
    caja = caja_abierta(db, turno.empresa_id)
    comision = round(monto * float(metodo.comision_pct or 0) / 100, 2)

    mov = MovimientoFinanciero(
        empresa_id=turno.empresa_id,
        caja_id=caja.id if caja else None,
        tipo=TipoMovimiento.INGRESO,
        concepto="Seña de reserva",
        descripcion=(
            f"Turno #{turno.id}"
            + (f" · pago MP {mp_payment_id}" if mp_payment_id else "")
        ),
        monto=monto,
        metodo_pago_id=metodo.id,
        usuario_id=None,  # lo cobró el cliente solo, no un usuario del panel
    )
    db.add(mov)
    db.flush()

    pago = Pago(
        empresa_id=turno.empresa_id,
        turno_id=turno.id,
        cliente_id=turno.cliente_id,
        metodo_pago_id=metodo.id,
        monto=monto,
        comision_aplicada=comision,
        movimiento_id=mov.id,
        origen="sena",
    )
    db.add(pago)
    db.flush()
    return pago


def senado_de(db: Session, turno_id: int) -> float:
    """Cuánto se cobró ya por adelantado de este turno."""
    return float(
        db.scalar(
            select(func.coalesce(func.sum(Pago.monto), 0)).where(
                Pago.turno_id == turno_id, Pago.origen == "sena"
            )
        )
        or 0
    )
