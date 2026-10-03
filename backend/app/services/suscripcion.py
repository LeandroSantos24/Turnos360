"""Estado de la suscripción de una empresa.

Regla de negocio (definida por Leandro):
- La suscripción vence en una fecha (suscripcion_vence).
- Tras el vencimiento hay una PRÓRROGA (gracia) antes de considerarla vencida
  de verdad. Durante la prórroga el negocio sigue operando con normalidad,
  pero se le avisa que regularice.

POR QUÉ TRES DÍAS Y NO DIEZ
───────────────────────────
Eran diez. Leandro los bajó a tres al rehacer el cobro: «nosotros damos 3 días
de período de gracia». Con el débito automático la prórroga deja de ser el
tiempo que tarda alguien en acordarse de transferir y pasa a ser el colchón
para un problema puntual —una tarjeta vencida, un límite—, que es una ventana
mucho más corta.

EL NÚMERO NO SE ESCRIBE EN NINGÚN OTRO LADO
───────────────────────────────────────────
Todo lo que dependa de la prórroga —los correos de aviso, los textos del
panel, el semáforo de cobranza, desde dónde se cuentan los 30 días del ciclo
siguiente, cuándo se cortan las reservas— se calcula a partir de esta
constante. Estuvo escrito a mano en los asuntos de los mails («te quedan 7
días»), y bajarlo de diez a tres los habría dejado mintiendo sin que nada
fallara.
"""

import datetime as dt

from app.models.organizacion import Empresa

DIAS_PRORROGA = 3


# ══════════════════════════════════════════════════════════════════════════
#  Cuánto paga esta empresa por mes
# ══════════════════════════════════════════════════════════════════════════
#
# EL BUG QUE ORIGINÓ ESTA FUNCIÓN
# ───────────────────────────────
# Leandro abrió el panel de uno de sus negocios de prueba y vio «$14.990»
# donde la grilla decía $13.900: «esto es muy mal, no sale 14990, habíamos
# quedado en 13900».
#
# El número no estaba mal escrito en ningún lado. Al registrarse, la empresa
# copiaba el precio de lista del momento a `empresa.precio_mensual` — una foto
# del precio, tomada el día del alta, de un negocio que todavía no había
# comprado nada. Esa empresa se había creado cuando el default del compose era
# 14990. Meses después la grilla decía otra cosa y la foto seguía ahí,
# contradiciendo a la grilla en la misma pantalla.
#
# La foto no se podía arreglar cambiándole el valor: el problema no es el
# número, es que exista. Un precio congelado el día del alta empieza a mentir
# el día que la lista se mueve, y nadie se entera hasta que un cliente lo lee.
#
# QUÉ SIGNIFICA AHORA CADA COSA
# ─────────────────────────────
#   · `empresa.precio_mensual` = PRECIO PACTADO. NULL salvo que el super-admin
#     le haya puesto uno distinto del de lista (un piloto bonificado, un
#     descuento por referido, un Enterprise a medida). Es lo que la columna
#     siempre quiso decir.
#   · el precio del plan (grilla) = lo que paga todo el mundo.
#
# Con eso, el precio de una empresa sin trato especial sigue a la grilla solo,
# y cambiar la grilla no deja pantallas viejas atrás.


def cuota_de(empresa: Empresa) -> tuple[float | None, str]:
    """Cuánto paga por mes, y de dónde sale ese número.

    Devuelve `(monto, origen)` con origen en:
      · "pactada"     → precio especial cargado en la ficha comercial
      · "plan"        → el de lista del plan que tiene
      · "sin_precio"  → no le corresponde pagar (prueba, Enterprise sin pactar)

    El origen viaja junto al monto porque la pantalla dice cosas distintas
    según cuál sea: un precio pactado no se puede presentar como "el precio de
    tu plan", y un Enterprise sin precio cargado necesita decir «hablemos» en
    lugar de "$0".
    """
    from app.core import planes

    if empresa.precio_mensual is not None:
        return float(empresa.precio_mensual), "pactada"

    lim = planes.limites_de(empresa.plan)
    # precio 0 en la grilla = a convenir (Enterprise) o no se vende (la
    # prueba). En los dos casos NO hay una cuota que mostrar, y devolver 0.0
    # haría que el panel dijera "$0 por mes" a alguien que va a pagar.
    if lim.precio > 0:
        return float(lim.precio), "plan"
    return None, "sin_precio"


