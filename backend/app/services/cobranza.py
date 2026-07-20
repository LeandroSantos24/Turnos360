"""Cobranza del SaaS: el semáforo de vencimientos y la caja de Turnos360.

Reglas de negocio (definidas por Leandro):
- El ciclo dura 30 días y después hay 10 días de PRÓRROGA antes de considerar
  la cuenta vencida de verdad (DIAS_PRORROGA en services/suscripcion.py).
- El semáforo del listado es para saber A QUIÉN COBRARLE de un vistazo:
    verde    = al día
    amarillo = vence dentro de los próximos DIAS_AVISO días (hay que ir a cobrar)
    rojo     = pasó el vencimiento (dentro o fuera de la prórroga)
    gris     = sin vencimiento (plan gratuito / piloto bonificado)
  El rojo incluye la prórroga a propósito: durante esos 10 días el negocio
  sigue operando, pero para vos ya es "me tiene que pagar".
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Empresa, PagoSuscripcion, Recurso, Usuario
from app.services.suscripcion import DIAS_PRORROGA

# Días de anticipación con los que una empresa entra en amarillo.
DIAS_AVISO = 7
# Duración del ciclo: registrar un pago empuja el vencimiento esta cantidad.
DIAS_CICLO = 30


def semaforo_de(empresa: Empresa, hoy: dt.date | None = None) -> dict:
    """Color, días restantes y estado de cobranza de una empresa."""
    hoy = hoy or dt.date.today()
    vence = empresa.suscripcion_vence

    if vence is None:
        return {
            "color": "gris",
            "dias_restantes": None,
            "fin_prorroga": None,
            "en_prorroga": False,
            "detalle": "Sin vencimiento",
        }

    dias = (vence - hoy).days
    fin_prorroga = vence + dt.timedelta(days=DIAS_PRORROGA)

    if dias < 0:
        en_prorroga = hoy <= fin_prorroga
        if en_prorroga:
            restantes = (fin_prorroga - hoy).days
            detalle = (
                f"Venció hace {abs(dias)} día{'s' if abs(dias) != 1 else ''} · "
                f"{restantes} de gracia"
            )
        else:
            detalle = f"Vencida hace {abs(dias)} días · sin gracia"
        color = "rojo"
    elif dias <= DIAS_AVISO:
        color = "amarillo"
        en_prorroga = False
        detalle = "Vence hoy" if dias == 0 else f"Vence en {dias} día{'s' if dias != 1 else ''}"
    else:
        color = "verde"
        en_prorroga = False
        detalle = f"Al día · {dias} días"

    return {
        "color": color,
        "dias_restantes": dias,
        "fin_prorroga": str(fin_prorroga),
        "en_prorroga": en_prorroga,
        "detalle": detalle,
    }


def listar_empresas(
    db: Session,
    buscar: str | None = None,
    color: str | None = None,
    plan: str | None = None,
    activa: bool | None = None,
) -> list[dict]:
    """Listado del panel con semáforo, uso y datos comerciales.

    Los conteos de usuarios y recursos salen en dos queries agrupadas (no una
    por empresa): con 50 negocios la diferencia entre 3 queries y 101 se nota.
    """
    q = select(Empresa)
    if buscar:
        patron = f"%{buscar.strip().lower()}%"
        q = q.where(
            func.lower(Empresa.nombre).like(patron)
            | func.lower(func.coalesce(Empresa.razon_social, "")).like(patron)
            | func.lower(func.coalesce(Empresa.cuit, "")).like(patron)
            | func.lower(func.coalesce(Empresa.contacto_email, "")).like(patron)
            | func.lower(Empresa.slug).like(patron)
        )
    if plan:
        q = q.where(Empresa.plan == plan)
    if activa is not None:
        q = q.where(Empresa.activa.is_(activa))

    empresas = list(db.scalars(q.order_by(Empresa.nombre)).all())
    if not empresas:
        return []

    ids = [e.id for e in empresas]
    usuarios = dict(
        db.execute(
            select(Usuario.empresa_id, func.count(Usuario.id))
            .where(Usuario.empresa_id.in_(ids), Usuario.activo.is_(True))
            .group_by(Usuario.empresa_id)
        ).all()
    )
    recursos = dict(
        db.execute(
            select(Recurso.empresa_id, func.count(Recurso.id))
            .where(Recurso.empresa_id.in_(ids), Recurso.activo.is_(True))
            .group_by(Recurso.empresa_id)
        ).all()
    )
    ultimo_pago = dict(
        db.execute(
            select(PagoSuscripcion.empresa_id, func.max(PagoSuscripcion.fecha))
            .where(PagoSuscripcion.empresa_id.in_(ids))
            .group_by(PagoSuscripcion.empresa_id)
        ).all()
    )

    filas = []
    for e in empresas:
        sem = semaforo_de(e)
        if color and sem["color"] != color:
            continue
        usados = recursos.get(e.id, 0)
        filas.append(
            {
                "id": e.id,
                "nombre": e.nombre,
                "slug": e.slug,
                "activa": e.activa,
                "plan": e.plan or "gratuito",
                "suscripcion_vence": str(e.suscripcion_vence) if e.suscripcion_vence else None,
                "precio_mensual": float(e.precio_mensual) if e.precio_mensual else None,
                "razon_social": e.razon_social,
                "cuit": e.cuit,
                "contacto_nombre": e.contacto_nombre,
                "contacto_email": e.contacto_email,
                "contacto_telefono": e.contacto_telefono,
                "notas_admin": e.notas_admin,
                "cantidad_usuarios": usuarios.get(e.id, 0),
                "cantidad_recursos": usados,
                "limite_recursos": e.limite_recursos,
                # Aviso de capacidad: el panel lo pinta cuando llegó al tope.
                "capacidad_excedida": (
                    e.limite_recursos is not None and usados >= e.limite_recursos
                ),
                "ultimo_pago": str(ultimo_pago[e.id]) if e.id in ultimo_pago else None,
                **{f"semaforo_{k}": v for k, v in sem.items()},
            }
        )
    return filas


def resumen_cobranza(db: Session, hoy: dt.date | None = None) -> dict:
    """Tarjetas de balance rápido del panel."""
    hoy = hoy or dt.date.today()
    inicio_mes = hoy.replace(day=1)

    cobrado = db.scalar(
        select(func.coalesce(func.sum(PagoSuscripcion.monto), 0)).where(
            PagoSuscripcion.fecha >= inicio_mes, PagoSuscripcion.fecha <= hoy
        )
    ) or Decimal(0)

    por_metodo = [
        {"metodo": m, "total": float(t)}
        for m, t in db.execute(
            select(PagoSuscripcion.metodo, func.sum(PagoSuscripcion.monto))
            .where(PagoSuscripcion.fecha >= inicio_mes, PagoSuscripcion.fecha <= hoy)
            .group_by(PagoSuscripcion.metodo)
            .order_by(func.sum(PagoSuscripcion.monto).desc())
        ).all()
    ]

    # Pendiente estimado: lo que habría que cobrar en los próximos DIAS_AVISO
    # días, según el precio pactado de cada empresa que vence en esa ventana.
    # Las empresas sin precio cargado NO suman (no inventamos plata): se
    # informan aparte para que sepas que el número está incompleto.
    limite = hoy + dt.timedelta(days=DIAS_AVISO)
    por_vencer = list(
        db.scalars(
            select(Empresa).where(
                Empresa.activa.is_(True),
                Empresa.suscripcion_vence.is_not(None),
                Empresa.suscripcion_vence >= hoy,
                Empresa.suscripcion_vence <= limite,
            )
        ).all()
    )
    pendiente = sum(float(e.precio_mensual) for e in por_vencer if e.precio_mensual)
    sin_precio = sum(1 for e in por_vencer if not e.precio_mensual)

    # Vencidas: ya pasaron la fecha (incluye las que están en prórroga).
    vencidas = list(
        db.scalars(
            select(Empresa).where(
                Empresa.activa.is_(True),
                Empresa.suscripcion_vence.is_not(None),
                Empresa.suscripcion_vence < hoy,
            )
        ).all()
    )
    deuda_vencida = sum(float(e.precio_mensual) for e in vencidas if e.precio_mensual)

    # MRR: suma de los precios pactados de las cuentas activas y al día o en
    # prórroga. No incluye las bonificadas (precio None) ni las pausadas.
    mrr = db.scalar(
        select(func.coalesce(func.sum(Empresa.precio_mensual), 0)).where(
            Empresa.activa.is_(True), Empresa.precio_mensual.is_not(None)
        )
    ) or Decimal(0)

    return {
        "cobrado_mes": float(cobrado),
        "por_metodo": por_metodo,
        "pendiente_estimado": pendiente,
        "empresas_por_vencer": len(por_vencer),
        "por_vencer_sin_precio": sin_precio,
        "deuda_vencida": deuda_vencida,
        "empresas_vencidas": len(vencidas),
        "mrr": float(mrr),
        "dias_aviso": DIAS_AVISO,
    }


def registrar_pago(
    db: Session,
    empresa: Empresa,
    monto: float,
    metodo: str,
    fecha: dt.date | None = None,
    notas: str | None = None,
    registrado_por: str | None = None,
    renovar: bool = True,
) -> PagoSuscripcion:
    """Anota una cuota cobrada y (por defecto) empuja el vencimiento 30 días.

    De dónde se cuentan los 30 días:
    - Si paga DENTRO de la prórroga (hasta 10 días tarde), se cuenta desde el
      vencimiento viejo: el negocio nunca dejó de estar cubierto y no pierde
      los días de atraso.
    - Si paga DESPUÉS de la prórroga, se cuenta desde hoy. Estuvo cortado, así
      que no se le regalan las semanas que no pagó.
    """
    fecha = fecha or dt.date.today()
    desde = empresa.suscripcion_vence

    pago = PagoSuscripcion(
        empresa_id=empresa.id,
        fecha=fecha,
        monto=monto,
        metodo=metodo,
        notas=notas,
        registrado_por=registrado_por,
    )

    if renovar:
        limite_continuidad = fecha - dt.timedelta(days=DIAS_PRORROGA)
        base = desde if desde and desde >= limite_continuidad else fecha
        nuevo = base + dt.timedelta(days=DIAS_CICLO)
        pago.periodo_desde = base
        pago.periodo_hasta = nuevo
        empresa.suscripcion_vence = nuevo

    db.add(pago)
    db.flush()
    return pago


def prorrogar(db: Session, empresa: Empresa, dias: int) -> dt.date:
    """Extiende el vencimiento N días (gracia manual o extensión de prueba).

    Si la empresa no tenía fecha, se cuenta desde hoy. Si ya venció, también:
    dar 5 días de gracia a alguien que venció hace un mes significa 5 días
    desde hoy, no desde una fecha vieja.
    """
    hoy = dt.date.today()
    base = empresa.suscripcion_vence
    if base is None or base < hoy:
        base = hoy
    empresa.suscripcion_vence = base + dt.timedelta(days=dias)
    db.flush()
    return empresa.suscripcion_vence


def historial_pagos(db: Session, empresa_id: int, limite: int = 24) -> list[dict]:
    filas = db.scalars(
        select(PagoSuscripcion)
        .where(PagoSuscripcion.empresa_id == empresa_id)
        .order_by(PagoSuscripcion.fecha.desc(), PagoSuscripcion.id.desc())
        .limit(limite)
    ).all()
    return [
        {
            "id": p.id,
            "fecha": str(p.fecha),
            "monto": float(p.monto),
            "metodo": p.metodo,
            "periodo_desde": str(p.periodo_desde) if p.periodo_desde else None,
            "periodo_hasta": str(p.periodo_hasta) if p.periodo_hasta else None,
            "notas": p.notas,
        }
        for p in filas
    ]
