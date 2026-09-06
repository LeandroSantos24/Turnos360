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


def estado_suscripcion(empresa: Empresa) -> dict:
    """Devuelve el estado legible de la suscripción para mostrar en el panel."""
    plan = empresa.plan or "gratuito"
    vence = empresa.suscripcion_vence
    hoy_ = dt.date.today()

    # La prueba se evalúa PRIMERO: mientras dura, el negocio no está ni al día
    # ni vencido. Mezclarlo con cualquiera de los dos le muestra un cartel que
    # no corresponde.
    if empresa.prueba_hasta is not None and hoy_ <= empresa.prueba_hasta:
        restantes = (empresa.prueba_hasta - hoy_).days
        return {
            "plan": plan,
            "estado": "prueba",
            "vence": str(empresa.prueba_hasta),
            "dias_restantes": restantes,
            "en_prorroga": False,
            "corte": None,
            "dias_hasta_corte": None,
            "mensaje": (
                "Último día de prueba"
                if restantes == 0
                else f"Te quedan {restantes} día{'s' if restantes != 1 else ''} de prueba"
            ),
        }

    if vence is None:
        # Sin fecha: plan gratuito o cuenta sin vencimiento definido.
        return {
            "plan": plan,
            "estado": "sin_vencimiento",
            "vence": None,
            "dias_restantes": None,
            "en_prorroga": False,
            "corte": None,
            "dias_hasta_corte": None,
            "mensaje": (
                "Tu prueba terminó. Escribinos para activar tu cuenta."
                if empresa.prueba_hasta is not None
                else ("Plan gratuito" if plan == "gratuito" else "Sin vencimiento")
            ),
        }

    hoy = dt.date.today()
    dias = (vence - hoy).days
    fin_prorroga = vence + dt.timedelta(days=DIAS_PRORROGA)

    if hoy <= vence:
        estado = "activa"
        mensaje = (
            f"Activa · vence en {dias} día{'s' if dias != 1 else ''}"
            if dias > 0
            else "Activa · vence hoy"
        )
    elif hoy <= fin_prorroga:
        estado = "prorroga"
        dias_gracia = (fin_prorroga - hoy).days
        mensaje = (
            f"Venció · {dias_gracia} día{'s' if dias_gracia != 1 else ''} de gracia "
            "para regularizar"
        )
    else:
        estado = "vencida"
        mensaje = "Suscripción vencida"

    return {
        "plan": plan,
        "estado": estado,
        "vence": str(vence),
        "dias_restantes": dias,
        "en_prorroga": estado == "prorroga",
        "mensaje": mensaje,
        # Hasta cuándo puede pagar sin que se le corte el servicio. Es el dato
        # que faltaba: el negocio veía la fecha de vencimiento y creía que ahí
        # se apagaba todo.
        "corte": str(fin_prorroga),
        "dias_hasta_corte": (fin_prorroga - hoy).days,
    }


def _fmt(d) -> str | None:
    return str(d) if d else None