def _hoy() -> dt.date:
    """Hoy en la zona del negocio (en UTC, a las 21 ya es mañana)."""
    from app.core.reloj import hoy_de_pared

    return hoy_de_pared()


def _plural(n: int, palabra: str) -> str:
    return f"{n} {palabra}{'s' if n != 1 else ''}"


def estado_suscripcion(
    empresa: Empresa,
    db=None,
    hoy: dt.date | None = None,
    *,
    en_revision: bool | None = None,
    pago_pendiente: bool | None = None,
) -> dict:
    """EL estado de la suscripción. La única función que lo decide.

    Sin `db` calcula el ciclo de vida a partir de las fechas. Con `db` además
    superpone lo que está en curso: un aviso de transferencia en revisión o un
    pago de Mercado Pago pendiente (ver core/estados_suscripcion.py).

    Devuelve las claves de siempre (`estado`, `vence`, `mensaje`, `corte`…) más
    `etiqueta`, `tono`, `reservas_abiertas` y `estado_base` (sin superponer).
    """
    from app.core.estados_suscripcion import ETIQUETAS, EstadoSuscripcion as E

    plan = empresa.plan or "gratuito"
    hoy = hoy or _hoy()
    vence = empresa.suscripcion_vence
    prueba = empresa.prueba_hasta
    corte: dt.date | None = None
    vence_mostrar = vence
    dias = (vence - hoy).days if vence else None

    # Hasta cuándo dura lo que ya está cubierto (ciclo pago o prueba).
    fin_ciclo = max(d for d in (vence, prueba) if d is not None) if (vence or prueba) else None

    if not empresa.activa:
        estado, mensaje = E.SUSPENDED, "Tu cuenta está suspendida. Escribinos para reactivarla."
    elif empresa.cancela_al_vencer and (
        empresa.cancelada_en is not None or fin_ciclo is None or hoy > fin_ciclo
    ):
        estado = E.CANCELED
        mensaje = "Tu suscripción está cancelada. Tus datos siguen guardados."
        vence_mostrar = fin_ciclo
    elif prueba is not None and hoy <= prueba and (vence is None or vence <= prueba):
        vence_mostrar = prueba
        restantes = (prueba - hoy).days
        dias = restantes
        if empresa.cancela_al_vencer:
            estado = E.CANCEL_PENDING
            mensaje = f"Cancelaste la prueba: termina el {prueba.strftime('%d/%m/%Y')}"
        else:
            estado = E.TRIAL
            mensaje = (
                "Último día de prueba"
                if restantes == 0
                else f"Te quedan {_plural(restantes, 'día')} de prueba"
            )
    elif vence is None:
        if prueba is not None:
            # Terminó la prueba sin pagar: misma gracia que una cuota vencida
            # y después la página deja de tomar reservas.
            estado = E.EXPIRED
            corte = prueba + dt.timedelta(days=DIAS_PRORROGA)
            vence_mostrar = prueba
            if hoy <= corte:
                quedan = (corte - hoy).days
                mensaje = (
                    f"Terminó tu prueba · {_plural(quedan, 'día')} para elegir un plan "
                    "sin que se corte nada"
                )
            else:
                mensaje = "Terminó tu prueba. Elegí un plan para seguir tomando reservas."
        else:
            estado = E.NO_DUE_DATE
            mensaje = "Plan gratuito" if plan == "gratuito" else "Sin vencimiento"
    else:
        corte = vence + dt.timedelta(days=DIAS_PRORROGA)
        if hoy <= vence:
            if empresa.cancela_al_vencer:
                estado = E.CANCEL_PENDING
                mensaje = f"Cancelación programada · activa hasta el {vence.strftime('%d/%m/%Y')}"
                corte = None
            else:
                estado = E.ACTIVE
                mensaje = (
                    f"Activa · vence en {_plural(dias, 'día')}" if dias > 0 else "Activa · vence hoy"
                )
        elif hoy <= corte:
            estado = E.GRACE_PERIOD
            mensaje = (
                f"Venció · {_plural((corte - hoy).days, 'día')} de gracia para regularizar"
            )
        else:
            estado = E.PAST_DUE
            mensaje = "Suscripción vencida"

    base = estado
    # Superpuestos: el negocio ya hizo su parte y estamos esperando. Con `db`
    # se consulta; sin `db` se usan los flags que pasa quien ya los calculó en
    # lote (el listado de cobranza, para no hacer una consulta por empresa).
    if estado in (E.GRACE_PERIOD, E.PAST_DUE, E.EXPIRED):
        aviso_estado = None
        if db is not None:
            from app.services import cobranza

            aviso = cobranza.aviso_abierto(db, empresa.id)
            aviso_estado = aviso.estado if aviso is not None else None
            if pago_pendiente is None:
                pago_pendiente = _pago_mp_en_curso(db, empresa.id, hoy)
        elif en_revision:
            aviso_estado = "pendiente"
        if aviso_estado is not None:
            estado = E.PAYMENT_REVIEW
            mensaje = (
                "Necesitamos un dato para confirmar tu pago"
                if aviso_estado == "info_solicitada"
                else "Estamos verificando tu pago"
            )
        elif pago_pendiente:
            estado = E.PAYMENT_PENDING
            mensaje = "Tu pago en Mercado Pago todavía no se acreditó"

    # Reservas web: se cierran recién pasada la gracia. Mientras un pago está
    # en revisión NO se cortan: el negocio ya hizo su parte.
    cerrada = base in (E.CANCELED, E.SUSPENDED) or (
        base in (E.PAST_DUE, E.EXPIRED) and corte is not None and hoy > corte
        and estado not in (E.PAYMENT_REVIEW,)
    )

    etiqueta, tono = ETIQUETAS[estado]
    return {
        "plan": plan,
        "estado": estado.value,
        "estado_base": base.value,
        "etiqueta": etiqueta,
        "tono": tono,
        "vence": str(vence_mostrar) if vence_mostrar else None,
        "dias_restantes": dias,
        "en_prorroga": base is E.GRACE_PERIOD or (
            base is E.EXPIRED and corte is not None and hoy <= corte
        ),
        "mensaje": mensaje,
        # Hasta cuándo puede pagar sin que se le corte el servicio.
        "corte": str(corte) if corte else None,
        "dias_hasta_corte": (corte - hoy).days if corte else None,
        "reservas_abiertas": not cerrada,
    }


