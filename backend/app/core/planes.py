"""La grilla de planes: precios, cupos y qué incluye cada uno, en UN solo lugar.

POR QUÉ EXISTE ESTE ARCHIVO
───────────────────────────
Antes el "plan" era un `String(20)` libre en `empresa.plan`, sin enum ni CHECK.
Circulaban dos valores, `"gratuito"` y `"pro"`, y `"pro"` se escribía en un
único lugar de todo el backend: como efecto lateral del botón "Renovar 30
días". Los precios vivían en otro lado (config.py) y los límites en otro
(`empresa.limite_recursos`), y ninguno se hablaba con el plan. Una empresa
podía pagar la cuota por Mercado Pago durante un año y seguir figurando en
`"gratuito"`; una del plan de 3 profesionales podía cargar 40 sin que nada se
lo impidiera.

LOS TRES EJES VAN SEPARADOS
───────────────────────────
Profesionales, usuarios y sucursales. Son tres cosas distintas y confundirlas
sale caro:

  · PROFESIONAL es quien ocupa una columna de la agenda — el que atiende. Es lo
    que de verdad escala con el tamaño del negocio y lo que se cobra.
  · USUARIO es quien entra al sistema con su clave. Un profesional que no toca
    la computadora no necesita usuario; una recepcionista que no atiende a
    nadie sí. Se limita por separado y con la mano floja: cobrar por asiento a
    una peluquería de barrio es la forma más rápida de que compartan una clave
    entre cuatro, que es peor para todos —empezando por la trazabilidad de la
    caja—.
  · SUCURSAL es un local con su propia caja, su equipo y su agenda.

EL PRECIO ENTRA POR DEBAJO DE LA COMPETENCIA
────────────────────────────────────────────
Ágora —el competidor directo en Argentina— cobra $11.900 con plan único.
Inicial sale lo mismo y da la agenda completa con página de reservas y señas;
el salto a Pro se paga por el equipo más grande y por lo que hace ganar plata
(membresías, gift cards, cupones, campañas), y el salto a Multi por lo que
ningún competidor del segmento tiene terminado: varios locales de verdad.

EL PLAN DE ENTRADA ES EL CRITERIO DE ACEPTACIÓN
───────────────────────────────────────────────
Todo lo que se construya tiene que dejar al negocio de un solo local y dos
profesionales viendo la aplicación exactamente igual de simple. Los límites de
arriba no se le muestran hasta que los toca.
"""

import enum
from dataclasses import dataclass, field


class Plan(str, enum.Enum):
    """Los planes que se pueden contratar.

    `GRATUITO` no se vende: es el estado de una empresa en período de prueba o
    dada de alta a dedo por el super-admin. Se le dan los cupos y las funciones
    del plan MÁS ALTO a propósito — una prueba recortada no deja probar
    justamente lo que uno querría vender, y el negocio se va sin haber visto
    la mitad del producto. Al vencer la prueba cae a Inicial.
    """

    GRATUITO = "gratuito"
    INICIAL = "inicial"
    PRO = "pro"
    MULTI = "multi"
    # No se vende solo: no tiene precio de lista y el botón lleva a WhatsApp.
    # Los cupos y el precio los pone el super-admin en la ficha comercial
    # (`precio_mensual`, `limite_recursos`, `limite_sucursales`), que ya
    # existían y son exactamente el mecanismo que este plan necesita.
    ENTERPRISE = "enterprise"


class Funcion(str, enum.Enum):
    """Lo que un plan habilita, además de los cupos.

    Son las que se pueden apagar sin romper el producto: apagar la agenda no
    tiene sentido —es para lo que se contrata—, apagar las gift cards sí.

    La regla al elegir qué va en cada plan: en Inicial entra todo lo que hace
    falta para ATENDER (agenda, página de reservas, señas, recordatorios,
    caja, clientes). Lo que entra en Pro es lo que hace falta para VENDER MÁS
    a los que ya son clientes.
    """

    MEMBRESIAS = "membresias"
    GIFT_CARDS = "gift_cards"
    CUPONES = "cupones"
    CAMPANAS = "campanas"          # cumpleaños, inactivos, reseñas
    COMISIONES = "comisiones"      # liquidación por profesional
    WHATSAPP = "whatsapp"
    MULTISUCURSAL = "multisucursal"
    ESTADISTICAS_AVANZADAS = "estadisticas_avanzadas"


# Lo que ya viene en Inicial. Se nombra en vez de dejarlo implícito para que
# se lea de un vistazo qué es "lo básico".
DE_INICIAL = frozenset(
    {
        Funcion.CAMPANAS,  # los recordatorios anti-ausencias son el corazón
    }
)

DE_PRO = DE_INICIAL | frozenset(
    {
        Funcion.MEMBRESIAS,
        Funcion.GIFT_CARDS,
        Funcion.CUPONES,
        Funcion.COMISIONES,
        Funcion.WHATSAPP,
    }
)

DE_MULTI = DE_PRO | frozenset(
    {
        Funcion.MULTISUCURSAL,
        Funcion.ESTADISTICAS_AVANZADAS,
    }
)


@dataclass(frozen=True)
class Limites:
    etiqueta: str
    precio: float
    # None = sin tope. Se cuentan los recursos ACTIVOS de tipo persona.
    profesionales: int | None
    # None = sin tope. Se cuentan los usuarios ACTIVOS.
    usuarios: int | None
    sucursales: int
    resumen: str
    # Para la landing: la frase de una línea que dice para quién es.
    para_quien: str
    funciones: frozenset[Funcion] = field(default_factory=frozenset)

    def incluye(self, funcion: Funcion) -> bool:
        return funcion in self.funciones