def mi_suscripcion(db, empresa_id: int) -> dict:
    """Vista de la suscripción PARA EL NEGOCIO (pantalla "Mi suscripción").

    Distinta de la del super-admin: acá el negocio ve lo suyo y nada más.
    En particular NO se exponen `notas` ni `registrado_por` de cada pago, que
    son apuntes internos de cobranza ("me dijo que paga el martes") y no
    tienen por qué llegarle al cliente.
    """
    from sqlalchemy import func, select

    from app.core.config import settings
    from app.models.saas import PagoSuscripcion
    from app.core import planes
    from app.services import mp_debito
    from app.services import mp_suscripcion as mp_sus

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return {}

    from app.models.agenda import Recurso
    from app.models.enums import TipoRecurso

    profesionales_usados = int(
        db.scalar(
            select(func.count(Recurso.id)).where(
                Recurso.empresa_id == empresa_id,
                Recurso.activo.is_(True),
                Recurso.tipo == TipoRecurso.PERSONA,
            )
        )
        or 0
    )

    estado = estado_suscripcion(empresa)

    pagos = list(
        db.scalars(
            select(PagoSuscripcion)
            .where(PagoSuscripcion.empresa_id == empresa_id)
            .order_by(PagoSuscripcion.fecha.desc())
            .limit(24)
        )
    )

    cuota, cuota_origen = cuota_de(empresa)

    return {
        **estado,
        # LA CUOTA, UNA SOLA VEZ Y CON SU ORIGEN.
        #
        # `precio_mensual` es el precio PACTADO y hoy está en NULL para casi
        # todo el mundo; el precio normal sale de la grilla del plan. La
        # pantalla no tiene que resolver esa regla: recibe el número resuelto
        # y, si necesita matizarlo, mira `cuota_origen`.
        #
        # Antes la pantalla mezclaba `precio_mensual` (una foto del precio de
        # lista del día del alta) con la grilla que dibujaba abajo, y mostraba
        # los dos números a la vez. Así fue como Leandro vio «$14.990» arriba
        # de una grilla que decía $13.900.
        "cuota": cuota,
        "cuota_origen": cuota_origen,
        # Se mantiene por compatibilidad con lo que ya lee la pantalla, pero
        # ahora dice lo mismo que `cuota`.
        "precio_mensual": cuota,
        "precio_pactado": empresa.precio_mensual is not None,
        # Si todavía no se cargó la cuota pactada, el último pago sirve de
        # referencia: mostrarle un guion a alguien que ya pagó la cuota es raro.
        "ultimo_monto": float(pagos[0].monto) if pagos else None,
        # Precio de lista vigente. Se usa SOLO en el mensaje de la prueba
        # ("cuando termine seguís por $X"): a un negocio en prueba todavía no
        # se le pactó nada, y el número es justo lo que necesita para decidir.
        "precio_lista": float(settings.precio_vigente),
        # El precio del plan de ENTRADA, que es a lo que cae quien termina la
        # prueba sin elegir nada. Es el número honesto para "cuando termine,
        # seguís por $X": el de lista puede tener una promo encima.
        "precio_entrada": float(planes.GRILLA[planes.PLAN_DE_ENTRADA].precio),
        # Qué incluye el plan actual y cuánto se está usando. Es lo que hace
        # que el tope deje de ser una sorpresa cuando el dueño intenta cargar
        # un profesional más y le rebota.
        "plan_etiqueta": planes.limites_de(empresa.plan).etiqueta,
        "plan_resumen": planes.limites_de(empresa.plan).resumen,
        "profesionales_usados": profesionales_usados,
        "profesionales_tope": planes.tope_profesionales(
            empresa.plan, empresa.limite_recursos
        ),
        "grilla": planes.para_mostrar(),
        "plan_codigo": planes.plan_de(empresa.plan).value,
        # La baja anotada para el fin del ciclo. La pantalla la muestra como
        # un aviso con opción de cancelarla: sin eso, alguien que pidió bajar
        # y se arrepintió no tiene forma de deshacerlo y termina escribiendo.
        "plan_programado": empresa.plan_programado,
        "plan_programado_etiqueta": (
            planes.limites_de(empresa.plan_programado).etiqueta
            if empresa.plan_programado
            else None
        ),
        # Sin token del SaaS no hay botón de pago: la pantalla ofrece solo
        # transferencia. Mostrar un botón que devuelve 503 es peor que no
        # mostrarlo.
        "mp_disponible": mp_sus.esta_activo(),
        # EL DÉBITO AUTOMÁTICO: el "pagás y listo" de Netflix/Spotify.
        # None = no tiene uno, y la pantalla ofrece activarlo. Ver
        # services/mp_debito.py.
        "debito": mp_debito.para_mostrar(db, empresa_id),
        "debito_disponible": mp_debito.esta_activo(),
        "dias_prorroga": DIAS_PRORROGA,
        "pagos": [
            {
                "fecha": _fmt(p.fecha),
                "monto": float(p.monto),
                "metodo": p.metodo,
                "periodo_desde": _fmt(p.periodo_desde),
                "periodo_hasta": _fmt(p.periodo_hasta),
            }
            for p in pagos
        ],
        # Datos de cobro de Turnos360, por entorno (el repo es público).
        # Si no están cargados, el frontend no muestra la sección.
        "cobro": {
            "cbu": settings.cobro_cbu or None,
            "alias": settings.cobro_alias or None,
            "titular": settings.cobro_titular or None,
            "cuit": settings.cobro_cuit or None,
            "banco": settings.cobro_banco or None,
            "mp_link": settings.cobro_mp_link or None,
            # ¿Se puede pagar la cuota con Checkout de Mercado Pago? Depende
            # de que haya token de la cuenta de Turnos360. Sin eso el frontend
            # no muestra el botón: ofrecer un pago que después nadie acredita
            # es peor que no ofrecerlo.
            "mp_checkout": mp_sus.esta_activo(),
            "whatsapp": settings.cobro_whatsapp or None,
        },
    }
