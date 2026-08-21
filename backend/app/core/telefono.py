"""Números de teléfono argentinos → el formato que quiere WhatsApp.

Por qué este módulo existe
--------------------------
El teléfono de un cliente se carga a mano, en el mostrador, en el celular, o
lo escribe el propio cliente en la landing. Llega de todas estas formas, y
todas son la misma persona:

    2614123456          261 4123456         0261 15 4123456
    +54 9 261 412-3456  54 9 2614123456     (0261) 15-4123456

WhatsApp no acepta ninguna. Quiere E.164 sin el "+": `5492614123456`.

Y hay una trampa argentina que rompe integraciones todo el tiempo: para un
celular argentino hay que mandar el **9** después del 54, y hay que sacar el
**15**. Son la misma cosa dicha de dos maneras —el 15 es cómo se marca un
celular desde adentro del país, el 9 es cómo se lo marca desde afuera— y si
mandás los dos, o ninguno, el mensaje no llega y Meta te lo cobra igual.

La decisión de diseño
---------------------
Esta función **falla en voz alta**. Si no puede estar segura de qué número es,
levanta ValueError con un mensaje que se le puede mostrar a un dueño de
barbería, en vez de devolver algo parecido y mandarle un mensaje a un
desconocido. Un mensaje a la persona equivocada cuesta plata, ensucia la
reputación del número ante Meta, y es un problema de privacidad.
"""

import re

# El número nacional argentino (código de área + abonado) SIEMPRE tiene 10
# dígitos: 11 + 8 en Buenos Aires, 261 + 7 en Mendoza, 2966 + 6 en Río Gallegos.
LARGO_NACIONAL = 10


class TelefonoInvalido(ValueError):
    """El texto no se pudo interpretar como un celular argentino."""


def _solo_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def normalizar_ar(texto: str | None) -> str:
    """Devuelve el número en formato WhatsApp (`549` + 10 dígitos), o levanta.

    >>> normalizar_ar("0261 15 4123456")
    '5492614123456'
    >>> normalizar_ar("+54 9 261 412-3456")
    '5492614123456'
    >>> normalizar_ar("11 1234-5678")
    '5491112345678'
    """
    crudo = (texto or "").strip()
    if not crudo:
        raise TelefonoInvalido("El cliente no tiene teléfono cargado.")

    d = _solo_digitos(crudo)
    if not d:
        raise TelefonoInvalido(f"«{crudo}» no tiene ningún número.")

    # Prefijo internacional escrito como 00: 0054 11 ...
    if d.startswith("00"):
        d = d[2:]

    # ── Sacar el código de país si vino ───────────────────────────────────
    if d.startswith("54"):
        resto = d[2:]
        # 54 9 ... : el 9 de celular. Lo sacamos acá y lo volvemos a poner al
        # final, para tratar a todos los formatos por el mismo camino.
        if len(resto) in (11, 13) and resto.startswith("9"):
            resto = resto[1:]
        nacional = resto
    else:
        nacional = d

    # ── Sacar el 0 de larga distancia: 0261 ... ───────────────────────────
    if nacional.startswith("0"):
        nacional = nacional[1:]

    # ── Sacar el 15 ───────────────────────────────────────────────────────
    # Con el 15 el número tiene 12 dígitos y sin él tiene 10. El 15 va
    # justo después del código de área, que puede ser de 2, 3 o 4 dígitos:
    # solo el "11" de Buenos Aires es de 2.
    if len(nacional) == LARGO_NACIONAL + 2:
        largos_area = (2,) if nacional.startswith("11") else (3, 4)
        for largo in largos_area:
            if nacional[largo : largo + 2] == "15":
                nacional = nacional[:largo] + nacional[largo + 2 :]
                break

    # ── Verificar ─────────────────────────────────────────────────────────
    if len(nacional) != LARGO_NACIONAL:
        raise TelefonoInvalido(
            f"«{crudo}» no parece un celular argentino: "
            f"me quedan {len(nacional)} dígitos y tienen que ser {LARGO_NACIONAL} "
            "(código de área + número, sin el 0 y sin el 15)."
        )
    if nacional[0] == "0":
        raise TelefonoInvalido(f"«{crudo}» empieza con 0 después de limpiarlo.")
    if len(set(nacional)) == 1:
        # 0000000000, 1111111111: datos de relleno que alguien cargó para
        # pasar un campo obligatorio. Mandar ahí es tirar plata.
        raise TelefonoInvalido(f"«{crudo}» son todos el mismo dígito.")

    return f"549{nacional}"


def es_valido_ar(texto: str | None) -> bool:
    """Versión que no levanta, para pintar la lista de clientes."""
    try:
        normalizar_ar(texto)
        return True
    except TelefonoInvalido:
        return False


def para_mostrar(texto: str | None) -> str:
    """`5492614123456` → `+54 9 261 412-3456`. Solo para la pantalla."""
    try:
        e164 = normalizar_ar(texto)
    except TelefonoInvalido:
        return (texto or "").strip()
    nacional = e164[3:]
    area = "11" if nacional.startswith("11") else nacional[:3]
    resto = nacional[len(area) :]
    return f"+54 9 {area} {resto[:-4]}-{resto[-4:]}"
