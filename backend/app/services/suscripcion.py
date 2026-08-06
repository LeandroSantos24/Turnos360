"""Estado de la suscripción de una empresa.

Regla de negocio (definida por Leandro):
- La suscripción vence en una fecha (suscripcion_vence).
- Tras el vencimiento hay 10 días de PRÓRROGA (gracia) antes de considerarla
  vencida de verdad. Durante la prórroga el negocio sigue operando, pero se le
  avisa que regularice.
"""

import datetime as dt

from app.models.organizacion import Empresa

DIAS_PRORROGA = 10


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
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.saas import PagoSuscripcion

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        return {}

    estado = estado_suscripcion(empresa)

    pagos = list(
        db.scalars(
            select(PagoSuscripcion)
            .where(PagoSuscripcion.empresa_id == empresa_id)
            .order_by(PagoSuscripcion.fecha.desc())
            .limit(24)
        )
    )

    return {
        **estado,
        "precio_mensual": (
            float(empresa.precio_mensual) if empresa.precio_mensual is not None else None
        ),
        # Si todavía no se cargó la cuota pactada, el último pago sirve de
        # referencia: mostrarle un guion a alguien que ya pagó $16.990 es raro.
        "ultimo_monto": float(pagos[0].monto) if pagos else None,
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
            "whatsapp": settings.cobro_whatsapp or None,
        },
    }
