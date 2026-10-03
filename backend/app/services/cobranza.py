"""Cobranza del SaaS: el semáforo de vencimientos y la caja de Turnos360.

Reglas de negocio (definidas por Leandro):
- El ciclo dura 30 días y después hay unos días de PRÓRROGA antes de
  considerar la cuenta vencida de verdad (DIAS_PRORROGA en
  services/suscripcion.py; hoy son 3).
- El semáforo del listado es para saber A QUIÉN COBRARLE de un vistazo:
    verde    = al día
    amarillo = vence dentro de los próximos DIAS_AVISO días (hay que ir a cobrar)
    rojo     = pasó el vencimiento (dentro o fuera de la prórroga)
    gris     = sin vencimiento (plan gratuito / piloto bonificado)
  El rojo incluye la prórroga a propósito: durante esos días el negocio
  sigue operando, pero para vos ya es "me tiene que pagar".
"""

import datetime as dt
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import planes
from app.models import (
    AjusteSuscripcion,
    AvisoPago,
    DebitoAutomatico,
    Empresa,
    PagoSuscripcion,
    Recurso,
    Usuario,
)
from app.services.suscripcion import DIAS_PRORROGA, cuota_de


def _cuota(empresa: Empresa) -> float | None:
    """La cuota mensual de esta empresa. None = no le corresponde pagar."""
    monto, _origen = cuota_de(empresa)
    return monto

# Los tres estados de un aviso de transferencia. Son strings y no un Enum de
# base porque los estados de cobranza cambian con el negocio y no vale una
# migración por cada uno — el mismo criterio que ya usa `metodo`.
PENDIENTE = "pendiente"
INFO_SOLICITADA = "info_solicitada"
CONFIRMADA = "confirmada"
RECHAZADA = "rechazada"
ESTADOS_AVISO = (PENDIENTE, INFO_SOLICITADA, CONFIRMADA, RECHAZADA)
# Los que todavía esperan una decisión del super-admin.
ESTADOS_ABIERTOS = (PENDIENTE, INFO_SOLICITADA)

# Días de anticipación con los que una empresa entra en amarillo.
DIAS_AVISO = 7
# Duración del ciclo: registrar un pago empuja el vencimiento esta cantidad.
DIAS_CICLO = 30