def _pago_mp_en_curso(db, empresa_id: int, hoy: dt.date) -> bool:
    """¿Hay un pago de Mercado Pago iniciado o pendiente de los últimos días?"""
    from sqlalchemy import select

    from app.models.saas import IntentoPago

    desde = dt.datetime.combine(hoy - dt.timedelta(days=3), dt.time.min, tzinfo=dt.timezone.utc)
    return (
        db.scalar(
            select(IntentoPago.id).where(
                IntentoPago.empresa_id == empresa_id,
                IntentoPago.estado == "pendiente",
                IntentoPago.creado_en >= desde,
            ).limit(1)
        )
        is not None
    )


def reservas_abiertas(db, empresa: Empresa) -> bool:
    return estado_suscripcion(empresa, db)["reservas_abiertas"]


def _fmt(d) -> str | None:
    return str(d) if d else None


METODOS = {
    "transferencia": "Transferencia bancaria",
    "mercadopago": "Mercado Pago",
    "debito_automatico": "Débito automático (Mercado Pago)",
    "efectivo": "Efectivo",
}
TIPOS_PAGO = {
    "alta": "Pago inicial",
    "renovacion": "Renovación",
    "cambio_plan": "Cambio de plan",
    "reactivacion": "Reactivación",
    "manual": "Pago",
}
# Lo que el negocio ve de su historial. Sin quién (emails del equipo de
# Turnos360) ni apuntes internos.
EVENTOS_VISIBLES = {
    "pago": "Pago acreditado",
    "plan": "Plan",
    "cancelacion": "Cancelación",
    "reactivacion": "Reactivación",
    "cancelada": "Cancelación efectiva",
    "suspension": "Suspensión",
    "reanudacion": "Reanudación",
    "aviso": "Transferencia informada",
    "aviso_rechazado": "Transferencia rechazada",
    "info_solicitada": "Te pedimos información",
    "pago_rechazado": "Pago rechazado",
    "pago_devuelto": "Pago devuelto",
    "baja_postergada": "Baja de plan postergada",
    "prorroga": "Días de gracia",
    "renovacion": "Renovación",
    "manual": "Vencimiento ajustado",
    "reversion": "Corrección",
}