GRILLA: dict[Plan, Limites] = {
    Plan.GRATUITO: Limites(
        etiqueta="Prueba",
        precio=0,
        # LOS CUPOS DE PRO, PERO UN SOLO LOCAL.
        #
        # Que pruebe todo lo que va a usar de verdad —su equipo entero,
        # membresías, gift cards, cupones, campañas— porque justamente eso es
        # lo que hace que se quede. Un cupo apretado durante la prueba es una
        # forma cara de que se vaya sin haber visto la mitad del producto.
        #
        # El único techo es el segundo local, que es exactamente lo que
        # justifica pagar Multi. Multisucursal no se regala en la prueba: si
        # se probara gratis, el plan más caro perdería su único argumento.
        profesionales=8,
        usuarios=10,
        sucursales=1,
        resumen="Todo lo de Pro por 14 días, en un local",
        para_quien="Para probarlo con tus turnos de verdad, sin tarjeta.",
        funciones=DE_PRO,
    ),
    Plan.INICIAL: Limites(
        etiqueta="Inicial",
        precio=11900,
        profesionales=2,
        usuarios=3,
        sucursales=1,
        resumen="2 profesionales · 1 local",
        para_quien="El que atiende solo o con una persona más.",
        funciones=DE_INICIAL,
    ),
    Plan.PRO: Limites(
        etiqueta="Pro",
        precio=19900,
        profesionales=8,
        usuarios=10,
        sucursales=1,
        resumen="8 profesionales · 1 local",
        para_quien="El local con equipo, que ya quiere vender más a los que tiene.",
        funciones=DE_PRO,
    ),
    Plan.MULTI: Limites(
        etiqueta="Multi",
        precio=32900,
        profesionales=None,
        usuarios=None,
        sucursales=5,
        resumen="Profesionales ilimitados · hasta 5 locales",
        para_quien="El que abrió el segundo local y necesita compararlos.",
        funciones=DE_MULTI,
    ),
    Plan.ENTERPRISE: Limites(
        etiqueta="Enterprise",
        # precio 0 = a convenir. NO es gratis: `a_convenir` de abajo es lo que
        # hace que la pantalla muestre «Hablemos» en vez de «$0», y el cobro
        # automático se saltea este plan justamente porque no tiene precio de
        # lista. El de verdad lo carga el super-admin en `precio_mensual`.
        precio=0,
        profesionales=None,
        usuarios=None,
        # Un número alto y no ilimitado: el tope real lo pone
        # `limite_sucursales` en la ficha de cada cliente. Sin ningún tope, un
        # error de tipeo en un alta podría crear cien locales sin que nada
        # frene.
        sucursales=50,
        resumen="Todo ilimitado · locales a medida",
        para_quien="Cadenas y franquicias. Lo armamos con vos.",
        funciones=DE_MULTI,
    ),
}

# Los planes que se compran solos desde «Mi suscripción», en orden de precio.
# Enterprise NO está: no tiene precio de lista, así que no puede generar un
# link de pago. GRATUITO tampoco: no se vende, se vence.
PLANES_A_LA_VENTA = (Plan.INICIAL, Plan.PRO, Plan.MULTI)


def se_vende_solo(plan: Plan) -> bool:
    """¿Este plan se puede pagar sin que intervenga nadie de Turnos360?"""
    return plan in PLANES_A_LA_VENTA

# El plan con el que arranca quien paga por primera vez viniendo de la prueba.
PLAN_DE_ENTRADA = Plan.INICIAL


def plan_de(valor: str | None) -> Plan:
    """Convierte el string de la base en un Plan, sin explotar nunca.

    La columna es texto libre y estuvo así meses: puede haber cualquier cosa
    escrita ahí. Un valor que no reconocemos se trata como GRATUITO, que es lo
    que corresponde — nunca hacia arriba, porque equivocarse hacia arriba sería
    regalar un plan que nadie pagó.

    `"basico"` se mapea a INICIAL: es el nombre viejo del mismo plan, y las
    empresas que lo tengan escrito en la base no se enteran del cambio.
    """
    crudo = str(valor or "").strip().lower()
    if crudo == "basico":
        return Plan.INICIAL
    try:
        return Plan(crudo)
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


def tope_usuarios(plan: str | None, override: int | None = None) -> int | None:
    """Cuántas cuentas con clave puede tener. None = sin tope."""
    if override is not None:
        return override
    return limites_de(plan).usuarios


def tope_sucursales(plan: str | None, override: int | None = None) -> int:
    if override is not None:
        return override
    return limites_de(plan).sucursales


def incluye(plan: str | None, funcion: Funcion) -> bool:
    """¿El plan de esta empresa incluye esta función?

    Se pregunta con el enum y no con un string para que un typo sea un error
    de Python y no un `False` silencioso — que en una función de gating
    significaría dejar afuera a alguien que pagó.
    """
    return limites_de(plan).incluye(funcion)


def para_mostrar() -> list[dict]:
    """La grilla como la consumen la landing y la pantalla de suscripción."""
    return [
        {
            "codigo": p.value,
            "etiqueta": lim.etiqueta,
            "precio": lim.precio,
            "profesionales": lim.profesionales,
            "usuarios": lim.usuarios,
            "sucursales": lim.sucursales,
            "resumen": lim.resumen,
            "para_quien": lim.para_quien,
            "funciones": sorted(f.value for f in lim.funciones),
            # La pantalla decide con esto si dibuja un precio y un botón de
            # pago, o «Hablemos» con el link a WhatsApp.
            "a_convenir": not se_vende_solo(p),
        }
        for p, lim in GRILLA.items()
        if p is not Plan.GRATUITO  # la prueba no se vende
    ]
