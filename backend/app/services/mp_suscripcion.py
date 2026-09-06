"""Cobro de la CUOTA DEL SAAS por Mercado Pago (la cuenta de Turnos360).

NO CONFUNDIR CON app/services/mercadopago.py
────────────────────────────────────────────
Son dos Mercado Pago distintos y es la confusión más cara que se puede tener
acá adentro:

  · `mercadopago.py`  → el MP de CADA NEGOCIO. Cobra la seña de un turno a SU
    cliente final. El token vive cifrado en `empresa.mp_credenciales`, hay uno
    por empresa, y el webhook entra por /publico/mp/webhook/{slug}.

  · este archivo      → el MP de TURNOS360. Cobra la cuota mensual a cada
    negocio. El token es UNO SOLO y sale del entorno
    (`MP_SAAS_ACCESS_TOKEN`). El webhook entra por
    /publico/mp/webhook-suscripcion, sin slug, porque la cuenta es la misma
    para todos.

Meterle el token equivocado a una preferencia significa cobrarle a la cuenta
que no es. Por eso el token nunca se pasa por parámetro: se lee acá.

APAGADO POR DEFECTO
───────────────────
Sin `MP_SAAS_ACCESS_TOKEN`, `esta_activo()` da False, el botón no aparece en
"Mi suscripción" y el webhook contesta 503. Es a propósito: los avisos de
Mercado Pago necesitan una URL pública con HTTPS, y en un staging por VPN no
llegan nunca. Un cobro que entra y que nadie acredita es peor que no ofrecer
el botón.
"""

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.planes import limites_de, plan_de, se_vende_solo
from app.models import Empresa, PagoSuscripcion

log = logging.getLogger("turnos360.mp_suscripcion")

MP_API = "https://api.mercadopago.com"
TIMEOUT = 15

# external_reference: "sus:<empresa_id>". El prefijo evita confundir esta
# notificación con la de una seña, cuyo external_reference es un id de turno
# pelado. Si algún día las dos cuentas fueran la misma, el prefijo es lo único
# que separa "me pagaron una cuota" de "le pagaron una seña a un negocio".
# El PLAN va en la referencia y no se deduce de la empresa a propósito: es el
# único dato que viaja con el pago y vuelve intacto en la notificación. Sin él,
# alguien en Inicial que paga Pro vuelve del checkout con la plata cobrada y el
# plan sin cambiar —para cuando llega el webhook, la empresa sigue diciendo
# "inicial"— y lo vive como que pagó y no le dieron nada.
#
# El plan es OPCIONAL en la expresión para que las notificaciones viejas
# ("sus:12", de antes de este cambio) se sigan acreditando. Sin ese `?`, un
# pago hecho ayer y reintentado hoy por Mercado Pago quedaría sin acreditar.
_REF = re.compile(r"^sus:(\d+)(?::([a-z]+))?$")


def esta_activo() -> bool:
    return bool(settings.mp_saas_access_token)


def referencia_de(empresa_id: int, plan: str | None = None) -> str:
    """La referencia que viaja con el pago y vuelve en la notificación."""
    return f"sus:{empresa_id}:{plan}" if plan else f"sus:{empresa_id}"


def empresa_de_referencia(ref: str | None) -> int | None:
    m = _REF.match((ref or "").strip())
    return int(m.group(1)) if m else None


def plan_de_referencia(ref: str | None) -> str | None:
    """Qué plan compró. None en las referencias viejas, que no lo llevaban."""
    m = _REF.match((ref or "").strip())
    return m.group(2) if m else None