def mi_suscripcion(db, empresa_id: int) -> dict:
    """Vista de la suscripción PARA EL NEGOCIO (pantalla "Mi suscripción").

    Distinta de la del super-admin: acá el negocio ve lo suyo y nada más. No
    se exponen `notas`, `registrado_por` ni quién del equipo de Turnos360 hizo
    cada cosa.
    """
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.saas import AjusteSuscripcion, AvisoPago, IntentoPago, PagoSuscripcion
    from app.core import planes
    from app.services import cobranza
    from app.services import mp_debito
    from app.services import mp_suscripcion as mp_sus

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return {}

    estado = estado_suscripcion(empresa, db)
    uso = cobranza.uso_actual(db, empresa)
    plan_vigente = planes.plan_de(empresa.plan).value
    topes = cobranza.topes_de(empresa, plan_vigente)

    pagos = list(
        db.scalars(
            select(PagoSuscripcion)
            .where(PagoSuscripcion.empresa_id == empresa_id, PagoSuscripcion.anulado.is_(False))
            .order_by(PagoSuscripcion.fecha.desc(), PagoSuscripcion.id.desc())
            .limit(24)
        )
    )
    cuota, cuota_origen = cuota_de(empresa)
    debito = mp_debito.para_mostrar(db, empresa_id)
    debito_ok = bool(debito and debito["estado"] == "authorized")

    # Método y estado del pago, separados (no es lo mismo «transferencia» que
    # «en revisión»).
    metodo = "debito_automatico" if debito_ok else (pagos[0].metodo if pagos else None)
    aviso = cobranza.aviso_abierto(db, empresa_id)
    hace_30 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    rechazado = None
    if aviso is None:
        rechazado = db.scalar(
            select(AvisoPago).where(
                AvisoPago.empresa_id == empresa_id, AvisoPago.estado == "rechazada",
                AvisoPago.resuelto_en >= hace_30,
            ).order_by(AvisoPago.resuelto_en.desc()).limit(1)
        )
        if rechazado is not None and pagos and pagos[0].creado_en and rechazado.resuelto_en and pagos[0].creado_en > rechazado.resuelto_en:
            rechazado = None
    intento = db.scalar(
        select(IntentoPago).where(
            IntentoPago.empresa_id == empresa_id,
            IntentoPago.creado_en >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7),
        ).order_by(IntentoPago.id.desc()).limit(1)
    )
    if intento is not None and intento.estado not in ("rechazado", "pendiente"):
        intento = None

    if aviso is not None:
        estado_pago = "info_solicitada" if aviso.estado == "info_solicitada" else "en_revision"
    elif intento is not None:
        estado_pago = "rechazado" if intento.estado == "rechazado" else "pendiente"
    elif debito and debito.get("cobros_fallidos"):
        estado_pago = "rechazado"
    elif rechazado is not None:
        estado_pago = "rechazado"
    elif estado["estado_base"] in ("prorroga", "vencida", "prueba_vencida"):
        estado_pago = "adeuda"
    else:
        estado_pago = "al_dia"

    cancelacion = None
    if empresa.cancela_al_vencer:
        fin = estado["vence"]
        cancelacion = {
            "efectiva": estado["estado"] == "cancelada",
            "solicitada_en": (
                empresa.cancelacion_solicitada_en.isoformat()
                if empresa.cancelacion_solicitada_en else None
            ),
            "activa_hasta": fin,
            "motivo": empresa.cancelacion_motivo,
        }

    eventos = list(
        db.scalars(
            select(AjusteSuscripcion)
            .where(
                AjusteSuscripcion.empresa_id == empresa_id,
                AjusteSuscripcion.tipo.in_(tuple(EVENTOS_VISIBLES)),
            )
            .order_by(AjusteSuscripcion.creado_en.desc(), AjusteSuscripcion.id.desc())
            .limit(12)
        )
    )

    renueva = None if empresa.cancela_al_vencer else (
        str(empresa.suscripcion_vence) if empresa.suscripcion_vence else None
    )

    return {
        **estado,
        "cuota": cuota,
        "cuota_origen": cuota_origen,
        "precio_mensual": cuota,
        "precio_pactado": empresa.precio_mensual is not None,
        "ultimo_monto": float(pagos[0].monto) if pagos else None,
        "precio_lista": float(settings.precio_vigente),
        "precio_entrada": float(planes.GRILLA[planes.PLAN_DE_ENTRADA].precio),
        "plan_etiqueta": planes.limites_de(empresa.plan).etiqueta,
        "plan_resumen": planes.limites_de(empresa.plan).resumen,
        "profesionales_usados": uso["profesionales"],
        "profesionales_tope": topes["profesionales"],
        "uso": uso,
        "topes": topes,
        "grilla": planes.para_mostrar(),
        "plan_codigo": plan_vigente,
        "plan_programado": empresa.plan_programado,
        "plan_programado_etiqueta": (
            planes.limites_de(empresa.plan_programado).etiqueta
            if empresa.plan_programado
            else None
        ),
        "mp_disponible": mp_sus.esta_activo(),
        "debito": debito,
        "debito_disponible": mp_debito.esta_activo(),
        "dias_prorroga": DIAS_PRORROGA,
        "metodo_pago": metodo,
        "metodo_pago_etiqueta": METODOS.get(metodo or "", metodo),
        "estado_pago": estado_pago,
        "proxima_renovacion": renueva,
        "renovacion_automatica": debito_ok and not empresa.cancela_al_vencer,
        "ultimo_pago": (
            {
                "fecha": _fmt(pagos[0].fecha),
                "monto": float(pagos[0].monto),
                "metodo": METODOS.get(pagos[0].metodo, pagos[0].metodo),
                "tipo": TIPOS_PAGO.get(pagos[0].tipo or "", "Pago"),
            }
            if pagos else None
        ),
        "aviso": (
            {
                "estado": aviso.estado,
                "monto": float(aviso.monto) if aviso.monto is not None else None,
                "monto_esperado": float(aviso.monto_esperado) if aviso.monto_esperado is not None else None,
                "plan_etiqueta": planes.limites_de(aviso.plan).etiqueta if aviso.plan else None,
                "creado_en": aviso.creado_en.isoformat() if aviso.creado_en else None,
                "mensaje_admin": aviso.mensaje_admin,
                "referencia": aviso.referencia,
                "tiene_comprobante": bool(aviso.comprobante),
            }
            if aviso is not None else None
        ),
        "aviso_rechazado": (
            {
                "motivo": rechazado.motivo,
                "fecha": rechazado.resuelto_en.isoformat() if rechazado.resuelto_en else None,
                "monto": float(rechazado.monto) if rechazado.monto is not None else None,
            }
            if rechazado is not None else None
        ),
        "ultimo_intento": (
            {
                "estado": intento.estado,
                "monto": float(intento.monto),
                "plan_etiqueta": planes.limites_de(intento.plan).etiqueta if intento.plan else None,
                "fecha": intento.creado_en.isoformat() if intento.creado_en else None,
            }
            if intento is not None else None
        ),
        "cancelacion": cancelacion,
        "actividad": [
            {
                "tipo": ev.tipo,
                "titulo": EVENTOS_VISIBLES.get(ev.tipo, ev.tipo),
                "detalle": ev.detalle,
                "fecha": ev.creado_en.isoformat() if ev.creado_en else None,
                "quien": {"dueno": "Vos", "admin": "Turnos360", "sistema": "Automático",
                          "mercadopago": "Mercado Pago"}.get(ev.actor_tipo or "", "Turnos360"),
                "monto": float(ev.monto) if ev.monto is not None else None,
            }
            for ev in eventos
        ],
        "pagos": [
            {
                "fecha": _fmt(p.fecha),
                "monto": float(p.monto),
                "metodo": METODOS.get(p.metodo, p.metodo),
                "periodo_desde": _fmt(p.periodo_desde),
                "periodo_hasta": _fmt(p.periodo_hasta),
                "tipo": p.tipo,
                "tipo_etiqueta": TIPOS_PAGO.get(p.tipo or "", "Pago"),
                "plan_etiqueta": planes.limites_de(p.plan).etiqueta if p.plan else None,
                "estado": "aprobado",
            }
            for p in pagos
        ],
        # Concepto sugerido para la transferencia: con esto se la encuentra
        # en el resumen del banco sin adivinar de quién es.
        "referencia_transferencia": f"T360-{empresa_id}",
        "fecha_limite_pago": estado.get("corte") or estado.get("vence"),
        "cobro": {
            "cbu": settings.cobro_cbu or None,
            "alias": settings.cobro_alias or None,
            "titular": settings.cobro_titular or None,
            "cuit": settings.cobro_cuit or None,
            "banco": settings.cobro_banco or None,
            "mp_link": settings.cobro_mp_link or None,
            "mp_checkout": mp_sus.esta_activo(),
            "whatsapp": settings.cobro_whatsapp or None,
        },
    }
