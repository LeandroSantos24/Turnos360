"""Débito automático de la cuota: la suscripción recurrente de Mercado Pago.

QUÉ RESUELVE
────────────
Leandro lo pidió así: «hacé bien la parte de cobros, basate en Netflix,
Spotify, algo así que pagás suscripción y listo». Eso es exactamente lo que
falta hoy: el negocio pone la tarjeta una vez y no vuelve a pensar en la
cuota. Lo que había —transferir y avisar, o pagar un link de Mercado Pago
todos los meses— es cobranza manual con pasos automáticos, y el trabajo
manual que queda es de los dos lados: el negocio se tiene que acordar, y
Turnos360 tiene que ir a buscar al que no se acordó.

CÓMO SE LLAMA CADA COSA EN MERCADO PAGO
───────────────────────────────────────
  · `preference`  → un pago suelto. Cobra UNA vez. Es lo que hace
    `mp_suscripcion.py`, que sigue existiendo: es el pago manual.
  · `preapproval` → una SUSCRIPCIÓN. Queda viva y cobra todos los meses hasta
    que alguien la corta. Es esto.
  · `authorized_payment` → cada uno de los cobros mensuales que genera un
    preapproval. Es la "factura" del mes, y adentro trae el pago de verdad.

EL FLUJO, DE PUNTA A PUNTA
──────────────────────────
  1. El dueño elige un plan y toca «Activar débito automático».
  2. `crear()` hace POST /preapproval con `status: "pending"` y SIN tarjeta.
     Mercado Pago devuelve un `init_point`: una URL de checkout.
  3. Se lo manda ahí. Pone la tarjeta EN MERCADO PAGO —nunca acá— y vuelve.
  4. La suscripción pasa a `authorized` y Mercado Pago empieza a cobrar.
  5. Cada mes llega un webhook `subscription_authorized_payment`.
     `acreditar_cobro()` lo verifica contra la API y corre el vencimiento.

POR QUÉ EL FLUJO "PENDING" Y NO EL DE TARJETA
─────────────────────────────────────────────
Mercado Pago tiene otro camino: tokenizar la tarjeta en NUESTRO frontend y
mandarla en la creación (`card_token_id` + `status: "authorized"`). Da un
paso menos, y a cambio hace que los datos de la tarjeta pasen por nuestra
página. Eso cambia de categoría el proyecto entero —qué se audita, qué se
guarda, qué pasa si el bundle se compromete— a cambio de ahorrar un redirect
que la gente ya conoce de comprar en cualquier lado. No vale la pena.

Ese camino, además, es OBLIGATORIO si se usa un `preapproval_plan` (un plan
guardado en la cuenta de MP). Por eso acá las suscripciones se crean sin plan
asociado: es lo único que habilita el redirect.

QUÉ HACE MERCADO PAGO SOLO, Y QUÉ TENEMOS QUE HACER NOSOTROS
────────────────────────────────────────────────────────────
Cuando un cobro sale rechazado, Mercado Pago reintenta por su cuenta —según
su documentación, hasta cuatro veces dentro de unos diez días— y da de baja
la suscripción sola después de tres ciclos rechazados.

Entonces NO hay que programar reintentos acá: duplicarlos sería cobrarle dos
veces a alguien cuya tarjeta volvió a andar. Lo que sí hay que hacer es
avisarle al dueño, que es lo único que puede destrabarlo, y notar la baja
cuando Mercado Pago la hace.

OJO CON LA PRÓRROGA: son 3 días (DIAS_PRORROGA) y los reintentos de Mercado
Pago pueden tardar más. Un negocio con la tarjeta vencida puede quedar
cortado mientras MP todavía está reintentando. Por eso el panel, cuando hay
un cobro fallido, ofrece pagar a mano en el acto: la salida no puede ser
esperar a que a MP le salga bien.

APAGADO POR DEFECTO
───────────────────
Sin `MP_SAAS_ACCESS_TOKEN` nada de esto existe: `esta_activo()` da False y el
panel no ofrece el botón. Es el mismo criterio que el resto del cobro por MP —
los webhooks necesitan una URL pública con HTTPS, y un cobro que entra y que
nadie acredita es peor que no ofrecer el botón.
"""