def semaforo_de(empresa: Empresa, hoy: dt.date | None = None) -> dict:
    """Color, días restantes y estado de cobranza de una empresa."""
    hoy = hoy or _hoy_negocio()
    vence = empresa.suscripcion_vence

    # Pausada por el super-admin o cancelada por el negocio: no hay a quién
    # cobrarle este mes, pero tiene que leerse de un vistazo.
    if not empresa.activa:
        return {"color": "rojo", "dias_restantes": None, "fin_prorroga": None,
                "en_prorroga": False, "detalle": "Suspendida por administración"}
    if empresa.cancela_al_vencer:
        fin = max(d for d in (vence, empresa.prueba_hasta) if d) if (vence or empresa.prueba_hasta) else None
        if empresa.cancelada_en is not None or fin is None or hoy > fin:
            return {"color": "gris", "dias_restantes": None, "fin_prorroga": None,
                    "en_prorroga": False, "detalle": "Cancelada"}
        dias = (fin - hoy).days
        return {"color": "amarillo", "dias_restantes": dias, "fin_prorroga": None,
                "en_prorroga": False,
                "detalle": f"Cancela el {fin.strftime('%d/%m')} · {dias} día{'s' if dias != 1 else ''}"}

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
    filtro: str | None = None,
) -> list[dict]:
    """Listado del panel con semáforo, uso y datos comerciales.

    `filtro` es el chip del panel: en_revision · por_vencer · vencidas ·
    al_dia · en_prueba · canceladas · sin_vencimiento.

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
            .where(
                PagoSuscripcion.empresa_id.in_(ids),
                PagoSuscripcion.anulado.is_(False),
            )
            .group_by(PagoSuscripcion.empresa_id)
        ).all()
    )

    # QUIÉN PAGA SOLO Y QUIÉN HAY QUE IR A BUSCAR.
    #
    # Es la distinción que ordena todo el trabajo de cobranza: un negocio con
    # débito automático andando no necesita que nadie lo llame ni le revise el
    # banco, y mezclarlo con los demás hace que la lista de "pendientes" sea
    # más larga de lo que realmente es. El que tiene un cobro rebotado sí
    # necesita atención —y URGENTE, porque él todavía no lo sabe—, así que se
    # trae también la cuenta de fallos.
    #
    # Una consulta para todos, no una por fila: con cien clientes serían cien
    # viajes a la base para dibujar una etiqueta.
    debitos = {
        fila.empresa_id: fila
        for fila in db.scalars(
            select(DebitoAutomatico).where(
                DebitoAutomatico.empresa_id.in_(ids),
                DebitoAutomatico.estado.in_(("pending", "authorized", "paused")),
            )
        )
    }

    from app.services.suscripcion import estado_suscripcion

    revisando = set(
        db.scalars(
            select(AvisoPago.empresa_id).where(
                AvisoPago.empresa_id.in_(ids), AvisoPago.estado.in_(ESTADOS_ABIERTOS)
            )
        )
    )
    hoy = _hoy_negocio()

    filas = []
    for e in empresas:
        sem = semaforo_de(e, hoy)
        if color and sem["color"] != color:
            continue
        est = estado_suscripcion(e, hoy=hoy, en_revision=e.id in revisando)
        if filtro and not _pasa_filtro(filtro, est, sem):
            continue
        usados = recursos.get(e.id, 0)
        filas.append(
            {
                "id": e.id,
                "estado": est["estado"],
                "estado_etiqueta": est["etiqueta"],
                "estado_tono": est["tono"],
                "cancela_al_vencer": bool(e.cancela_al_vencer),
                "plan_programado": e.plan_programado,
                "nombre": e.nombre,
                "slug": e.slug,
                "activa": e.activa,
                "plan": e.plan or "gratuito",
                "suscripcion_vence": str(e.suscripcion_vence) if e.suscripcion_vence else None,
                # La cuota que se le cobra, venga de un precio pactado o de
                # la grilla. La columna cruda diría NULL para casi todos.
                "precio_mensual": _cuota(e),
                "precio_pactado": e.precio_mensual is not None,
                # El estado del débito automático, o None si no tiene.
                "debito": (
                    {
                        "estado": debitos[e.id].estado,
                        "cobros_fallidos": debitos[e.id].cobros_fallidos or 0,
                        "ultimo_error": debitos[e.id].ultimo_error,
                    }
                    if e.id in debitos
                    else None
                ),
                "razon_social": e.razon_social,
                "cuit": e.cuit,
                "contacto_nombre": e.contacto_nombre,
                "contacto_email": e.contacto_email,
                "contacto_telefono": e.contacto_telefono,
                "notas_admin": e.notas_admin,
                "cantidad_usuarios": usuarios.get(e.id, 0),
                "cantidad_recursos": usados,
                "limite_recursos": e.limite_recursos,
                "limite_sucursales": e.limite_sucursales,
                # Aviso de capacidad: el panel lo pinta cuando llegó al tope.
                "capacidad_excedida": (
                    e.limite_recursos is not None and usados >= e.limite_recursos
                ),
                "ultimo_pago": str(ultimo_pago[e.id]) if e.id in ultimo_pago else None,
                **{f"semaforo_{k}": v for k, v in sem.items()},
            }
        )
    return filas


FILTROS = ("en_revision", "por_vencer", "vencidas", "al_dia", "en_prueba", "canceladas", "sin_vencimiento")


def _pasa_filtro(filtro: str, est: dict, sem: dict) -> bool:
    e = est["estado"]
    if filtro == "en_revision":
        return e in ("en_revision", "pendiente_pago")
    if filtro == "por_vencer":
        return sem["color"] == "amarillo" and e in ("activa", "cancelacion_programada")
    if filtro == "vencidas":
        return est["estado_base"] in ("prorroga", "vencida", "prueba_vencida")
    if filtro == "al_dia":
        return e == "activa"
    if filtro == "en_prueba":
        return e == "prueba"
    if filtro == "canceladas":
        return e in ("cancelada", "cancelacion_programada")
    if filtro == "sin_vencimiento":
        return e == "sin_vencimiento"
    return True


def resumen_cobranza(db: Session, hoy: dt.date | None = None) -> dict:
    """KPIs y alertas del panel de cobranza.

    Todo sale del MISMO estado que ve el negocio (`estado_suscripcion`), así
    el panel y la pantalla del cliente no pueden contradecirse. Los pagos
    anulados no cuentan como cobrados.
    """
    from app.core.estados_suscripcion import VIVOS
    from app.core.estados_suscripcion import EstadoSuscripcion as E
    from app.models import IntentoPago
    from app.services.suscripcion import estado_suscripcion

    hoy = hoy or _hoy_negocio()
    inicio_mes = hoy.replace(day=1)
    inicio_mes_dt = dt.datetime.combine(inicio_mes, dt.time.min, tzinfo=dt.UTC)
    vigente = PagoSuscripcion.anulado.is_(False)

    cobrado = db.scalar(
        select(func.coalesce(func.sum(PagoSuscripcion.monto), 0)).where(
            PagoSuscripcion.fecha >= inicio_mes, PagoSuscripcion.fecha <= hoy, vigente
        )
    ) or Decimal(0)
    por_metodo = [
        {"metodo": m, "total": float(t)}
        for m, t in db.execute(
            select(PagoSuscripcion.metodo, func.sum(PagoSuscripcion.monto))
            .where(PagoSuscripcion.fecha >= inicio_mes, PagoSuscripcion.fecha <= hoy, vigente)
            .group_by(PagoSuscripcion.metodo)
            .order_by(func.sum(PagoSuscripcion.monto).desc())
        ).all()
    ]
    renovaciones_ok = int(
        db.scalar(
            select(func.count(PagoSuscripcion.id)).where(
                PagoSuscripcion.fecha >= inicio_mes, vigente,
                PagoSuscripcion.tipo.in_(("renovacion", "alta", "cambio_plan", "reactivacion")),
            )
        )
        or 0
    )

    avisos = list(db.scalars(select(AvisoPago).where(AvisoPago.estado.in_(ESTADOS_ABIERTOS))))
    revisando = {a.empresa_id for a in avisos}

    empresas = list(db.scalars(select(Empresa)).all())
    por_vencer, vencidas, vivas, canceladas_prog = [], [], [], 0
    en_prueba = 0
    for e in empresas:
        est = estado_suscripcion(e, hoy=hoy, en_revision=e.id in revisando)
        estado, base = E(est["estado"]), E(est["estado_base"])
        if estado in VIVOS:
            vivas.append(e)
        if estado is E.TRIAL:
            en_prueba += 1
        if estado is E.CANCEL_PENDING:
            canceladas_prog += 1
        if estado is E.ACTIVE and est["dias_restantes"] is not None and est["dias_restantes"] <= DIAS_AVISO:
            por_vencer.append(e)
        if base in (E.GRACE_PERIOD, E.PAST_DUE, E.EXPIRED):
            vencidas.append(e)

    pendiente = sum(_cuota(e) or 0 for e in por_vencer)
    sin_precio = sum(1 for e in por_vencer if _cuota(e) is None)
    deuda_vencida = sum(_cuota(e) or 0 for e in vencidas)
    mrr = Decimal(str(sum(_cuota(e) or 0 for e in vivas)))

    cancelaciones_mes = int(
        db.scalar(
            select(func.count(AjusteSuscripcion.id)).where(
                AjusteSuscripcion.tipo == "cancelacion",
                AjusteSuscripcion.creado_en >= inicio_mes_dt,
            )
        )
        or 0
    )
    rechazados = int(
        db.scalar(
            select(func.count(IntentoPago.id)).where(
                IntentoPago.estado == "rechazado", IntentoPago.creado_en >= inicio_mes_dt
            )
        )
        or 0
    ) + int(
        db.scalar(
            select(func.count(DebitoAutomatico.id)).where(
                DebitoAutomatico.estado.in_(("pending", "authorized", "paused")),
                DebitoAutomatico.cobros_fallidos > 0,
            )
        )
        or 0
    )
    monto_revision = sum(float(a.monto or 0) for a in avisos)

    alertas = []
    if avisos:
        n = len(avisos)
        alertas.append({"nivel": "rojo", "filtro": "en_revision",
                        "texto": f"{n} pago{'s' if n != 1 else ''} requiere{'n' if n != 1 else ''} revisión"})
    if vencidas:
        n = len(vencidas)
        alertas.append({"nivel": "naranja", "filtro": "vencidas",
                        "texto": f"{n} suscripci{'ones' if n != 1 else 'ón'} vencida{'s' if n != 1 else ''}"})
    if rechazados:
        alertas.append({"nivel": "naranja", "filtro": None,
                        "texto": f"{rechazados} pago{'s' if rechazados != 1 else ''} rechazado{'s' if rechazados != 1 else ''} este mes"})
    if por_vencer:
        n = len(por_vencer)
        alertas.append({"nivel": "ambar", "filtro": "por_vencer",
                        "texto": f"{n} suscripci{'ones' if n != 1 else 'ón'} vence{'n' if n != 1 else ''} en {DIAS_AVISO} días"})
    if renovaciones_ok:
        alertas.append({"nivel": "verde", "filtro": None,
                        "texto": f"{renovaciones_ok} pago{'s' if renovaciones_ok != 1 else ''} acreditado{'s' if renovaciones_ok != 1 else ''} este mes"})

    return {
        "empresas_en_prueba": en_prueba,
        "cobrado_mes": float(cobrado),
        "por_metodo": por_metodo,
        "pendiente_estimado": pendiente,
        "empresas_por_vencer": len(por_vencer),
        "por_vencer_sin_precio": sin_precio,
        "deuda_vencida": deuda_vencida,
        "empresas_vencidas": len(vencidas),
        "mrr": float(mrr),
        "suscripciones_activas": len(vivas),
        "pagos_en_revision": len(avisos),
        "monto_en_revision": monto_revision,
        "cancelaciones_mes": cancelaciones_mes,
        "cancelaciones_programadas": canceladas_prog,
        "pagos_rechazados": rechazados,
        "renovaciones_mes": renovaciones_ok,
        "alertas": alertas,
        "dias_aviso": DIAS_AVISO,
        "dias_prorroga": DIAS_PRORROGA,
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
    *,
    actor_tipo: str | None = None,
    intento_id: int | None = None,
    clave_idempotencia: str | None = None,
    aviso_id: int | None = None,
) -> PagoSuscripcion:
    """Anota una cuota cobrada, activa el plan comprado y corre el vencimiento.

    DE DÓNDE SE CUENTAN LOS 30 DÍAS
    ───────────────────────────────
    - Si paga DENTRO de la prórroga, se cuenta desde el vencimiento viejo: el
      negocio nunca dejó de estar cubierto y no pierde los días de atraso.
    - Si paga DESPUÉS de la prórroga, se cuenta desde hoy.
    - Y NUNCA queda con menos días de los que ya tenía.

    Subir de plan cobra el plan nuevo completo y suma 30 días al vencimiento
    (decisión de negocio: no hay prorrateo).

    La empresa se toma con FOR UPDATE: dos acreditaciones simultáneas (un
    webhook y una confirmación manual, o un doble click) se serializan y la
    segunda ve el vencimiento ya corrido, en vez de pisarlo.

    Pagar REACTIVA: limpia una cancelación programada o hecha efectiva.
    """
    db.scalar(select(Empresa.id).where(Empresa.id == empresa.id).with_for_update())
    db.refresh(empresa)

    if clave_idempotencia:
        previo = db.scalar(
            select(PagoSuscripcion).where(
                PagoSuscripcion.clave_idempotencia == clave_idempotencia
            )
        )
        if previo is not None:
            if previo.empresa_id != empresa.id:
                raise HTTPException(status.HTTP_409_CONFLICT, "Esa operación ya se usó.")
            return previo

    hoy = _hoy_negocio()
    fecha = fecha or hoy
    desde = empresa.suscripcion_vence
    estado_antes = _estado(db, empresa)
    plan_antes = empresa.plan
    hubo_pagos = (
        db.scalar(
            select(PagoSuscripcion.id).where(
                PagoSuscripcion.empresa_id == empresa.id,
                PagoSuscripcion.anulado.is_(False),
            ).limit(1)
        )
        is not None
    )

    pago = PagoSuscripcion(
        empresa_id=empresa.id,
        fecha=fecha,
        monto=monto,
        metodo=metodo,
        notas=notas,
        registrado_por=registrado_por,
        intento_id=intento_id,
        clave_idempotencia=clave_idempotencia,
    )

    if renovar:
        if plan:
            # Compró un plan concreto: se activa, sea subida o bajada. Y se
            # cancela cualquier baja programada — acaba de decidir de nuevo.
            empresa.plan = plan
            empresa.plan_programado = None
        elif planes.plan_de(empresa.plan) is planes.Plan.GRATUITO:
            # Quien paga deja de estar en prueba y cae en el plan de ENTRADA.
            empresa.plan = planes.PLAN_DE_ENTRADA.value

        limite_continuidad = fecha - dt.timedelta(days=DIAS_PRORROGA)
        base = desde if desde and desde >= limite_continuidad else fecha
        nuevo = base + dt.timedelta(days=DIAS_CICLO)
        if desde and desde > nuevo:
            nuevo = desde
        pago.periodo_desde = base
        pago.periodo_hasta = nuevo
        empresa.suscripcion_vence = nuevo
        # Pagar es volver a elegir: una cancelación pendiente o hecha se va.
        reactiva = empresa.cancela_al_vencer
        empresa.cancela_al_vencer = False
        empresa.cancelada_en = None
        empresa.cancelacion_solicitada_en = None
        empresa.cancelacion_motivo = None
    else:
        reactiva = False

    if not hubo_pagos:
        pago.tipo = "alta"
    elif reactiva or estado_antes in ("cancelada",):
        pago.tipo = "reactivacion"
    elif plan and planes.plan_de(plan) is not planes.plan_de(plan_antes):
        pago.tipo = "cambio_plan"
    elif not renovar:
        pago.tipo = "manual"
    else:
        pago.tipo = "renovacion"
    pago.plan = empresa.plan

    db.add(pago)
    db.flush()

    registrar_ajuste(
        db,
        empresa,
        tipo="pago",
        vence_antes=desde,
        vence_despues=empresa.suscripcion_vence,
        detalle=(
            f"{_TIPO_PAGO.get(pago.tipo, 'Cuota')} de {pesos(monto)} por {metodo}"
            + (f" · pasa a {planes.limites_de(plan).etiqueta}" if plan and plan != plan_antes else "")
        ),
        pago_id=pago.id,
        hecho_por=registrado_por,
        actor_tipo=actor_tipo,
        estado_antes=estado_antes,
        estado_despues=_estado(db, empresa),
        plan_antes=plan_antes,
        plan_despues=empresa.plan,
        monto=float(monto),
        aviso_id=aviso_id,
    )
    return pago


_TIPO_PAGO = {
    "alta": "Pago inicial",
    "renovacion": "Renovación",
    "cambio_plan": "Cambio de plan",
    "reactivacion": "Reactivación",
    "manual": "Pago sin renovar",
}


def pesos(n) -> str:
    """$19.990 — separador de miles argentino, sin tocar el resto del texto."""
    return "$" + f"{float(n or 0):,.0f}".replace(",", ".")


def _hoy_negocio() -> dt.date:
    from app.core.reloj import hoy_de_pared

    return hoy_de_pared()


def prorrogar(
    db: Session, empresa: Empresa, dias: int, hecho_por: str | None = None
) -> dt.date:
    """Extiende el vencimiento N días (gracia manual o extensión de prueba).

    Si la empresa no tenía fecha, se cuenta desde hoy. Si ya venció, también:
    dar 5 días de gracia a alguien que venció hace un mes significa 5 días
    desde hoy, no desde una fecha vieja.
    """
    hoy = _hoy_negocio()
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
            # Con id de MP = se puede preguntar a Mercado Pago qué pasó
            # después. Sin id, la verificación es contra el banco y la hace
            # una persona. La pantalla necesita saber cuál de las dos es.
            "mp_payment_id": p.mp_payment_id,
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
    actor_tipo: str | None = None,
    estado_antes: str | None = None,
    estado_despues: str | None = None,
    plan_antes: str | None = None,
    plan_despues: str | None = None,
    monto: float | None = None,
    aviso_id: int | None = None,
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
        actor_tipo=actor_tipo or _actor_de(hecho_por),
        estado_antes=estado_antes,
        estado_despues=estado_despues,
        plan_antes=plan_antes,
        plan_despues=plan_despues,
        monto=monto,
        aviso_id=aviso_id,
    )
    db.add(aj)
    db.flush()
    return aj


def _actor_de(hecho_por: str | None) -> str:
    if hecho_por in ("sistema",):
        return "sistema"
    if hecho_por in ("mercadopago",):
        return "mercadopago"
    return "admin" if hecho_por else "sistema"


def evento(
    db: Session,
    empresa: Empresa,
    tipo: str,
    detalle: str,
    *,
    hecho_por: str | None,
    actor_tipo: str,
    estado_antes: str | None = None,
    estado_despues: str | None = None,
    plan_antes: str | None = None,
    plan_despues: str | None = None,
    monto: float | None = None,
    aviso_id: int | None = None,
    pago_id: int | None = None,
) -> AjusteSuscripcion:
    """Anota un hecho de la suscripción que NO mueve el vencimiento."""
    return registrar_ajuste(
        db,
        empresa,
        tipo=tipo,
        vence_antes=empresa.suscripcion_vence,
        vence_despues=empresa.suscripcion_vence,
        detalle=detalle,
        hecho_por=hecho_por,
        actor_tipo=actor_tipo,
        estado_antes=estado_antes,
        estado_despues=estado_despues,
        plan_antes=plan_antes,
        plan_despues=plan_despues,
        monto=monto,
        aviso_id=aviso_id,
        pago_id=pago_id,
    )


def _estado(db: Session, empresa: Empresa) -> str:
    from app.services.suscripcion import estado_suscripcion

    return estado_suscripcion(empresa, db)["estado"]


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
            "actor_tipo": a.actor_tipo,
            "estado_antes": a.estado_antes,
            "estado_despues": a.estado_despues,
            "plan_antes": a.plan_antes,
            "plan_despues": a.plan_despues,
            "monto": float(a.monto) if a.monto is not None else None,
            "creado_en": a.creado_en.isoformat() if a.creado_en else None,
            "revertido": bool(a.revertido),
            "revertido_por": a.revertido_por,
            # Una reversión no se revierte: sería un ping-pong sin sentido.
            # Para volver a mover la fecha están el cobro y la prórroga.
            "reversible": (not a.revertido)
            and a.tipo in ("pago", "renovacion", "prorroga", "manual"),
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
    if aj.tipo not in ("pago", "renovacion", "prorroga", "manual"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ese evento no movió el vencimiento: no hay nada que deshacer.",
        )

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    ahora = dt.datetime.now(dt.UTC)
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


def tipo_de_cobro(empresa: Empresa, plan: str | None) -> str:
    """Qué está pagando: el primer pago, una renovación o un cambio de plan."""
    from app.services.suscripcion import estado_suscripcion

    if plan and planes.plan_de(plan) is not planes.plan_de(empresa.plan):
        return "cambio_plan" if empresa.suscripcion_vence else "alta"
    if estado_suscripcion(empresa)["estado"] == "cancelada":
        return "reactivacion"
    return "renovacion" if empresa.suscripcion_vence else "alta"


def registrar_aviso(
    db: Session,
    empresa: Empresa,
    *,
    metodo: str = "transferencia",
    monto: float | None = None,
    referencia: str | None = None,
    avisado_por: str | None = None,
    plan: str | None = None,
    comprobante: str | None = None,
) -> AvisoPago:
    """El dueño avisa que pagó. Todavía no es plata: es un aviso.

    EL SERVIDOR DECIDE QUÉ SE ESTÁ PAGANDO: el plan (validado contra la
    grilla), el tipo de cobro y el monto esperado. Lo que manda el negocio es
    solo cuánto dice que transfirió y la referencia, y eso se COMPARA contra
    lo esperado; nunca lo reemplaza.

    Si ya hay un aviso abierto de esta empresa se actualiza ese mismo, sin
    crear otro. Si el super-admin había pedido información, la respuesta lo
    devuelve a «pendiente» para que vuelva a la bandeja.
    """
    from app.services import mp_suscripcion as mp_sus

    if plan is not None:
        elegido = planes.plan_de(plan)
        if not planes.se_vende_solo(elegido):
            plan = None
        else:
            plan = elegido.value
    plan_final = plan or (
        planes.PLAN_DE_ENTRADA.value
        if planes.plan_de(empresa.plan) is planes.Plan.GRATUITO
        else planes.plan_de(empresa.plan).value
    )
    esperado = mp_sus.precio_de(empresa, plan_final)
    tipo = tipo_de_cobro(empresa, plan_final)

    abierto = db.scalar(
        select(AvisoPago)
        .where(AvisoPago.empresa_id == empresa.id, AvisoPago.estado.in_(ESTADOS_ABIERTOS))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if abierto is not None:
        if referencia:
            abierto.referencia = referencia.strip()[:300]
        if comprobante:
            abierto.comprobante = comprobante
        if monto is not None:
            abierto.monto = monto
        if plan is not None and plan_final != abierto.plan:
            # Cambió lo que está pagando: lo esperado lo recalcula el servidor.
            abierto.plan, abierto.tipo, abierto.monto_esperado = plan_final, tipo, esperado
        if abierto.estado == INFO_SOLICITADA:
            abierto.estado = PENDIENTE
            evento(db, empresa, "aviso", "El negocio respondió el pedido de información",
                   hecho_por=avisado_por, actor_tipo="dueno", aviso_id=abierto.id)
        db.commit()
        db.refresh(abierto)
        return abierto

    aviso = AvisoPago(
        empresa_id=empresa.id,
        metodo=metodo,
        monto=monto,
        referencia=(referencia or "").strip()[:300] or None,
        avisado_por=(avisado_por or "")[:160] or None,
        plan=plan_final,
        tipo=tipo,
        monto_esperado=esperado,
        comprobante=comprobante,
    )
    db.add(aviso)
    db.flush()
    evento(
        db, empresa, "aviso",
        f"Informó una transferencia de {pesos(monto)} "
        f"({planes.limites_de(plan_final).etiqueta}, se esperan {pesos(esperado)})",
        hecho_por=avisado_por, actor_tipo="dueno", aviso_id=aviso.id,
        monto=float(monto) if monto is not None else None,
        estado_despues="en_revision",
    )
    db.commit()
    db.refresh(aviso)
    return aviso


def aviso_abierto(db: Session, empresa_id: int) -> AvisoPago | None:
    """El aviso que todavía espera una decisión (pendiente o con pedido de info)."""
    return db.scalar(
        select(AvisoPago).where(
            AvisoPago.empresa_id == empresa_id, AvisoPago.estado.in_(ESTADOS_ABIERTOS)
        )
    )


# Nombre histórico: lo usan los routers y los tests.
aviso_pendiente = aviso_abierto


def listar_avisos(db: Session, solo_pendientes: bool = True) -> list[dict]:
    """La bandeja de entrada: quién dice que pagó y no está confirmado.

    CADA AVISO VIAJA CON TODO LO QUE HACE FALTA PARA DECIDIR
    ────────────────────────────────────────────────────────
    Antes traía solo el nombre, el monto y la referencia. Confirmar un pago
    significaba abrir el diálogo de cobro, que llegaba con el monto de LISTA
    precargado —no con el que la persona dijo que transfirió— y sin nada del
    aviso a la vista. Había que acordarse del número mirando la lista de atrás,
    y si el negocio tenía un precio pactado distinto, el campo venía mal y no
    había cómo notarlo.

    Ahora viaja también qué se le espera cobrar, en qué plan está, y si el
    monto avisado coincide con el esperado. Eso convierte «confirmar un pago»
    de un ejercicio de memoria en una comparación de dos números que están uno
    al lado del otro.
    """
    q = select(AvisoPago, Empresa).join(Empresa, AvisoPago.empresa_id == Empresa.id)
    if solo_pendientes:
        q = q.where(AvisoPago.estado.in_(ESTADOS_ABIERTOS))
    filas = db.execute(q.order_by(AvisoPago.creado_en.desc()).limit(100)).all()

    salida = []
    for a, empresa in filas:
        avisado = float(a.monto) if a.monto is not None else None
        # Lo que le corresponde pagar: su precio pactado, o el del plan que
        # tiene. El pactado manda — para eso existe la columna.
        # El esperado lo fijó el servidor AL RECIBIR el aviso (incluye el plan
        # que se está comprando). Los avisos viejos no lo tienen: cuota actual.
        esperado = (
            float(a.monto_esperado) if a.monto_esperado is not None else _cuota(empresa)
        )
        plan_aviso = a.plan or empresa.plan
        salida.append(
            {
                "id": a.id,
                "empresa_id": a.empresa_id,
                "empresa_nombre": empresa.nombre,
                "metodo": a.metodo,
                "monto": avisado,
                "referencia": a.referencia,
                "avisado_por": a.avisado_por,
                "creado_en": a.creado_en.isoformat() if a.creado_en else None,
                "estado": a.estado,
                "motivo": a.motivo,
                "resuelto": a.resuelto,
                # Con qué comparar el monto avisado, sin salir de la bandeja.
                "monto_esperado": esperado or None,
                "plan_codigo": planes.plan_de(plan_aviso).value,
                "plan_etiqueta": planes.limites_de(plan_aviso).etiqueta,
                "plan_actual_etiqueta": planes.limites_de(empresa.plan).etiqueta,
                "tipo": a.tipo or "renovacion",
                "tiene_comprobante": bool(a.comprobante),
                "mensaje_admin": a.mensaje_admin,
                "pago_id": a.pago_id,
                "resuelto_por": a.resuelto_por,
                "resuelto_en": a.resuelto_en.isoformat() if a.resuelto_en else None,
                "vence": (
                    empresa.suscripcion_vence.isoformat()
                    if empresa.suscripcion_vence
                    else None
                ),
                # True = avisó exactamente lo que se le espera. La bandeja lo
                # marca en verde: esos se confirman de un vistazo, y el ojo
                # queda libre para los que NO coinciden, que son los únicos
                # que hay que pensar.
                # `esperado` es None cuando a la empresa no le corresponde
                # una cuota (está en prueba, o es un Enterprise sin precio
                # cargado). Ahí NUNCA coincide: no hay contra qué comparar, y
                # pintar de verde una fila que nadie verificó es exactamente
                # lo que esta columna vino a evitar.
                "coincide": (
                    avisado is not None
                    and esperado is not None
                    and esperado > 0
                    and abs(avisado - esperado) < 1
                ),
            }
        )
    return salida


def resolver_aviso(
    db: Session,
    aviso_id: int,
    *,
    pago_id: int | None,
    resuelto_por: str | None,
    motivo: str | None = None,
) -> None:
    """Cierra el aviso: confirmado si vino con cuota, rechazado si no.

    El ESTADO no se deduce de si hay pago_id o no: se escribe. Antes se
    deducía, y eso hacía indistinguible un rechazo de un camino que resolvió
    sin registrar la cuota — dos cosas muy distintas cuando el negocio
    pregunta por qué no le acreditaron el mes.

    `motivo` solo tiene sentido al rechazar, y es lo que se le contesta al que
    reclama: «no apareció en el banco», «vino por otro importe».
    """
    aviso = db.scalar(select(AvisoPago).where(AvisoPago.id == aviso_id).with_for_update()
                       .execution_options(populate_existing=True))
    if aviso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese aviso no existe.")
    if aviso.estado not in ESTADOS_ABIERTOS:
        return
    aviso.estado = CONFIRMADA if pago_id is not None else RECHAZADA
    aviso.motivo = (motivo or "").strip()[:200] or None
    aviso.resuelto_en = dt.datetime.now(dt.UTC)
    aviso.resuelto_por = (resuelto_por or "")[:160] or None
    aviso.pago_id = pago_id
    if pago_id is None:
        empresa = db.get(Empresa, aviso.empresa_id)
        evento(
            db, empresa, "aviso_rechazado",
            f"Transferencia rechazada: {aviso.motivo or 'sin motivo'}",
            hecho_por=resuelto_por, actor_tipo="admin", aviso_id=aviso.id,
            monto=float(aviso.monto) if aviso.monto is not None else None,
            estado_antes="en_revision", estado_despues=_estado(db, empresa),
        )
    db.commit()


def aprobar_aviso(
    db: Session,
    aviso_id: int,
    *,
    monto: float | None,
    fecha: dt.date | None,
    hecho_por: str,
    notas: str | None = None,
) -> PagoSuscripcion:
    """Confirma una transferencia: registra la cuota UNA vez y cierra el aviso.

    El aviso se toma con FOR UPDATE. Dos super-admins (o dos pestañas)
    aprobando el mismo aviso a la vez se serializan: el segundo lo encuentra
    confirmado y recibe 409 en vez de anotar otra cuota y regalar otro mes.

    El plan que se activa es el que el SERVIDOR fijó al recibir el aviso. El
    monto es el que el super-admin vio en el banco (por defecto, el avisado).
    """
    aviso = db.scalar(select(AvisoPago).where(AvisoPago.id == aviso_id).with_for_update()
                       .execution_options(populate_existing=True))
    if aviso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese aviso no existe.")
    if aviso.estado not in ESTADOS_ABIERTOS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ese aviso ya está {aviso.estado}. No se registró nada nuevo.",
        )
    empresa = db.get(Empresa, aviso.empresa_id)
    importe = float(monto if monto is not None else (aviso.monto or aviso.monto_esperado or 0))
    if importe <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indicá el monto que entró.")
    plan = aviso.plan if aviso.plan and planes.se_vende_solo(planes.plan_de(aviso.plan)) else None
    pago = registrar_pago(
        db, empresa, monto=importe, metodo=aviso.metodo or "transferencia",
        fecha=fecha, notas=notas or (f"Transferencia · {aviso.referencia}" if aviso.referencia else "Transferencia"),
        registrado_por=hecho_por, renovar=True, plan=plan, actor_tipo="admin",
        aviso_id=aviso.id,
    )
    aviso.estado = CONFIRMADA
    aviso.resuelto_en = dt.datetime.now(dt.UTC)
    aviso.resuelto_por = hecho_por[:160]
    aviso.pago_id = pago.id
    db.commit()
    db.refresh(pago)
    return pago


def solicitar_info(db: Session, aviso_id: int, mensaje: str, hecho_por: str) -> AvisoPago:
    """Le pide al negocio un dato más (comprobante, número de operación…).

    El aviso queda abierto en «info_solicitada»: el negocio ve el mensaje en
    «Mi suscripción» y, al responder, vuelve a «pendiente».
    """
    aviso = db.scalar(select(AvisoPago).where(AvisoPago.id == aviso_id).with_for_update()
                       .execution_options(populate_existing=True))
    if aviso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese aviso no existe.")
    if aviso.estado not in ESTADOS_ABIERTOS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ese aviso ya está {aviso.estado}.")
    texto = (mensaje or "").strip()[:300]
    if not texto:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Escribí qué información necesitás.")
    aviso.estado = INFO_SOLICITADA
    aviso.mensaje_admin = texto
    empresa = db.get(Empresa, aviso.empresa_id)
    evento(db, empresa, "info_solicitada", f"Se pidió información: {texto}",
           hecho_por=hecho_por, actor_tipo="admin", aviso_id=aviso.id)
    db.commit()
    db.refresh(aviso)
    return aviso


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


ETIQUETA_FUNCION = {
    "membresias": "Membresías y abonos",
    "gift_cards": "Gift cards",
    "cupones": "Cupones de descuento",
    "campanas": "Campañas automáticas",
    "comisiones": "Comisiones por profesional",
    "whatsapp": "WhatsApp",
    "multisucursal": "Varias sucursales",
    "estadisticas_avanzadas": "Estadísticas avanzadas",
}


def uso_actual(db: Session, empresa: Empresa) -> dict:
    """Lo que la empresa tiene cargado HOY y cuenta contra los topes del plan."""
    from app.models import Sucursal
    from app.models.enums import TipoRecurso

    return {
        "profesionales": int(db.scalar(select(func.count(Recurso.id)).where(
            Recurso.empresa_id == empresa.id, Recurso.activo.is_(True),
            Recurso.tipo == TipoRecurso.PERSONA)) or 0),
        "usuarios": int(db.scalar(select(func.count(Usuario.id)).where(
            Usuario.empresa_id == empresa.id, Usuario.activo.is_(True))) or 0),
        "sucursales": int(db.scalar(select(func.count(Sucursal.id)).where(
            Sucursal.empresa_id == empresa.id, Sucursal.activa.is_(True))) or 0),
    }


def topes_de(empresa: Empresa, plan: str) -> dict:
    """Los topes que tendría la empresa con `plan` (los overrides mandan)."""
    return {
        "profesionales": planes.tope_profesionales(plan, empresa.limite_recursos),
        "usuarios": planes.tope_usuarios(plan),
        "sucursales": planes.tope_sucursales(plan, empresa.limite_sucursales),
    }


_NOMBRE_RECURSO = {"profesionales": "profesionales", "usuarios": "usuarios con acceso", "sucursales": "sucursales"}


def incompatibilidades(db: Session, empresa: Empresa, destino: str) -> list[dict]:
    """Qué está usando hoy que el plan `destino` no admite.

    Bajar de plan con 3 sucursales a uno que permite 1 dejaría un estado
    imposible. Esto es lo que se le muestra al negocio ANTES de confirmar y lo
    que frena la baja si al llegar la fecha sigue sin resolverse.
    """
    uso = uso_actual(db, empresa)
    topes = topes_de(empresa, destino)
    etiqueta = planes.limites_de(destino).etiqueta
    salida = []
    for clave, usados in uso.items():
        tope = topes[clave]
        if tope is not None and usados > tope:
            salida.append({
                "recurso": clave,
                "usados": usados,
                "tope": tope,
                "mensaje": (
                    f"Actualmente usás {usados} {_NOMBRE_RECURSO[clave]}. "
                    f"El plan {etiqueta} permite {tope}."
                ),
            })
    return salida


def vista_previa_cambio(db: Session, empresa: Empresa, destino: str) -> dict:
    """Todo lo que el negocio tiene que ver ANTES de confirmar un cambio de plan.

    Lo calcula el servidor: el precio, desde cuándo, el nuevo vencimiento, qué
    gana, qué pierde y qué tiene que reducir. La pantalla no decide nada.
    """
    from app.services import mp_debito
    from app.services import mp_suscripcion as mp_sus
    from app.services.suscripcion import cuota_de, estado_suscripcion

    destino = planes.plan_de(destino).value
    actual = planes.plan_de(empresa.plan).value
    movimiento = cambio_de_plan(empresa, destino)
    lim_a, lim_d = planes.limites_de(actual), planes.limites_de(destino)
    cuota_actual, _ = cuota_de(empresa)
    precio_nuevo = mp_sus.precio_de(empresa, destino) if planes.se_vende_solo(planes.plan_de(destino)) else None
    est = estado_suscripcion(empresa, db)
    hoy = _hoy_negocio()

    if movimiento == "sube":
        # Mismo cálculo que registrar_pago: plan nuevo completo + 30 días.
        vence = empresa.suscripcion_vence
        base = vence if vence and vence >= hoy - dt.timedelta(days=DIAS_PRORROGA) else hoy
        nuevo_vence = base + dt.timedelta(days=DIAS_CICLO)
        aplica_desde = hoy
        a_pagar = precio_nuevo
    elif movimiento == "baja":
        nuevo_vence = empresa.suscripcion_vence
        aplica_desde = empresa.suscripcion_vence or hoy
        a_pagar = 0.0
    else:
        nuevo_vence, aplica_desde, a_pagar = empresa.suscripcion_vence, hoy, 0.0

    ganadas = sorted(lim_d.funciones - lim_a.funciones, key=lambda f: f.value)
    perdidas = sorted(lim_a.funciones - lim_d.funciones, key=lambda f: f.value)
    debito = mp_debito.vigente(db, empresa.id)
    return {
        "movimiento": movimiento,
        "plan_actual": actual,
        "plan_actual_etiqueta": lim_a.etiqueta,
        "plan_nuevo": destino,
        "plan_nuevo_etiqueta": lim_d.etiqueta,
        "precio_actual": cuota_actual,
        "precio_nuevo": precio_nuevo,
        "diferencia_mensual": (
            round(precio_nuevo - (cuota_actual or 0), 2) if precio_nuevo is not None else None
        ),
        "a_pagar_hoy": a_pagar,
        "aplica_desde": aplica_desde.isoformat() if aplica_desde else None,
        "vence_actual": empresa.suscripcion_vence.isoformat() if empresa.suscripcion_vence else None,
        "vence_nuevo": nuevo_vence.isoformat() if nuevo_vence else None,
        "inmediato": movimiento == "sube" or empresa.suscripcion_vence is None,
        "ganas": [ETIQUETA_FUNCION.get(f.value, f.value) for f in ganadas],
        "perdes": [ETIQUETA_FUNCION.get(f.value, f.value) for f in perdidas],
        "topes_actuales": topes_de(empresa, actual),
        "topes_nuevos": topes_de(empresa, destino),
        "uso": uso_actual(db, empresa),
        "incompatibilidades": incompatibilidades(db, empresa, destino) if movimiento == "baja" else [],
        "metodo_pago": "debito_automatico" if debito is not None and debito.estado == "authorized" else None,
        "estado": est["estado"],
        "se_vende_online": planes.se_vende_solo(planes.plan_de(destino)),
    }


def programar_baja(
    db: Session, empresa: Empresa, destino: str, hecho_por: str | None = None,
    actor_tipo: str = "dueno",
) -> dt.date | None:
    """Anota que al vencer el ciclo la empresa cae al plan `destino`.

    No toca el plan actual ni el vencimiento: el mes ya está pagado y se usa
    entero. Devuelve la fecha en que se va a aplicar.

    Si la empresa no tiene vencimiento (está en prueba, o es una cuenta
    bonificada) la baja se aplica ya, y por eso ahí SÍ se exige que lo que
    usa entre en el plan nuevo: aplicarla con 3 sucursales sobre un plan de 1
    es un estado imposible. Con ciclo pago se programa igual y se le muestra
    qué tiene que reducir antes de la fecha.
    """
    destino = planes.plan_de(destino).value
    if empresa.suscripcion_vence is None:
        problemas = incompatibilidades(db, empresa, destino)
        if problemas:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                " ".join(p["mensaje"] for p in problemas)
                + " Reducilo antes de cambiar de plan.",
            )
        antes = empresa.plan
        empresa.plan = destino
        empresa.plan_programado = None
        evento(
            db, empresa, "plan",
            f"Cambio de plan: {planes.limites_de(antes).etiqueta} → "
            f"{planes.limites_de(destino).etiqueta}",
            hecho_por=hecho_por, actor_tipo=actor_tipo, plan_antes=antes, plan_despues=destino,
        )
        db.flush()
        return None

    empresa.plan_programado = destino
    evento(
        db, empresa, "plan",
        f"Baja programada a {planes.limites_de(destino).etiqueta} "
        f"para el {empresa.suscripcion_vence.strftime('%d/%m/%Y')}",
        hecho_por=hecho_por, actor_tipo=actor_tipo,
        plan_antes=empresa.plan, plan_despues=destino,
    )
    db.flush()
    return empresa.suscripcion_vence


def cancelar_baja_programada(
    db: Session, empresa: Empresa, hecho_por: str | None = None, actor_tipo: str = "dueno"
) -> None:
    """Se arrepintió. Sigue en el plan que tiene."""
    if empresa.plan_programado is None:
        return
    destino = empresa.plan_programado
    empresa.plan_programado = None
    evento(
        db, empresa, "plan",
        f"Se canceló la baja a {planes.limites_de(destino).etiqueta}",
        hecho_por=hecho_por, actor_tipo=actor_tipo,
        plan_antes=empresa.plan, plan_despues=empresa.plan,
    )
    db.flush()


def aplicar_bajas_programadas(db: Session, hoy: dt.date | None = None) -> int:
    """Baja de plan a las empresas cuyo ciclo ya venció. Devuelve cuántas.

    Lo corre el barrido diario. Es idempotente: al aplicarla se limpia
    `plan_programado`.

    SI TODAVÍA USA MÁS DE LO QUE EL PLAN NUEVO PERMITE, NO SE APLICA: queda
    programada, se registra el motivo (una vez por día) y sigue en el plan que
    tiene. Aplicarla igual dejaría, por ejemplo, 3 sucursales activas en un
    plan de 1.
    """
    from app.services import mp_debito

    hoy = hoy or _hoy_negocio()
    pendientes = list(
        db.scalars(
            select(Empresa).where(
                Empresa.plan_programado.is_not(None),
                Empresa.suscripcion_vence.is_not(None),
                Empresa.suscripcion_vence <= hoy,
            )
        )
    )
    aplicadas = []
    for empresa in pendientes:
        problemas = incompatibilidades(db, empresa, empresa.plan_programado)
        if problemas:
            marca = f"baja_postergada {hoy.isoformat()}"
            ya = db.scalar(select(AjusteSuscripcion.id).where(
                AjusteSuscripcion.empresa_id == empresa.id,
                AjusteSuscripcion.tipo == "baja_postergada",
                AjusteSuscripcion.detalle.like(f"%{marca}%"),
            ))
            if ya is None:
                evento(
                    db, empresa, "baja_postergada",
                    f"No se aplicó la baja a {planes.limites_de(empresa.plan_programado).etiqueta}: "
                    + " ".join(p["mensaje"] for p in problemas) + f" ({marca})",
                    hecho_por="sistema", actor_tipo="sistema",
                )
            continue
        antes = empresa.plan
        empresa.plan = empresa.plan_programado
        empresa.plan_programado = None
        evento(
            db, empresa, "plan",
            f"Baja aplicada: {planes.limites_de(antes).etiqueta} → "
            f"{planes.limites_de(empresa.plan).etiqueta}",
            hecho_por="sistema", actor_tipo="sistema", plan_antes=antes, plan_despues=empresa.plan,
        )
        aplicadas.append(empresa)
    db.commit()
    # El débito automático cobra el monto viejo hasta que se le avise.
    for empresa in aplicadas:
        mp_debito.ajustar_al_plan(db, empresa)
    return len(aplicadas)


# ══════════════════════════════════════════════════════════════════════
#  Cancelación y reactivación de la suscripción
# ══════════════════════════════════════════════════════════════════════


def cancelar_suscripcion(
    db: Session, empresa: Empresa, *, motivo: str | None, hecho_por: str, actor_tipo: str
) -> dict:
    """El negocio (o el super-admin) cancela la suscripción.

    NO corta nada en el momento ni borra datos: el ciclo pago (o la prueba) se
    usa entero y al vencer la suscripción pasa a CANCELADA. Si no hay ciclo
    que respetar, se cancela ya.

    El débito automático se corta PRIMERO en Mercado Pago: si eso falla no se
    cancela nada, porque una suscripción «cancelada» que MP sigue cobrando es
    el peor error posible.
    """
    from app.core import estados_suscripcion as est_sus
    from app.services import mp_debito

    estado_antes = _estado(db, empresa)
    est_sus.exigir(estado_antes, "cancelar")

    debito = mp_debito.vigente(db, empresa.id)
    if debito is not None and not mp_debito.cancelar(db, empresa.id, quien=hecho_por):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No pudimos cortar el débito automático en Mercado Pago, así que no "
            "cancelamos nada. Probá de nuevo en unos minutos.",
        )

    ahora = dt.datetime.now(dt.UTC)
    hoy = _hoy_negocio()
    empresa.cancela_al_vencer = True
    empresa.cancelacion_solicitada_en = ahora
    empresa.cancelacion_motivo = (motivo or "").strip()[:300] or None
    empresa.plan_programado = None
    fin = max(d for d in (empresa.suscripcion_vence, empresa.prueba_hasta) if d) if (
        empresa.suscripcion_vence or empresa.prueba_hasta
    ) else None
    if fin is None or fin < hoy:
        empresa.cancelada_en = ahora
    evento(
        db, empresa, "cancelacion",
        (f"Cancelación pedida · activa hasta el {fin.strftime('%d/%m/%Y')}"
         if empresa.cancelada_en is None and fin else "Suscripción cancelada")
        + (f" · motivo: {empresa.cancelacion_motivo}" if empresa.cancelacion_motivo else ""),
        hecho_por=hecho_por, actor_tipo=actor_tipo,
        estado_antes=estado_antes, estado_despues=_estado(db, empresa),
    )
    db.commit()
    return {
        "estado": _estado(db, empresa),
        "activa_hasta": fin.isoformat() if fin and empresa.cancelada_en is None else None,
    }


def reactivar_suscripcion(
    db: Session, empresa: Empresa, *, hecho_por: str, actor_tipo: str
) -> dict:
    """Deshace la cancelación. Si el ciclo ya terminó, queda vencida y paga."""
    from app.core import estados_suscripcion as est_sus

    estado_antes = _estado(db, empresa)
    est_sus.exigir(estado_antes, "reactivar")
    empresa.cancela_al_vencer = False
    empresa.cancelada_en = None
    empresa.cancelacion_solicitada_en = None
    empresa.cancelacion_motivo = None
    evento(
        db, empresa, "reactivacion", "Se deshizo la cancelación",
        hecho_por=hecho_por, actor_tipo=actor_tipo,
        estado_antes=estado_antes, estado_despues=_estado(db, empresa),
    )
    db.commit()
    return {"estado": _estado(db, empresa)}


def aplicar_cancelaciones(db: Session, hoy: dt.date | None = None) -> int:
    """Barrido diario: anota como efectivas las cancelaciones cuyo ciclo terminó."""
    hoy = hoy or _hoy_negocio()
    ahora = dt.datetime.now(dt.UTC)
    n = 0
    for empresa in db.scalars(
        select(Empresa).where(Empresa.cancela_al_vencer.is_(True), Empresa.cancelada_en.is_(None))
    ):
        fin = max(d for d in (empresa.suscripcion_vence, empresa.prueba_hasta) if d) if (
            empresa.suscripcion_vence or empresa.prueba_hasta
        ) else None
        if fin is not None and fin >= hoy:
            continue
        empresa.cancelada_en = ahora
        evento(db, empresa, "cancelada", "La cancelación se hizo efectiva",
               hecho_por="sistema", actor_tipo="sistema",
               estado_antes="cancelacion_programada", estado_despues="cancelada")
        n += 1
    db.commit()
    return n


def suspender(db: Session, empresa: Empresa, *, activa: bool, hecho_por: str, motivo: str | None = None) -> None:
    """Pausa o reanuda la cuenta (super-admin). Corta el acceso, no los datos."""
    from app.core import estados_suscripcion as est_sus

    estado_antes = _estado(db, empresa)
    est_sus.exigir(estado_antes, "reanudar" if activa else "suspender")
    empresa.activa = activa
    evento(
        db, empresa, "reanudacion" if activa else "suspension",
        ("Cuenta reanudada" if activa else "Cuenta suspendida")
        + (f" · {motivo.strip()[:200]}" if motivo and motivo.strip() else ""),
        hecho_por=hecho_por, actor_tipo="admin",
        estado_antes=estado_antes, estado_despues=_estado(db, empresa),
    )
