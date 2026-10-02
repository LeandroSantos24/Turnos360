"""Cálculo de estadísticas de facturación sobre los pagos reales."""

import datetime as dt

from sqlalchemy import and_ as sa_and, case as sa_case, func, or_ as sa_or, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Recurso, Sucursal
from app.models.agenda import Servicio
from app.models.cupon import CuponDescuento
from app.models.enums import EstadoTurno
from app.models.finanzas import MetodoPago, Pago
from app.services.finanzas import ORIGEN_USO_GIFT
from app.models.turno import Turno


def facturacion(
    db: Session,
    empresa_id: int,
    desde: dt.datetime,
    hasta: dt.datetime,
    recurso_id: int | None = None,
    sucursal_id: int | None = None,
) -> dict:
    """Resumen de lo cobrado en el rango: totales, por método, por profesional y por día.

    Si recurso_id viene, TODO el panel se filtra a ese profesional: sus pagos,
    sus servicios, sus horarios y su ausentismo.

    Si sucursal_id viene, lo mismo pero por local. Y venga o no, el resultado
    incluye `por_sucursal`: la comparación entre locales, que es la pregunta
    que se hace un dueño con dos sucursales y la razón por la que paga el plan
    Multi. Con un solo local la lista trae una fila y el panel no la muestra.
    """
    # Los pagos anulados (una gift card emitida por error, una venta
    # revertida) NO facturan. Va en `cond`, que comparten facturación,
    # comisiones, cantidad, por método, por día y por origen: agregarlo acá
    # arregla las seis de una.
    cond = [
        Pago.empresa_id == empresa_id,
        Pago.fecha >= desde,
        Pago.fecha < hasta,
        Pago.anulado.is_(False),
    ]
    # El local es una columna del propio pago (paso 5): filtrar acá no cuesta
    # un join, y alcanza con esta línea para que TODO el panel —totales, por
    # método, por día, por servicio, cupones— quede acotado al local.
    if sucursal_id is not None:
        cond.append(Pago.sucursal_id == sucursal_id)
    # Los pagos no tienen recurso directo: se filtran por el turno del recurso.
    if recurso_id is not None:
        cond.append(
            Pago.turno_id.in_(
                select(Turno.id).where(
                    Turno.empresa_id == empresa_id,
                    Turno.recurso_id == recurso_id,
                )
            )
        )
    # `cond` = todo pago vigente del período (incluye uso de gift card).
    # `cond_ingreso` = solo lo que es PLATA QUE ENTRÓ. El uso de una gift card
    # no lo es: la plata entró al venderla y ahí ya se contó. Contarla otra vez
    # era plata fantasma.
    no_es_uso = sa_or(Pago.origen.is_(None), Pago.origen != ORIGEN_USO_GIFT)
    es_uso = Pago.origen == ORIGEN_USO_GIFT
    cond_total = cond
    cond = [*cond_total, no_es_uso]

    facturado = float(
        db.scalar(select(func.coalesce(func.sum(Pago.monto), 0)).where(*cond)) or 0
    )
    comision = float(
        db.scalar(
            select(func.coalesce(func.sum(Pago.comision_aplicada), 0)).where(*cond)
        )
        or 0
    )
    cantidad = int(db.scalar(select(func.count(Pago.id)).where(*cond)) or 0)

    # Período anterior (mismo lapso justo antes de 'desde'), para la variación %.
    lapso = hasta - desde
    ant_desde = desde - lapso
    cond_ant = [
        Pago.empresa_id == empresa_id,
        Pago.fecha >= ant_desde,
        Pago.fecha < desde,
        Pago.anulado.is_(False),
        no_es_uso,
    ]
    if sucursal_id is not None:
        cond_ant.append(Pago.sucursal_id == sucursal_id)
    if recurso_id is not None:
        cond_ant.append(
            Pago.turno_id.in_(
                select(Turno.id).where(
                    Turno.empresa_id == empresa_id,
                    Turno.recurso_id == recurso_id,
                )
            )
        )
    facturado_anterior = float(
        db.scalar(select(func.coalesce(func.sum(Pago.monto), 0)).where(*cond_ant)) or 0
    )
    if facturado_anterior > 0:
        variacion_pct = round((facturado - facturado_anterior) / facturado_anterior * 100, 1)
    else:
        variacion_pct = None  # sin base de comparación

    # Por método de pago
    filas_m = db.execute(
        select(MetodoPago.nombre, func.coalesce(func.sum(Pago.monto), 0))
        .select_from(Pago)
        .join(MetodoPago, Pago.metodo_pago_id == MetodoPago.id, isouter=True)
        .where(*cond)
        .group_by(MetodoPago.nombre)
        .order_by(func.coalesce(func.sum(Pago.monto), 0).desc())
    ).all()
    por_metodo = [
        {"metodo": n or "Sin método", "total": float(t)} for n, t in filas_m
    ]

    # Por profesional (el pago se une al turno para saber qué barbero atendió).
    # Se separa la plata cobrada del uso de gift card: las dos son trabajo del
    # profesional (comisiones), solo la primera es facturación.
    monto_ingreso = func.coalesce(func.sum(sa_case((no_es_uso, Pago.monto), else_=0)), 0)
    monto_prepago = func.coalesce(func.sum(sa_case((es_uso, Pago.monto), else_=0)), 0)
    filas_p = db.execute(
        select(
            Recurso.nombre,
            monto_ingreso,
            func.count(func.distinct(Turno.id)),
            monto_prepago,
        )
        .select_from(Pago)
        .join(Turno, Pago.turno_id == Turno.id)
        .join(Recurso, Turno.recurso_id == Recurso.id)
        .where(*cond_total)
        .group_by(Recurso.nombre)
        .order_by(monto_ingreso.desc())
    ).all()
    por_profesional = [
        {"recurso": n, "total": float(t), "turnos": int(c), "prepago": float(pp)}
        for n, t, c, pp in filas_p
    ]

    # Evolución diaria, en el DÍA DEL NEGOCIO. `date(fecha)` sale en la zona
    # de la base (UTC en producción): un cobro de las 23:30 de Mendoza caía
    # en el gráfico del día siguiente.
    dia_local = func.date(func.timezone(settings.zona_horaria, Pago.fecha))
    filas_d = db.execute(
        select(dia_local, func.coalesce(func.sum(Pago.monto), 0))
        .where(*cond)
        .group_by(dia_local)
        .order_by(dia_local)
    ).all()
    por_dia = [{"fecha": str(f), "total": float(t)} for f, t in filas_d]

    # ── Turnos por estado (ausentismo) ─ sobre la agenda, no sobre pagos ──
    # Miramos los turnos del período por su fecha de inicio, y contamos cómo
    # terminaron. La tasa de ausentismo = ausentes / (finalizados + ausentes).
    cond_turno = [
        Turno.empresa_id == empresa_id,
        Turno.fecha_inicio >= desde,
        Turno.fecha_inicio < hasta,
    ]
    if recurso_id is not None:
        cond_turno.append(Turno.recurso_id == recurso_id)
    if sucursal_id is not None:
        cond_turno.append(Turno.sucursal_id == sucursal_id)
    filas_estado = db.execute(
        select(Turno.estado, func.count(Turno.id))
        .where(*cond_turno)
        .group_by(Turno.estado)
    ).all()
    conteo = {str(e.value if hasattr(e, "value") else e): int(c) for e, c in filas_estado}
    finalizados = conteo.get("finalizado", 0)
    cancelados = conteo.get("cancelado", 0)
    ausentes = conteo.get("ausente", 0)
    base_asistencia = finalizados + ausentes
    tasa_ausentismo = round(ausentes / base_asistencia * 100, 1) if base_asistencia else 0.0
    estados = {
        "finalizados": finalizados,
        "cancelados": cancelados,
        "ausentes": ausentes,
        "tasa_ausentismo": tasa_ausentismo,
    }

    # ── Servicios: plata del período (pagos) + demanda (finalizados) ──
    # Antes la plata salía de turnos FINALIZADOS por fecha de turno, y la
    # facturación de pagos por fecha de pago: una seña del mes anterior o un
    # turno cobrado sin finalizar hacían que «Servicios» no sumara lo mismo
    # que la facturación. Ahora la plata sale de los mismos pagos que el total
    # (Σ servicios == facturado_turnos) y la cantidad sigue siendo demanda.
    filas_serv_plata = db.execute(
        select(Servicio.nombre, monto_ingreso, monto_prepago)
        .select_from(Pago)
        .join(Turno, Pago.turno_id == Turno.id)
        .join(Servicio, Turno.servicio_id == Servicio.id, isouter=True)
        .where(*cond_total)
        .group_by(Servicio.nombre)
    ).all()
    filas_serv_cant = db.execute(
        select(Servicio.nombre, func.count(Turno.id))
        .select_from(Turno)
        .join(Servicio, Turno.servicio_id == Servicio.id)
        .where(*cond_turno, Turno.estado == EstadoTurno.FINALIZADO)
        .group_by(Servicio.nombre)
    ).all()
    servicios: dict[str, dict] = {}
    for n, t, pp in filas_serv_plata:
        n = n or "Sin servicio"
        servicios[n] = {"servicio": n, "cantidad": 0, "total": float(t), "prepago": float(pp)}
    for n, c in filas_serv_cant:
        servicios.setdefault(n, {"servicio": n, "cantidad": 0, "total": 0.0, "prepago": 0.0})
        servicios[n]["cantidad"] = int(c)
    por_servicio = sorted(
        servicios.values(), key=lambda x: (-x["total"], -x["cantidad"], x["servicio"])
    )

    # ── Horarios más demandados (por hora del día) ──
    # Contamos turnos finalizados agrupados por la hora de inicio (0-23).
    filas_hora = db.execute(
        select(
            func.extract("hour", Turno.fecha_inicio),
            func.count(Turno.id),
        )
        .where(
            *cond_turno,
            Turno.estado == EstadoTurno.FINALIZADO,
        )
        .group_by(func.extract("hour", Turno.fecha_inicio))
        .order_by(func.extract("hour", Turno.fecha_inicio))
    ).all()
    por_hora = [
        {"hora": int(h), "cantidad": int(c)} for h, c in filas_hora if h is not None
    ]

    # ── De dónde salió la plata (turnos / abonos / gift cards) ──────────
    # La facturación ya no es solo la atención: vender un abono o una gift
    # card también entra. Mezclarlo todo en un número haría que el ticket
    # promedio mintiera (una venta de abono de $50.000 no es un "ticket").
    # Acá se separa para poder leer las dos cosas.
    # Se agrupa por la columna CRUDA, no por coalesce(origen, "turno").
    # PostgreSQL exige que la expresión del GROUP BY sea idéntica a la del
    # SELECT, y SQLAlchemy le asigna un parámetro distinto a cada una
    # (coalesce_2 en el SELECT, coalesce_5 en el GROUP BY): PG las considera
    # expresiones diferentes y rechaza la consulta entera. SQLite lo acepta,
    # así que este bug solo aparece contra la base real.
    # El nulo (pagos anteriores a la migración) se resuelve abajo, en Python.
    filas_o = db.execute(
        select(
            Pago.origen,
            func.coalesce(func.sum(Pago.monto), 0),
            func.count(Pago.id),
        )
        .where(*cond)
        .group_by(Pago.origen)
    ).all()
    ETIQUETA_ORIGEN = {
        "turno": "Atención (turnos)",
        "sena": "Señas online",
        "abono": "Venta de abonos",
        "giftcard": "Venta de gift cards",
    }
    # Agrupado en Python para unificar NULL con "turno": los pagos anteriores
    # a la migración no tienen origen y son, todos, cobros de turnos.
    acum: dict[str, dict] = {}
    for o, tot, c in filas_o:
        clave = o or "turno"
        fila = acum.setdefault(clave, {"total": 0.0, "cantidad": 0})
        fila["total"] += float(tot)
        fila["cantidad"] += int(c)
    por_origen = [
        {
            "origen": k,
            "etiqueta": ETIQUETA_ORIGEN.get(k, k),
            "total": round(v["total"], 2),
            "cantidad": v["cantidad"],
        }
        for k, v in sorted(acum.items(), key=lambda x: -x[1]["total"])
    ]
    # Lo cobrado por la atención = todo pago atado a un turno (mostrador +
    # seña). Coincide con Σ por_profesional y Σ por_servicio.
    monto_turnos = round(sum(p["total"] for p in por_profesional), 2)
    prepago_consumido = round(
        float(
            db.scalar(
                select(func.coalesce(func.sum(Pago.monto), 0)).where(*cond_total, es_uso)
            )
            or 0
        ),
        2,
    )
    # Ticket = lo que gasta un cliente por visita: por TURNO, no por pago. Con
    # el pago dividido (mitad y mitad) el ticket salía a la mitad.
    cant_turnos = sum(p["turnos"] for p in por_profesional)

    # ── Rendimiento de los cupones de descuento ─────────────────────────
    # Responde la pregunta que decide si una promo sirvió: cuánta gente la
    # usó, cuánto facturaron esos turnos y cuánto se regaló en descuento.
    # Se mira por turnos del período (no por pagos), porque un cupón se
    # consume al reservar y lo que interesa es si esa reserva se concretó.
    pagado_turno = (
        select(
            Pago.turno_id.label("turno_id"),
            func.sum(Pago.monto).label("pagado"),
        )
        .where(Pago.anulado.is_(False), no_es_uso, Pago.empresa_id == empresa_id)
        .group_by(Pago.turno_id)
        .subquery()
    )
    filas_c = db.execute(
        select(
            CuponDescuento.codigo,
            CuponDescuento.tipo,
            CuponDescuento.valor,
            CuponDescuento.activo,
            CuponDescuento.vence_el,
            CuponDescuento.max_usos,
            func.count(Turno.id),
            func.count(func.distinct(Turno.cliente_id)),
            # Facturado = plata REAL cobrada de esos turnos (antes era una
            # estimación importe × (1 − %), aunque nadie lo hubiera cobrado).
            func.coalesce(func.sum(pagado_turno.c.pagado), 0),
            func.coalesce(
                func.sum(
                    func.coalesce(Turno.importe_previsto, 0)
                    * func.coalesce(Turno.descuento_pct, 0)
                    / 100
                    + func.coalesce(Turno.descuento_monto, 0)
                ),
                0,
            ),
            func.sum(
                sa_case((Turno.estado == EstadoTurno.FINALIZADO, 1), else_=0)
            ),
            func.sum(
                sa_case((Turno.estado == EstadoTurno.CANCELADO, 1), else_=0)
            ),
            func.sum(sa_case((Turno.estado == EstadoTurno.AUSENTE, 1), else_=0)),
        )
        .select_from(Turno)
        .join(CuponDescuento, Turno.cupon_id == CuponDescuento.id)
        .join(pagado_turno, pagado_turno.c.turno_id == Turno.id, isouter=True)
        .where(*cond_turno)
        .group_by(
            CuponDescuento.id,
            CuponDescuento.codigo,
            CuponDescuento.tipo,
            CuponDescuento.valor,
            CuponDescuento.activo,
            CuponDescuento.vence_el,
            CuponDescuento.max_usos,
        )
        .order_by(func.count(Turno.id).desc())
    ).all()
    por_cupon = [
        {
            "codigo": codigo,
            "tipo": tipo,
            "valor": float(valor),
            "activo": bool(activo),
            "vence_el": str(vence) if vence else None,
            "max_usos": max_usos,
            "usos": int(usos),
            "personas": int(personas),
            "facturado": round(float(fact), 2),
            "descuento_otorgado": round(float(desc), 2),
            "finalizados": int(fin or 0),
            "cancelados": int(canc or 0),
            "ausentes": int(aus or 0),
            # Lo que de verdad importa: ¿el descuento se convirtió en plata?
            # Turnos que terminaron sobre turnos que usaron el código.
            "tasa_concrecion": (
                round(int(fin or 0) / int(usos) * 100, 1) if usos else 0.0
            ),
        }
        for (
            codigo, tipo, valor, activo, vence, max_usos,
            usos, personas, fact, desc, fin, canc, aus,
        ) in filas_c
    ]
    cupones_resumen = {
        "usos": sum(c["usos"] for c in por_cupon),
        "personas": sum(c["personas"] for c in por_cupon),
        "facturado": round(sum(c["facturado"] for c in por_cupon), 2),
        "descuento_otorgado": round(
            sum(c["descuento_otorgado"] for c in por_cupon), 2
        ),
    }

    # ── Comparación entre locales ───────────────────────────────────────
    # La pregunta de un dueño con dos sucursales: cuál factura más, cuál tiene
    # el ticket más alto, cuál se está quedando atrás. Es lo que hace que el
    # plan Multi tenga sentido para él.
    #
    # A propósito NO se filtra por `sucursal_id`: aunque el dueño esté mirando
    # un local, la comparación tiene que mostrarle los dos. Si se filtrara,
    # elegir un local haría desaparecer aquello con lo que se compara.
    cond_todos = [
        Pago.empresa_id == empresa_id,
        Pago.fecha >= desde,
        Pago.fecha < hasta,
        Pago.anulado.is_(False),
        no_es_uso,
    ]
    filas_suc = db.execute(
        select(
            Sucursal.id,
            Sucursal.nombre,
            func.coalesce(func.sum(Pago.monto), 0),
            func.count(Pago.id),
            func.count(func.distinct(Pago.turno_id)),
        )
        .select_from(Sucursal)
        .join(
            Pago,
            sa_and(Pago.sucursal_id == Sucursal.id, *cond_todos),
            isouter=True,
        )
        .where(Sucursal.empresa_id == empresa_id)
        .group_by(Sucursal.id, Sucursal.nombre)
        .order_by(func.coalesce(func.sum(Pago.monto), 0).desc())
    ).all()
    total_todos = sum(float(t) for _, _, t, _, _ in filas_suc) or 0.0
    por_sucursal = [
        {
            "sucursal_id": sid,
            "sucursal": nombre,
            "total": round(float(total), 2),
            "cantidad_pagos": int(cant),
            "turnos": int(turnos),
            "ticket": round(float(total) / int(turnos), 2) if turnos else 0.0,
            "pct": round(float(total) / total_todos * 100, 1) if total_todos else 0.0,
        }
        for sid, nombre, total, cant, turnos in filas_suc
    ]

    # Ticket promedio: SOLO sobre la atención. Meter la venta de un abono acá
    # inflaría el número y dejaría de servir para lo único que sirve, que es
    # comparar cuánto gasta un cliente por visita.
    ticket = (
        (monto_turnos + sum(p["prepago"] for p in por_profesional)) / cant_turnos
        if cant_turnos
        else 0.0
    )

    return {
        "por_sucursal": por_sucursal,
        "por_origen": por_origen,
        "facturado_turnos": round(monto_turnos, 2),
        "prepago_consumido": prepago_consumido,
        "por_cupon": por_cupon,
        "cupones_resumen": cupones_resumen,
        "facturado_real": facturado,
        "facturado_anterior": facturado_anterior,
        "variacion_pct": variacion_pct,
        "comision_total": comision,
        "neto": facturado - comision,
        "cantidad_pagos": cantidad,
        "ticket_promedio": round(ticket, 2),
        "por_metodo": por_metodo,
        "por_profesional": [
            {
                **p,
                "ticket": round(p["total"] / p["turnos"], 2) if p["turnos"] else 0.0,
                "pct": round(p["total"] / facturado * 100, 1) if facturado else 0.0,
            }
            for p in por_profesional
        ],
        "por_dia": por_dia,
        "estados": estados,
        "por_servicio": por_servicio,
        "por_hora": por_hora,
    }