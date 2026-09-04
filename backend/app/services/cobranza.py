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

from sqlalchemy import func, or_ as sa_or, select
from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app.core import planes
from app.models import (
    AjusteSuscripcion,
    AvisoPago,
    Empresa,
    PagoSuscripcion,
    Recurso,
    Usuario,
)
from app.services.suscripcion import DIAS_PRORROGA

# Días de anticipación con los que una empresa entra en amarillo.
DIAS_AVISO = 7
# Duración del ciclo: registrar un pago empuja el vencimiento esta cantidad.
DIAS_CICLO = 30


def semaforo_de(empresa: Empresa, hoy: dt.date | None = None) -> dict:
    """Color, días restantes y estado de cobranza de una empresa."""
    hoy = hoy or dt.date.today()
    vence = empresa.suscripcion_vence

    # La prueba se evalúa PRIMERO: un negocio en prueba no debe pintarse de
    # rojo por no tener vencimiento, ni de verde como si estuviera pagando.
    if empresa.prueba_hasta is not None and hoy <= empresa.prueba_hasta:
        restantes = (empresa.prueba_hasta - hoy).days
        return {
            "color": "azul",
            "dias_restantes": restantes,
            "fin_prorroga": None,
            "en_prorroga": False,
            "detalle": (
                "Prueba · último día"
                if restantes == 0
                else f"Prueba · {restantes} día{'s' if restantes != 1 else ''}"
            ),
        }

    if vence is None:
        return {
            "color": "gris",
            "dias_restantes": None,
            "fin_prorroga": None,
            "en_prorroga": False,
            "detalle": (
                "Prueba terminada · sin convertir"
                if empresa.prueba_hasta is not None
                else "Sin vencimiento"
            ),
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
    # Filtro común: un negocio dentro de su período de prueba no debe nada y
    # tampoco es ingreso recurrente. Si contara, el MRR quedaría inflado con
    # plata que todavía no existe y la deuda vencida mostraría morosos falsos.
    no_en_prueba = sa_or(
        Empresa.prueba_hasta.is_(None), Empresa.prueba_hasta < hoy
    )

    limite = hoy + dt.timedelta(days=DIAS_AVISO)
    por_vencer = list(
        db.scalars(
            select(Empresa).where(
                Empresa.activa.is_(True),
                Empresa.suscripcion_vence.is_not(None),
                Empresa.suscripcion_vence >= hoy,
                Empresa.suscripcion_vence <= limite,
                no_en_prueba,
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
                no_en_prueba,
            )
        ).all()
    )
    deuda_vencida = sum(float(e.precio_mensual) for e in vencidas if e.precio_mensual)

    # MRR: suma de los precios pactados de las cuentas activas y al día o en
    # prórroga. No incluye las bonificadas (precio None) ni las pausadas.
    mrr = db.scalar(
        select(func.coalesce(func.sum(Empresa.precio_mensual), 0)).where(
            Empresa.activa.is_(True),
            Empresa.precio_mensual.is_not(None),
            no_en_prueba,
        )
    ) or Decimal(0)

    en_prueba = db.scalar(
        select(func.count(Empresa.id)).where(
            Empresa.activa.is_(True),
            Empresa.prueba_hasta.is_not(None),
            Empresa.prueba_hasta >= hoy,
        )
    )

    return {
        "empresas_en_prueba": int(en_prueba or 0),
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
    plan: str | None = None,
) -> PagoSuscripcion:
    """Anota una cuota cobrada, activa el plan comprado y corre el vencimiento.

    DE DÓNDE SE CUENTAN LOS 30 DÍAS
    ───────────────────────────────
    - Si paga DENTRO de la prórroga (hasta 10 días tarde), se cuenta desde el
      vencimiento viejo: el negocio nunca dejó de estar cubierto y no pierde
      los días de atraso.
    - Si paga DESPUÉS de la prórroga, se cuenta desde hoy. Estuvo cortado, así
      que no se le regalan las semanas que no pagó.
    - Y NUNCA queda con menos días de los que ya tenía. Sin ese piso, alguien
      que pagó ayer y hoy sube a Pro perdería 29 días que ya pagó: cobra el
      plan nuevo completo, sí, pero no puede salir con menos vencimiento del
      que entró.

    `plan` ES LO QUE HACE QUE EL COBRO SEA AUTOMÁTICO
    ─────────────────────────────────────────────────
    Viene del external_reference del pago de Mercado Pago (o lo elige el
    super-admin al registrar una transferencia). Antes no existía: el pago
    entraba, el vencimiento se corría, y el plan quedaba como estaba. Un
    upgrade a Pro cobraba Pro y dejaba al negocio en Inicial hasta que alguien
    lo arreglara a mano — que es exactamente el trabajo manual que este cambio
    viene a sacar.
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
        if plan:
            # Compró un plan concreto: se activa, sea subida o bajada. Y se
            # cancela cualquier baja programada — acaba de decidir de nuevo.
            empresa.plan = plan
            empresa.plan_programado = None
        elif planes.plan_de(empresa.plan) is planes.Plan.GRATUITO:
            # Renovación sin plan elegido (el botón viejo, o una transferencia
            # registrada a mano sin indicar cuál). Quien paga deja de estar en
            # prueba y cae en el plan de ENTRADA, no en el del medio.
            #
            # Antes el plan y el cobro vivían desacoplados: una empresa podía
            # pagar por Mercado Pago durante un año y seguir figurando en
            # "gratuito", con los límites de la prueba.
            empresa.plan = planes.PLAN_DE_ENTRADA.value

        limite_continuidad = fecha - dt.timedelta(days=DIAS_PRORROGA)
        base = desde if desde and desde >= limite_continuidad else fecha
        nuevo = base + dt.timedelta(days=DIAS_CICLO)
        # El piso: nunca menos días de los que ya tenía.
        if desde and desde > nuevo:
            nuevo = desde
        pago.periodo_desde = base
        pago.periodo_hasta = nuevo
        empresa.suscripcion_vence = nuevo

    db.add(pago)
    db.flush()

    registrar_ajuste(
        db,
        empresa,
        tipo="pago",
        vence_antes=desde,
        vence_despues=empresa.suscripcion_vence,
        detalle=(
            f"Cuota de ${float(monto):,.0f} por {metodo}"
            + (f" · pasa a {planes.limites_de(plan).etiqueta}" if plan else "")
        ).replace(",", "."),
        pago_id=pago.id,
        hecho_por=registrado_por,
    )
    return pago


def prorrogar(
    db: Session, empresa: Empresa, dias: int, hecho_por: str | None = None
) -> dt.date:
    """Extiende el vencimiento N días (gracia manual o extensión de prueba).

    Si la empresa no tenía fecha, se cuenta desde hoy. Si ya venció, también:
    dar 5 días de gracia a alguien que venció hace un mes significa 5 días
    desde hoy, no desde una fecha vieja.
    """
    hoy = dt.date.today()
    antes = empresa.suscripcion_vence
    base = antes
    if base is None or base < hoy:
        base = hoy
    empresa.suscripcion_vence = base + dt.timedelta(days=dias)
    db.flush()
    registrar_ajuste(
        db,
        empresa,
        tipo="prorroga",
        vence_antes=antes,
        vence_despues=empresa.suscripcion_vence,
        dias=dias,
        detalle=f"{dias} días de gracia, sin cobrar",
        hecho_por=hecho_por,
    )
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
            # Se muestra anulado en vez de esconderse: una cuota que se anotó
            # y después se dio de baja es justo lo que hay que poder ver.
            "anulado": bool(p.anulado),
            "anulado_por": p.anulado_por,
        }
        for p in filas
    ]


# ══════════════════════════════════════════════════════════════════════════
#  Historial de ajustes: qué le pasó al vencimiento y cómo volver atrás
# ══════════════════════════════════════════════════════════════════════════


def registrar_ajuste(
    db: Session,
    empresa: Empresa,
    *,
    tipo: str,
    vence_antes: dt.date | None,
    vence_despues: dt.date | None,
    dias: int | None = None,
    detalle: str | None = None,
    pago_id: int | None = None,
    hecho_por: str | None = None,
) -> AjusteSuscripcion:
    """Anota que el vencimiento se movió, y desde qué fecha.

    Guardar `vence_antes` es lo que hace posible revertir: volver atrás pasa a
    ser restaurar un dato guardado y no recalcular una fecha que quizá vino de
    una prórroga acumulada sobre otra prórroga.
    """
    aj = AjusteSuscripcion(
        empresa_id=empresa.id,
        tipo=tipo,
        vence_antes=vence_antes,
        vence_despues=vence_despues,
        dias=dias,
        detalle=(detalle or "")[:500] or None,
        pago_id=pago_id,
        hecho_por=(hecho_por or "")[:160] or None,
    )
    db.add(aj)
    db.flush()
    return aj


def listar_ajustes(db: Session, empresa_id: int, limite: int = 40) -> list[dict]:
    filas = db.scalars(
        select(AjusteSuscripcion)
        .where(AjusteSuscripcion.empresa_id == empresa_id)
        .order_by(AjusteSuscripcion.creado_en.desc(), AjusteSuscripcion.id.desc())
        .limit(limite)
    ).all()
    return [
        {
            "id": a.id,
            "tipo": a.tipo,
            "vence_antes": str(a.vence_antes) if a.vence_antes else None,
            "vence_despues": str(a.vence_despues) if a.vence_despues else None,
            "dias": a.dias,
            "detalle": a.detalle,
            "hecho_por": a.hecho_por,
            "creado_en": a.creado_en.isoformat() if a.creado_en else None,
            "revertido": bool(a.revertido),
            "revertido_por": a.revertido_por,
            # Una reversión no se revierte: sería un ping-pong sin sentido.
            # Para volver a mover la fecha están el cobro y la prórroga.
            "reversible": (not a.revertido) and a.tipo != "reversion",
        }
        for a in filas
    ]


def revertir_ajuste(
    db: Session, empresa_id: int, ajuste_id: int, hecho_por: str | None
) -> dict:
    """Deshace un movimiento del vencimiento: lo devuelve a `vence_antes`.

    Es el arreglo para el click equivocado: "renovar 30 días" y "+10 días" son
    botones chicos, al lado de otros, y hasta ahora no había forma de volver
    atrás ni de saber cuál era la fecha anterior.

    Revertir NO borra: marca el ajuste original como revertido y anota un
    ajuste nuevo de tipo "reversion". Así el historial cuenta lo que pasó de
    verdad —se dio y se sacó— en vez de fingir que nunca ocurrió.

    Si el ajuste vino de un pago, ese pago se anula también: si no, quedaría
    una cuota cobrada que no cubre ningún período.
    """
    aj = db.get(AjusteSuscripcion, ajuste_id)
    if aj is None or aj.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese movimiento no existe.")
    if aj.revertido:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ese movimiento ya fue revertido."
        )
    if aj.tipo == "reversion":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se revierte una reversión. Si querés mover el vencimiento de "
            "nuevo, registrá un pago o dale una prórroga.",
        )

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    ahora = dt.datetime.now(dt.timezone.utc)
    desde = empresa.suscripcion_vence
    empresa.suscripcion_vence = aj.vence_antes

    aj.revertido = True
    aj.revertido_en = ahora
    aj.revertido_por = (hecho_por or "")[:160] or None

    if aj.pago_id is not None:
        pago = db.get(PagoSuscripcion, aj.pago_id)
        if pago is not None and not pago.anulado:
            pago.anulado = True
            pago.anulado_en = ahora
            pago.anulado_por = aj.revertido_por

    registrar_ajuste(
        db,
        empresa,
        tipo="reversion",
        vence_antes=desde,
        vence_despues=empresa.suscripcion_vence,
        detalle=f"Se deshizo el movimiento #{aj.id} ({aj.tipo})",
        hecho_por=hecho_por,
    )
    db.commit()
    return {
        "ok": True,
        "vence": str(empresa.suscripcion_vence) if empresa.suscripcion_vence else None,
    }


# ══════════════════════════════════════════════════════════════════════════
#  Avisos de pago: "ya te transferí"
# ══════════════════════════════════════════════════════════════════════════


def registrar_aviso(
    db: Session,
    empresa: Empresa,
    *,
    metodo: str = "transferencia",
    monto: float | None = None,
    referencia: str | None = None,
    avisado_por: str | None = None,
) -> AvisoPago:
    """El dueño avisa que pagó. Todavía no es plata: es un aviso.

    Si ya hay un aviso pendiente de esta empresa se devuelve ese mismo, sin
    crear otro. Un dueño ansioso que aprieta el botón cuatro veces no tiene que
    generarle cuatro pendientes a nadie.
    """
    abierto = db.scalar(
        select(AvisoPago).where(
            AvisoPago.empresa_id == empresa.id,
            AvisoPago.resuelto.is_(False),
        )
    )
    if abierto is not None:
        return abierto

    aviso = AvisoPago(
        empresa_id=empresa.id,
        metodo=metodo,
        monto=monto,
        referencia=(referencia or "").strip()[:300] or None,
        avisado_por=(avisado_por or "")[:160] or None,
    )
    db.add(aviso)
    db.commit()
    db.refresh(aviso)
    return aviso


def aviso_pendiente(db: Session, empresa_id: int) -> AvisoPago | None:
    return db.scalar(
        select(AvisoPago).where(
            AvisoPago.empresa_id == empresa_id, AvisoPago.resuelto.is_(False)
        )
    )


def listar_avisos(db: Session, solo_pendientes: bool = True) -> list[dict]:
    """La bandeja de entrada de Leandro: quién dice que pagó y no está confirmado."""
    q = select(AvisoPago, Empresa.nombre).join(Empresa, AvisoPago.empresa_id == Empresa.id)
    if solo_pendientes:
        q = q.where(AvisoPago.resuelto.is_(False))
    filas = db.execute(q.order_by(AvisoPago.creado_en.desc()).limit(100)).all()
    return [
        {
            "id": a.id,
            "empresa_id": a.empresa_id,
            "empresa_nombre": nombre,
            "metodo": a.metodo,
            "monto": float(a.monto) if a.monto is not None else None,
            "referencia": a.referencia,
            "creado_en": a.creado_en.isoformat() if a.creado_en else None,
            "resuelto": bool(a.resuelto),
        }
        for a, nombre in filas
    ]


def resolver_aviso(
    db: Session, aviso_id: int, *, pago_id: int | None, resuelto_por: str | None
) -> None:
    """Marca el aviso como atendido (se confirmó el pago, o se descartó)."""
    aviso = db.get(AvisoPago, aviso_id)
    if aviso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese aviso no existe.")
    if aviso.resuelto:
        return
    aviso.resuelto = True
    aviso.resuelto_en = dt.datetime.now(dt.timezone.utc)
    aviso.resuelto_por = (resuelto_por or "")[:160] or None
    aviso.pago_id = pago_id
    db.commit()


# ══════════════════════════════════════════════════════════════════════
#  Cambio de plan por autoservicio
# ══════════════════════════════════════════════════════════════════════
#
# La regla, en una línea: SUBIR se paga y se activa al toque; BAJAR se anota
# y se aplica cuando vence el ciclo que ya está pagado.
#
# Por qué no al revés. Una subida que espera al fin del mes es alguien que
# pagó más y no recibe nada hasta dentro de tres semanas — nadie paga así. Una
# bajada inmediata es quitarle algo que ya pagó, y es exactamente el motivo
# por el que alguien pasa de bajar de plan a dar de baja la cuenta.


def cambio_de_plan(empresa: Empresa, destino: str) -> str:
    """Qué tipo de movimiento es: 'sube', 'baja' o 'mismo'.

    Se compara por PRECIO y no por el orden del enum: es la única definición
    que no se rompe el día que se agregue un plan en el medio de la grilla.
    """
    actual = planes.limites_de(empresa.plan).precio
    nuevo = planes.limites_de(destino).precio
    if nuevo > actual:
        return "sube"
    if nuevo < actual:
        return "baja"
    return "mismo"


def programar_baja(
    db: Session, empresa: Empresa, destino: str, hecho_por: str | None = None
) -> dt.date | None:
    """Anota que al vencer el ciclo la empresa cae al plan `destino`.

    No toca el plan actual ni el vencimiento: el mes ya está pagado y se usa
    entero. Devuelve la fecha en que se va a aplicar.

    Si la empresa no tiene vencimiento (está en prueba, o es una cuenta
    bonificada), la baja se aplica ya: no hay ciclo pago que respetar.
    """
    destino = planes.plan_de(destino).value
    if empresa.suscripcion_vence is None:
        antes = empresa.plan
        empresa.plan = destino
        empresa.plan_programado = None
        registrar_ajuste(
            db,
            empresa,
            tipo="plan",
            vence_antes=None,
            vence_despues=None,
            detalle=(
                f"Cambio de plan: {planes.limites_de(antes).etiqueta} → "
                f"{planes.limites_de(destino).etiqueta}"
            ),
            hecho_por=hecho_por,
        )
        db.flush()
        return None

    empresa.plan_programado = destino
    registrar_ajuste(
        db,
        empresa,
        tipo="plan",
        vence_antes=empresa.suscripcion_vence,
        vence_despues=empresa.suscripcion_vence,
        detalle=(
            f"Baja programada a {planes.limites_de(destino).etiqueta} "
            f"para el {empresa.suscripcion_vence.isoformat()}"
        ),
        hecho_por=hecho_por,
    )
    db.flush()
    return empresa.suscripcion_vence


def cancelar_baja_programada(
    db: Session, empresa: Empresa, hecho_por: str | None = None
) -> None:
    """Se arrepintió. Sigue en el plan que tiene."""
    if empresa.plan_programado is None:
        return
    destino = empresa.plan_programado
    empresa.plan_programado = None
    registrar_ajuste(
        db,
        empresa,
        tipo="plan",
        vence_antes=empresa.suscripcion_vence,
        vence_despues=empresa.suscripcion_vence,
        detalle=f"Se canceló la baja a {planes.limites_de(destino).etiqueta}",
        hecho_por=hecho_por,
    )
    db.flush()


def aplicar_bajas_programadas(db: Session, hoy: dt.date | None = None) -> int:
    """Baja de plan a las empresas cuyo ciclo ya venció. Devuelve cuántas.

    Lo corre el barrido diario. Es idempotente: al aplicarla se limpia
    `plan_programado`, así que correrlo dos veces el mismo día no hace nada la
    segunda vez.

    NO toca el vencimiento. Que la empresa quede vencida o no es asunto del
    cobro, no del cambio de plan — mezclar las dos cosas acá haría que una
    bajada de plan renovara la suscripción de arriba.
    """
    hoy = hoy or dt.date.today()
    pendientes = list(
        db.scalars(
            select(Empresa).where(
                Empresa.plan_programado.is_not(None),
                Empresa.suscripcion_vence.is_not(None),
                Empresa.suscripcion_vence <= hoy,
            )
        )
    )
    for empresa in pendientes:
        antes = empresa.plan
        empresa.plan = empresa.plan_programado
        empresa.plan_programado = None
        registrar_ajuste(
            db,
            empresa,
            tipo="plan",
            vence_antes=empresa.suscripcion_vence,
            vence_despues=empresa.suscripcion_vence,
            detalle=(
                f"Baja aplicada: {planes.limites_de(antes).etiqueta} → "
                f"{planes.limites_de(empresa.plan).etiqueta}"
            ),
            hecho_por="sistema",
        )
    if pendientes:
        db.commit()
    return len(pendientes)
