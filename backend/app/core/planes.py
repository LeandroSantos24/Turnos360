"""La grilla de planes: precios y límites, en UN solo lugar.

POR QUÉ EXISTE ESTE ARCHIVO
───────────────────────────
Antes el "plan" era un `String(20)` libre en `empresa.plan`, sin enum ni CHECK.
Circulaban dos valores, `"gratuito"` y `"pro"`, y `"pro"` se escribía en un
único lugar de todo el backend: como efecto lateral del botón "Renovar 30
días". Los precios vivían en otro lado (config.py), los límites en otro
(`empresa.limite_recursos`), y ninguno de los dos se hablaba con el plan.

Resultado: una empresa podía pagar la cuota por Mercado Pago durante un año y
seguir figurando en `"gratuito"`, y una del plan de 3 profesionales podía cargar
40 sin que nada se lo impidiera. El límite se pintaba en ámbar en el panel del
super-admin y no bloqueaba absolutamente nada.

LOS DOS EJES VAN SEPARADOS
──────────────────────────
Profesionales por un lado, sucursales por el otro. Así el plan del medio se
puede vender hoy, sin esperar a que multisucursal esté terminado.

EL PLAN BÁSICO ES EL ESTRELLA
─────────────────────────────
Es el criterio de aceptación de todo lo que se construya: el negocio de una
sola sucursal y tres profesionales tiene que seguir viendo la aplicación
exactamente igual de simple. Los límites de arriba no se le muestran hasta que
los toca.
"""

import enum
from dataclasses import dataclass


class Plan(str, enum.Enum):
    """Los planes que se pueden contratar.

    `GRATUITO` no es un plan que se venda: es el estado de una empresa en
    período de prueba o dada de alta a dedo por el super-admin. Se le dan los
    mismos límites que al Básico para que la prueba sea representativa de lo
    que va a pagar.
    """

    GRATUITO = "gratuito"
    BASICO = "basico"
    PRO = "pro"
    MULTI = "multi"


@dataclass(frozen=True)
class Limites:
    etiqueta: str
    precio: float
    # None = sin tope. Se cuentan los recursos ACTIVOS de tipo persona.
    profesionales: int | None
    sucursales: int
    resumen: str


GRILLA: dict[Plan, Limites] = {
    Plan.GRATUITO: Limites(
        etiqueta="Prueba",
        precio=0,
        profesionales=3,
        sucursales=1,
        resumen="3 profesionales · 1 local",
    ),
    Plan.BASICO: Limites(
        etiqueta="Básico",
        precio=14990,
        profesionales=3,
        sucursales=1,
        resumen="3 profesionales · 1 local",
    ),
    Plan.PRO: Limites(
        etiqueta="Pro",
        precio=24990,
        profesionales=10,
        sucursales=1,
        resumen="10 profesionales · 1 local",
    ),
    Plan.MULTI: Limites(
        etiqueta="Multi",
        precio=35990,
        profesionales=None,
        sucursales=5,
        resumen="Profesionales ilimitados · hasta 5 locales",
    ),
}

# El plan con el que arranca quien paga por primera vez viniendo de la prueba.
PLAN_DE_ENTRADA = Plan.BASICO


def plan_de(valor: str | None) -> Plan:
    """Convierte el string de la base en un Plan, sin explotar nunca.

    La columna es texto libre y estuvo así meses: puede haber cualquier cosa
    escrita ahí. Un valor que no reconocemos se trata como GRATUITO, que es el
    más restrictivo — nunca al revés, porque equivocarse hacia arriba sería
    regalar un plan que nadie pagó.
    """
    try:
        return Plan(str(valor or "").strip().lower())
    except ValueError:
        return Plan.GRATUITO


def limites_de(valor: str | None) -> Limites:
    return GRILLA[plan_de(valor)]


def tope_profesionales(plan: str | None, override: int | None) -> int | None:
    """Cuántos profesionales puede tener esta empresa. None = sin tope.

    `override` es `empresa.limite_recursos`, que el super-admin edita a mano en
    la ficha comercial. Manda sobre la grilla: es lo que permite hacerle un
    precio y un cupo especial a un cliente sin inventar un plan nuevo, y lo que
    permite dejar tranquilo a alguien que ya tenía más profesionales cargados
    que los que su plan admite.
    """
    if override is not None:
        return override
    return limites_de(plan).profesionales


def tope_sucursales(plan: str | None, override: int | None = None) -> int:
    if override is not None:
        return override
    return limites_de(plan).sucursales


def para_mostrar() -> list[dict]:
    """La grilla como la consume la landing y la pantalla de suscripción."""
    return [
        {
            "codigo": p.value,
            "etiqueta": lim.etiqueta,
            "precio": lim.precio,
            "profesionales": lim.profesionales,
            "sucursales": lim.sucursales,
            "resumen": lim.resumen,
        }
        for p, lim in GRILLA.items()
        if p is not Plan.GRATUITO  # la prueba no se vende
    ]