import datetime as dt
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.planes import limites_de, plan_de, se_vende_solo
from app.models import DebitoAutomatico, Empresa

log = logging.getLogger("turnos360.mp_debito")

MP_API = "https://api.mercadopago.com"
TIMEOUT = 15

# Los estados que Mercado Pago le pone a un preapproval. Se guardan crudos.
PENDIENTE = "pending"
ACTIVO = "authorized"
PAUSADO = "paused"
CANCELADO = "cancelled"

# Los que cuentan como "esta suscripción todavía existe". El índice único
# parcial de la base usa exactamente este criterio (estado <> 'cancelled'):
# si esta tupla y el índice se separan, el código va a creer que puede crear
# una segunda suscripción y la base lo va a rechazar con un error feo.
VIVOS = (PENDIENTE, ACTIVO, PAUSADO)

# Qué significa cada estado para el dueño, en su idioma.
ESTADOS: dict[str, dict[str, str]] = {
    PENDIENTE: {
        "etiqueta": "Falta poner la tarjeta",
        "color": "ambar",
        "detalle": (
            "Empezaste a activar el débito automático pero no terminaste de "
            "cargar la tarjeta en Mercado Pago."
        ),
    },
    ACTIVO: {
        "etiqueta": "Débito automático activo",
        "color": "verde",
        "detalle": "Se cobra solo todos los meses. No tenés que hacer nada.",
    },
    PAUSADO: {
        "etiqueta": "En pausa",
        "color": "ambar",
        "detalle": "El débito está pausado y no se está cobrando.",
    },
    CANCELADO: {
        "etiqueta": "Cancelado",
        "color": "gris",
        "detalle": "Ya no se cobra automáticamente.",
    },
}


def esta_activo() -> bool:
    """¿Este entorno puede cobrar por Mercado Pago?"""
    return bool(settings.mp_saas_access_token)


def referencia_de(empresa_id: int, plan: str) -> str:
    """Lo que viaja con la suscripción y vuelve en cada notificación.

    El prefijo `deb:` la separa de `sus:`, que es la de un pago suelto. Son
    dos cosas distintas que entran por el mismo webhook, y confundirlas
    significa buscar un `authorized_payment` en el endpoint de pagos (o al
    revés) y no encontrar nada.
    """
    return f"deb:{empresa_id}:{plan}"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.mp_saas_access_token}"}


def vigente(db: Session, empresa_id: int) -> DebitoAutomatico | None:
    """El débito automático vivo de esta empresa, si tiene uno.

    "Vivo" incluye el que está a medio activar (`pending`): mostrarlo es lo
    que permite decirle «te falta poner la tarjeta» en vez de ofrecerle
    activar de nuevo algo que ya empezó.
    """
    return db.scalar(
        select(DebitoAutomatico)
        .where(
            DebitoAutomatico.empresa_id == empresa_id,
            DebitoAutomatico.estado.in_(VIVOS),
        )
        .order_by(DebitoAutomatico.creada_en.desc())
    )


def monto_de(empresa: Empresa, plan: str) -> float:
    """Cuánto autorizar por mes. El precio pactado manda sobre la grilla."""
    if empresa.precio_mensual is not None:
        return float(empresa.precio_mensual)
    return float(limites_de(plan).precio)