def precio_de(empresa: Empresa, plan: str | None = None) -> float:
    """Cuánto se cobra: el precio pactado de esta empresa, o el del plan.

    EL PRECIO PACTADO MANDA, Y ES A PROPÓSITO
    `empresa.precio_mensual` es lo que el super-admin le puso en la ficha
    comercial: un precio especial, una cuenta bonificada, o el precio a medida
    de un Enterprise. Si existe, gana sobre la grilla — es exactamente para eso
    que existe la columna.

    `plan` es el que se está COMPRANDO, que puede no ser el que tiene: quien
    está en Inicial y toca «Pasar a Pro» tiene que pagar Pro. Por eso el plan
    comprado se mira antes que el plan actual, y solo si no vino ninguno se
    cae en la cuota que le corresponde hoy (`cuota_de`).

    El último recurso es el precio de lista, para el botón viejo de «renovar»
    de una empresa sin plan ni pactado. Nunca devuelve 0: cobrar cero por
    Mercado Pago es un error que MP rechaza y que acá se ve como un botón que
    no hace nada.
    """
    from app.services.suscripcion import cuota_de

    if empresa.precio_mensual is not None:
        return float(empresa.precio_mensual)
    if plan:
        limites = limites_de(plan)
        if limites.precio > 0:
            return float(limites.precio)
    monto, _origen = cuota_de(empresa)
    if monto:
        return float(monto)
    return float(settings.precio_vigente)


