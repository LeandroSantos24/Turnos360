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

    if vence is None:
        # Sin fecha: plan gratuito o cuenta sin vencimiento definido.
        return {
            "plan": plan,
            "estado": "sin_vencimiento",
            "vence": None,
            "dias_restantes": None,
            "en_prorroga": False,
            "mensaje": "Plan gratuito" if plan == "gratuito" else "Sin vencimiento",
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
    }