def crear(db: Session, empresa: Empresa, plan: str, email: str) -> str | None:
    """Crea la suscripción en Mercado Pago y devuelve a dónde mandar al dueño.

    Devuelve el `init_point` (la URL del checkout donde pone la tarjeta), o
    None si no se pudo. NUNCA levanta: esto lo dispara un botón del panel, y
    un error de red de Mercado Pago no puede ser un 500.

    LA FILA SE GUARDA ANTES DE DEVOLVER, y eso es a propósito: si el dueño
    abandona el checkout a mitad de camino, la suscripción queda en `pending`
    en los dos lados. Sin la fila, Mercado Pago tendría una suscripción a
    medio hacer de la que acá no habría ni rastro, y la próxima vez que
    tocara «Activar» se crearía una segunda.
    """
    if not esta_activo():
        return None

    candidato = plan_de(plan)
    if not se_vende_solo(candidato):
        # Enterprise no tiene precio de lista: no hay monto que autorizar.
        return None

    if vigente(db, empresa.id) is not None:
        # Ya tiene una. El panel no debería llegar acá, pero el índice único
        # de la base lo rechazaría igual y con un error mucho peor.
        return None

    monto = monto_de(empresa, candidato.value)
    if monto <= 0:
        return None

    panel = f"{settings.public_base_url}/suscripcion"
    payload = {
        "reason": f"Turnos360 {limites_de(candidato.value).etiqueta}"[:255],
        "external_reference": referencia_de(empresa.id, candidato.value),
        # A quién le cobra. Es el mail del dueño: Mercado Pago lo usa para
        # vincular la suscripción a su cuenta y para mandarle los avisos de
        # cada cobro, que son los que hacen que un cargo automático no
        # aparezca como una sorpresa en el resumen.
        "payer_email": email,
        "back_url": f"{panel}?debito=listo",
        # Sin tarjeta: el dueño la pone en el checkout de Mercado Pago. Ver
        # el docstring del módulo.
        "status": "pending",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": monto,
            "currency_id": "ARS",
        },
    }

    try:
        r = httpx.post(
            f"{MP_API}/preapproval", json=payload, headers=_headers(), timeout=TIMEOUT
        )
        r.raise_for_status()
        datos = r.json()
    except Exception:
        log.exception("MP débito: falló crear la suscripción (empresa %s)", empresa.id)
        return None

    preapproval_id = str(datos.get("id") or "").strip()
    init_point = datos.get("init_point")
    if not preapproval_id or not init_point:
        log.error("MP débito: respuesta sin id o sin init_point: %r", datos)
        return None

    db.add(
        DebitoAutomatico(
            empresa_id=empresa.id,
            preapproval_id=preapproval_id,
            estado=str(datos.get("status") or PENDIENTE),
            plan=candidato.value,
            monto=monto,
        )
    )
    db.commit()
    log.info(
        "MP débito: suscripción creada",
        extra={"empresa_id": empresa.id, "preapproval_id": preapproval_id},
    )
    return init_point