def crear_preferencia(empresa: Empresa, plan: str | None = None) -> str | None:
    """Preferencia de Checkout Pro para la cuota (o el cambio de plan).

    `plan` es el que el dueño eligió en «Mi suscripción». Viaja en el
    external_reference para que el webhook sepa qué comprar y lo active solo:
    esa es toda la diferencia entre un cobro automático y uno que necesita que
    alguien de Turnos360 lo mire.

    Devuelve el init_point (la URL a la que mandar al dueño), o None si el
    cobro por MP está apagado o la API falló.
    """
    if not esta_activo():
        return None

    monto = precio_de(empresa, plan)
    if monto <= 0:
        # Una cuenta bonificada no tiene nada que pagar.
        return None

    panel = f"{settings.public_base_url}/suscripcion"
    payload = {
        "items": [
            {
                "title": (
                    f"Turnos360 {limites_de(plan).etiqueta} · {empresa.nombre}"
                    if plan
                    else f"Turnos360 · cuota mensual ({empresa.nombre})"
                )[:120],
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": monto,
            }
        ],
        "external_reference": referencia_de(empresa.id, plan),
        "back_urls": {
            "success": f"{panel}?pago=aprobado",
            "pending": f"{panel}?pago=pendiente",
            "failure": f"{panel}?pago=rechazado",
        },
        "auto_return": "approved",
        "notification_url": f"{settings.api_base_url}/publico/mp/webhook-suscripcion",
        "statement_descriptor": "TURNOS360",
    }
    try:
        r = httpx.post(
            f"{MP_API}/checkout/preferences",
            json=payload,
            headers={"Authorization": f"Bearer {settings.mp_saas_access_token}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("init_point")
    except Exception:
        log.exception("MP SaaS: falló crear la preferencia (empresa %s)", empresa.id)
        return None


def consultar_pago(payment_id: str) -> dict | None:
    """Trae el pago desde la API con el token de Turnos360.

    Esta consulta ES la validación de autenticidad: un id inventado no existe
    en la cuenta y devuelve 404. La firma del webhook solo evita el tráfico
    saliente de notificaciones que ni siquiera vienen de Mercado Pago.
    """
    if not esta_activo():
        return None
    try:
        r = httpx.get(
            f"{MP_API}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {settings.mp_saas_access_token}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        log.exception("MP SaaS: falló consultar el pago %s", payment_id)
        return None


def ya_acreditado(db: Session, payment_id: str) -> bool:
    """¿Esta notificación ya se procesó? Mercado Pago reintenta varias veces."""
    return (
        db.scalar(
            select(PagoSuscripcion.id).where(
                PagoSuscripcion.mp_payment_id == str(payment_id)
            )
        )
        is not None
    )


def acreditar(db: Session, payment_id: str) -> PagoSuscripcion | None:
    """Procesa una notificación de pago de cuota. Nunca levanta.

    El orden importa: primero se corta por idempotencia (sin salir a la red),
    después se verifica contra la API, y recién ahí se toca la base.
    """
    from app.services import cobranza

    payment_id = str(payment_id)
    if ya_acreditado(db, payment_id):
        return None

    datos = consultar_pago(payment_id)
    if not datos or datos.get("status") != "approved":
        return None

    referencia = datos.get("external_reference")
    empresa_id = empresa_de_referencia(referencia)
    plan_comprado = plan_de_referencia(referencia)
    if empresa_id is None:
        log.warning(
            "MP SaaS: pago %s sin external_reference de suscripción (%r)",
            payment_id,
            datos.get("external_reference"),
        )
        return None

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        log.warning("MP SaaS: pago %s apunta a una empresa que no existe", payment_id)
        return None

    # El monto que se registra es el que MP confirmó, no el que esperábamos:
    # si el dueño pagó de menos, la cuota tiene que reflejar lo que entró.
    monto = float(datos.get("transaction_amount") or 0)

    # El plan que se compró se activa acá, sin que nadie lo toque. Es el punto
    # entero de este archivo: antes el pago entraba, el vencimiento se corría
    # 30 días y el plan quedaba como estaba, así que un upgrade a Pro cobraba
    # Pro y dejaba al negocio en Inicial hasta que alguien lo arreglara a mano.
    #
    # Se valida contra `se_vende_solo`: una referencia con un plan que no está
    # a la venta (o inventada) se ignora y el pago se acredita igual. Nunca al
    # revés — perder un pago acreditado es peor que no cambiar un plan.
    plan_a_activar = None
    if plan_comprado:
        candidato = plan_de(plan_comprado)
        if se_vende_solo(candidato):
            plan_a_activar = candidato.value
        else:
            log.warning(
                "MP SaaS: pago %s trae un plan que no se vende solo (%r)",
                payment_id,
                plan_comprado,
            )

    pago = cobranza.registrar_pago(
        db,
        empresa,
        monto=monto,
        metodo="mercadopago",
        notas=f"Acreditado por Mercado Pago (pago {payment_id})",
        registrado_por="mercadopago",
        renovar=True,
        plan=plan_a_activar,
    )
    pago.mp_payment_id = payment_id
    db.commit()
    log.info(
        "MP SaaS: cuota acreditada",
        extra={"empresa_id": empresa.id, "payment_id": payment_id, "monto": monto},
    )

    # El aviso a la casilla oficial. Con el cobro automatizado, un pago entra,
    # activa el plan y corre el vencimiento sin que nadie mire nada — que es el
    # punto del autoservicio, pero también significa poder pasar una semana sin
    # enterarse de si se cobró.
    #
    # Nunca puede tumbar la acreditación: la plata ya entró y el pago ya está
    # guardado. Si el mail falla, falla el mail.
    try:
        from app.core.cola import encolar
        from app.tasks.emails import avisar_pago_recibido

        encolar(
            avisar_pago_recibido,
            empresa.id,
            monto,
            "Mercado Pago",
            plan=plan_a_activar,
            referencia=f"pago {payment_id}",
            confirmado=True,
        )
    except Exception:
        log.exception("No se pudo avisar el pago %s", payment_id)

    return pago


# Qué significa cada estado de Mercado Pago, en castellano y sin ambigüedad.
# La clave es que «no approved» NO es todo lo mismo: un `pending` puede
# aprobarse solo en unas horas, un `rejected` no se aprueba nunca, y un
# `refunded` ES plata que estuvo y se devolvió. Tratarlos igual es lo que hace
# que una cuota devuelta siga contando como cobrada.
ESTADOS_MP: dict[str, dict[str, str]] = {
    "approved": {"etiqueta": "Acreditado", "color": "verde"},
    "authorized": {"etiqueta": "Autorizado, sin capturar", "color": "ambar"},
    "in_process": {"etiqueta": "En revisión", "color": "ambar"},
    "in_mediation": {"etiqueta": "En disputa", "color": "rojo"},
    "pending": {"etiqueta": "Pendiente", "color": "ambar"},
    "rejected": {"etiqueta": "Rechazado", "color": "rojo"},
    "cancelled": {"etiqueta": "Cancelado", "color": "rojo"},
    "refunded": {"etiqueta": "Devuelto", "color": "rojo"},
    "charged_back": {"etiqueta": "Contracargo", "color": "rojo"},
}


def verificar(db: Session, pago: PagoSuscripcion) -> dict:
    """Le pregunta a Mercado Pago qué pasó DE VERDAD con esta cuota.

    POR QUÉ HACE FALTA PREGUNTAR
    ────────────────────────────
    Lo planteó Leandro: «capaz no entro a Mercado Pago y se había marcado como
    cobrado». El webhook acredita solo, y eso es lo que queremos — pero
    después de acreditar, la fila de la base no vuelve a mirarse nunca. Si el
    pago se devolvió, se disputó o terminó en contracargo, Mercado Pago lo
    sabe y nosotros seguimos mostrando «cobrado» para siempre. El agujero no
    es que el webhook falle: es que lo que el webhook escribió no se revisa.

    Esto no toca nada. Devuelve lo que dice MP al lado de lo que dice nuestra
    base, y deja que decida una persona. Corregir automáticamente un pago
    porque una consulta HTTP salió mal —o volvió lenta, o el token venció— es
    peor que no revisar: borraría plata cobrada de verdad sin que nadie lo
    haya pedido.

    Nunca levanta: un problema de red no puede tumbar el panel de cobranza.
    """
    salida: dict = {
        "pago_id": pago.id,
        "mp_payment_id": pago.mp_payment_id,
        "monto_registrado": float(pago.monto),
        "anulado": bool(pago.anulado),
        # Los tres casos en los que NO hay nada que comparar, separados para
        # que la pantalla pueda decir por qué en vez de un "no se pudo".
        "consultable": False,
        "motivo": None,
        "estado": None,
        "estado_etiqueta": None,
        "color": "gris",
        "monto_mp": None,
        "coincide": None,
        "acreditado": None,
        "detalle": None,
    }

    if not pago.mp_payment_id:
        salida["motivo"] = "sin_id"
        salida["detalle"] = (
            "Esta cuota no entró por Mercado Pago, así que no hay nada que "
            "consultar. Si fue una transferencia, se verifica en el banco."
        )
        return salida

    if not esta_activo():
        salida["motivo"] = "mp_apagado"
        salida["detalle"] = (
            "Mercado Pago no está configurado en este entorno "
            "(falta MP_SAAS_ACCESS_TOKEN), así que no se puede consultar."
        )
        return salida

    datos = consultar_pago(pago.mp_payment_id)
    if datos is None:
        salida["motivo"] = "sin_respuesta"
        salida["detalle"] = (
            "Mercado Pago no respondió o el pago no existe en la cuenta. "
            "Probá de nuevo en un rato; si sigue igual, revisalo en el panel "
            "de Mercado Pago antes de tocar nada acá."
        )
        return salida

    estado = str(datos.get("status") or "").strip()
    info = ESTADOS_MP.get(estado, {"etiqueta": estado or "Desconocido", "color": "gris"})
    monto_mp = datos.get("transaction_amount")
    monto_mp = float(monto_mp) if monto_mp is not None else None

    salida.update(
        {
            "consultable": True,
            "estado": estado,
            "estado_etiqueta": info["etiqueta"],
            "color": info["color"],
            "monto_mp": monto_mp,
            "acreditado": estado == "approved",
            # Comparar los montos importa aparte del estado: un pago aprobado
            # por un importe distinto al registrado también es un problema, y
            # es el que nadie mira porque el semáforo está en verde.
            "coincide": (
                monto_mp is not None and abs(monto_mp - float(pago.monto)) < 1
            ),
            "detalle": datos.get("status_detail"),
        }
    )
    return salida