def consultar(preapproval_id: str) -> dict | None:
    """Trae la suscripción desde la API. None si no se pudo."""
    if not esta_activo():
        return None
    try:
        r = httpx.get(
            f"{MP_API}/preapproval/{preapproval_id}",
            headers=_headers(),
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        log.exception("MP débito: falló consultar %s", preapproval_id)
        return None


def sincronizar(db: Session, preapproval_id: str) -> DebitoAutomatico | None:
    """Trae el estado de Mercado Pago y lo copia a nuestra fila.

    ES LA ÚNICA FORMA DE ENTERARSE DE ALGUNOS CAMBIOS. Hay tres que ocurren
    sin que nosotros hagamos nada:
      · el dueño terminó de poner la tarjeta (pending → authorized);
      · el dueño canceló desde SU cuenta de Mercado Pago, no desde el panel;
      · Mercado Pago la dio de baja tras tres ciclos rechazados.
    En los tres, si no preguntamos, el panel sigue mostrando lo de antes.

    Nunca levanta. Si Mercado Pago no responde, la fila queda como estaba,
    que es preferible a marcarla cancelada por un problema de red — eso le
    apagaría el débito a alguien que lo tiene andando.
    """
    fila = db.scalar(
        select(DebitoAutomatico).where(
            DebitoAutomatico.preapproval_id == str(preapproval_id)
        )
    )
    if fila is None:
        log.warning("MP débito: notificación de una suscripción que no es nuestra (%s)",
                    preapproval_id)
        return None

    datos = consultar(preapproval_id)
    if datos is None:
        return fila

    estado = str(datos.get("status") or "").strip()
    if estado:
        if estado == CANCELADO and fila.estado != CANCELADO:
            fila.cancelada_en = dt.datetime.now(dt.timezone.utc)
            # Nadie del panel la tocó: si llegamos acá por sincronización, la
            # cortó Mercado Pago o el dueño desde su propia cuenta.
            fila.cancelada_por = fila.cancelada_por or "mercadopago"
        fila.estado = estado

    proximo = datos.get("next_payment_date")
    if proximo:
        try:
            fila.proximo_cobro = dt.datetime.fromisoformat(
                str(proximo).replace("Z", "+00:00")
            ).date()
        except (TypeError, ValueError):
            pass

    fila.actualizada_en = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return fila


def consultar_cobro(authorized_payment_id: str) -> dict | None:
    """Trae UN cobro mensual (la "factura" del mes) desde la API."""
    if not esta_activo():
        return None
    try:
        r = httpx.get(
            f"{MP_API}/authorized_payments/{authorized_payment_id}",
            headers=_headers(),
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        log.exception("MP débito: falló consultar el cobro %s", authorized_payment_id)
        return None


def acreditar_cobro(db: Session, authorized_payment_id: str):
    """Procesa el cobro mensual de una suscripción. Nunca levanta.

    Es el corazón del "y listo": acá es donde el mes se paga sin que nadie
    toque nada.

    EL ORDEN IMPORTA, igual que en el pago suelto: primero se corta por
    idempotencia (sin salir a la red), después se verifica contra la API, y
    recién ahí se toca la base. Mercado Pago reintenta la misma notificación
    varias veces; sin el corte, cada reintento correría otros 30 días.

    UN COBRO RECHAZADO TAMBIÉN SE PROCESA, y es la mitad del valor de esta
    función: no acredita nada, pero deja anotado el motivo para que el panel
    pueda decir «tu tarjeta venció» en lugar de que el negocio se entere el
    día que se le corta el servicio.
    """
    from app.services import cobranza, mp_suscripcion

    datos = consultar_cobro(authorized_payment_id)
    if not datos:
        return None

    fila = db.scalar(
        select(DebitoAutomatico).where(
            DebitoAutomatico.preapproval_id == str(datos.get("preapproval_id") or "")
        )
    )
    if fila is None:
        log.warning(
            "MP débito: cobro %s de una suscripción que no es nuestra",
            authorized_payment_id,
        )
        return None

    pago = datos.get("payment") or {}
    estado_pago = str(pago.get("status") or "").strip()
    payment_id = str(pago.get("id") or "").strip()

    if estado_pago != "approved":
        # Rechazado, pendiente o en revisión: no hay plata. Se anota para el
        # cartel del panel y se cuenta, que es lo que permite avisar antes de
        # que Mercado Pago dé de baja la suscripción sola.
        fila.cobros_fallidos = (fila.cobros_fallidos or 0) + 1
        fila.ultimo_error = (
            str(pago.get("status_detail") or estado_pago or "sin detalle")[:200]
        )
        fila.actualizada_en = dt.datetime.now(dt.timezone.utc)
        db.commit()
        log.warning(
            "MP débito: cobro no aprobado",
            extra={
                "empresa_id": fila.empresa_id,
                "estado": estado_pago,
                "detalle": fila.ultimo_error,
            },
        )
        return None

    # Aprobado. La idempotencia es la MISMA que la del pago suelto: el
    # `mp_payment_id` de `pago_suscripcion` es único, y el pago que hay
    # adentro de un cobro automático es un pago común de Mercado Pago. Así
    # una notificación `payment` y una `subscription_authorized_payment` del
    # mismo cargo no pueden acreditarse dos veces entre las dos.
    if not payment_id or mp_suscripcion.ya_acreditado(db, payment_id):
        return None

    empresa = db.get(Empresa, fila.empresa_id)
    if empresa is None:
        return None

    monto = float(datos.get("transaction_amount") or 0)

    # El plan que paga esta suscripción se activa solo, igual que en el pago
    # suelto. Se lee de NUESTRA fila y no del external_reference porque la
    # fila es la que sabe por qué monto está autorizada.
    plan_a_activar = None
    if fila.plan and se_vende_solo(plan_de(fila.plan)):
        plan_a_activar = plan_de(fila.plan).value

    cuota = cobranza.registrar_pago(
        db,
        empresa,
        monto=monto,
        metodo="debito_automatico",
        notas=(
            f"Débito automático de Mercado Pago "
            f"(cobro {authorized_payment_id}, pago {payment_id})"
        ),
        registrado_por="mercadopago",
        renovar=True,
        plan=plan_a_activar,
    )
    cuota.mp_payment_id = payment_id

    # Se cobró: la racha de fallos se corta y el motivo viejo se borra. Si no
    # se limpiara, el panel seguiría mostrando «tu tarjeta venció» al mes
    # siguiente, con la cuota ya cobrada.
    fila.cobros_fallidos = 0
    fila.ultimo_error = None
    fila.actualizada_en = dt.datetime.now(dt.timezone.utc)
    db.commit()

    log.info(
        "MP débito: cuota cobrada automáticamente",
        extra={"empresa_id": empresa.id, "monto": monto, "payment_id": payment_id},
    )

    try:
        from app.core.cola import encolar
        from app.tasks.emails import avisar_pago_recibido

        encolar(
            avisar_pago_recibido,
            empresa.id,
            monto,
            "Débito automático",
            plan=plan_a_activar,
            referencia=f"pago {payment_id}",
            confirmado=True,
        )
    except Exception:
        log.exception("No se pudo avisar el cobro automático %s", payment_id)

    return cuota


def cancelar(db: Session, empresa_id: int, quien: str) -> bool:
    """Corta el débito automático. Devuelve si se pudo.

    NO le quita el servicio a nadie: `suscripcion_vence` no se toca, así que
    el negocio sigue andando hasta el final del mes que ya pagó. Es como
    funciona cualquier suscripción y es lo que la gente espera — cortar en el
    acto algo que está pagado se siente como un robo, aunque el botón diga
    «cancelar».

    EL ORDEN ES: PRIMERO MERCADO PAGO, DESPUÉS NOSOTROS. Al revés, si la
    llamada falla, nuestra fila diría "cancelada" mientras Mercado Pago sigue
    cobrando todos los meses — el peor de los dos errores posibles.
    """
    fila = vigente(db, empresa_id)
    if fila is None:
        return False

    if esta_activo():
        try:
            r = httpx.put(
                f"{MP_API}/preapproval/{fila.preapproval_id}",
                json={"status": CANCELADO},
                headers=_headers(),
                timeout=TIMEOUT,
            )
            r.raise_for_status()
        except Exception:
            log.exception(
                "MP débito: falló cancelar en Mercado Pago (%s)", fila.preapproval_id
            )
            return False

    fila.estado = CANCELADO
    fila.cancelada_en = dt.datetime.now(dt.timezone.utc)
    fila.cancelada_por = quien
    fila.actualizada_en = dt.datetime.now(dt.timezone.utc)
    db.commit()
    log.info(
        "MP débito: cancelado",
        extra={"empresa_id": empresa_id, "por": quien},
    )
    return True


def para_mostrar(db: Session, empresa_id: int) -> dict | None:
    """Lo que la pantalla «Mi suscripción» necesita saber del débito.

    None = esta empresa no tiene débito automático, y el panel ofrece
    activarlo. Nunca devuelve datos de la tarjeta porque no los tenemos.
    """
    fila = vigente(db, empresa_id)
    if fila is None:
        return None

    info = ESTADOS.get(fila.estado, {"etiqueta": fila.estado, "color": "gris", "detalle": ""})
    return {
        "estado": fila.estado,
        "etiqueta": info["etiqueta"],
        "color": info["color"],
        "detalle": info["detalle"],
        "plan": fila.plan,
        "plan_etiqueta": limites_de(fila.plan).etiqueta if fila.plan else None,
        "monto": float(fila.monto) if fila.monto is not None else None,
        "proximo_cobro": str(fila.proximo_cobro) if fila.proximo_cobro else None,
        "desde": fila.creada_en.date().isoformat() if fila.creada_en else None,
        # Si el último cobro falló, el panel tiene que decirlo ARRIBA de todo
        # y ofrecer pagar a mano: los reintentos de Mercado Pago pueden tardar
        # más que los días de prórroga.
        "cobros_fallidos": fila.cobros_fallidos or 0,
        "ultimo_error": fila.ultimo_error,
    }
