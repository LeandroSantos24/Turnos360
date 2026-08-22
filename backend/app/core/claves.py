"""Fortaleza de las claves que NO elige un usuario común.

Esto no se aplica a la clave de un dueño de barbería, que la tipea todos los
días. Se aplica al super-administrador: una cuenta que se configura UNA vez,
por variable de entorno, se guarda en un gestor de contraseñas y controla el
alta de todas las empresas, la pausa de cualquier negocio y las suscripciones
del SaaS entero.

POR QUÉ NO HAY REGLAS DE COMPOSICIÓN
─────────────────────────────────────
No se exige "una mayúscula, un número y un símbolo". Esa regla está
DESACONSEJADA desde 2017 por la guía de NIST (SP 800-63B, §5.1.1.2), y con
razón: no mide fuerza, mide obediencia. Empuja a la gente a `Password1!` —que
cumple las cuatro reglas y es de las primeras que prueba cualquiera— y castiga
a `correcto caballo batería grapa`, que es muchísimo más difícil de adivinar.

Lo que sí importa, y es lo que se chequea acá:

  · LARGO. Es la única variable que crece exponencialmente. Para una clave que
    se pega una vez en un archivo, 16 caracteres no le cuesta nada a nadie y
    deja afuera todo lo que alguien pueda escribir de memoria en el momento.
  · QUE NO SEA CONOCIDA. La mayoría de los ataques no prueban combinaciones:
    prueban listas. Una clave larguísima que ya está en una lista filtrada no
    vale nada.
  · QUE NO SEA ADIVINABLE DESDE LO PÚBLICO. El email del admin, el nombre del
    producto, el dominio: todo eso lo sabe cualquiera que mire la landing.
  · QUE TENGA VARIEDAD. `abababababababab` tiene 16 caracteres y dos símbolos
    distintos. El largo solo sirve si hay algo adentro.

EL CASO PARTICULAR DE ESTE REPO
────────────────────────────────
`admin@turnos360.com` / `superadmin360` están escritos en `seeds_minimo.py`,
en un repositorio PÚBLICO, como valores de desarrollo. Cualquiera los lee.
Están explícitamente en la lista de rechazadas: no es hipotético.
"""


class ClaveDebil(ValueError):
    """La clave no sirve para la cuenta que se le quiere poner."""


LARGO_MINIMO = 16
VARIEDAD_MINIMA = 8  # caracteres distintos

# Las obvias, más las que este repo publicó en su propio código.
_CONOCIDAS = {
    "superadmin360", "admin", "administrador", "administrator", "root",
    "turnos360", "turnos", "password", "contraseña", "contrasena",
    "123456", "1234567890", "12345678", "qwerty", "abc123", "111111",
    "password1", "password123", "admin123", "admin1234", "letmein",
    "changeme", "cambiar", "cambiame", "secret", "clave", "clave123",
    "iloveyou", "welcome", "monkey", "dragon", "master", "sunshine",
    "cambiar-en-produccion", "test", "prueba", "demo",
}


def _es_secuencia(clave: str) -> bool:
    """`abcdefghijklmnop`, `123456789012` y sus reversos."""
    if len(clave) < 4:
        return False
    pasos = {ord(b) - ord(a) for a, b in zip(clave, clave[1:])}
    return pasos in ({1}, {-1})


def _es_repeticion(clave: str) -> bool:
    """¿Es un bloque corto repetido? `abcabcabcabc`, `1234567890` × 2.

    Lo agregué porque un test me lo encontró: `12345678901234567890` pasaba
    los otros tres controles. Tiene veinte caracteres (largo, bien), diez
    distintos (variedad, bien) y no es una cuesta corrida porque el 9 vuelve
    al 0 (secuencia, bien). Y es, obviamente, una de las peores claves
    posibles.

    Un bloque que se repite no agrega fuerza: la clave vale lo que vale el
    bloque, no lo que mide el total.
    """
    n = len(clave)
    for largo in range(1, n // 2 + 1):
        if n % largo == 0 and clave[:largo] * (n // largo) == clave:
            return True
    return False


def revisar_clave_superadmin(clave: str, email: str = "") -> None:
    """Lanza ClaveDebil con un motivo entendible, o no hace nada.

    El mensaje dice QUÉ está mal y CÓMO arreglarlo. Un error que solo dice
    "clave inválida" termina en alguien probando variantes hasta que pasa, que
    es justo lo contrario de lo que se busca.
    """
    clave = clave or ""
    receta = (
        "Generá una así:  python -c \"import secrets; "
        'print(secrets.token_urlsafe(24))\"'
    )

    plana = clave.strip().lower()

    # Esta va PRIMERO aunque la clave también sea corta: el motivo real es
    # mucho más útil. "superadmin360" no es mala por tener 13 caracteres, es
    # mala porque está escrita en un repositorio público.
    if plana in _CONOCIDAS:
        raise ClaveDebil(
            "Esa clave está en las listas que prueba cualquier atacante antes "
            "que nada — y algunas, como «superadmin360», salen del código "
            f"público de este mismo repositorio. {receta}"
        )

    if len(clave) < LARGO_MINIMO:
        raise ClaveDebil(
            f"La clave del super-admin tiene {len(clave)} caracteres y el "
            f"mínimo son {LARGO_MINIMO}. Esta cuenta controla el alta de "
            f"TODAS las empresas y no se tipea a diario: no hay motivo para "
            f"que sea corta. {receta}"
        )

    if len(set(clave)) < VARIEDAD_MINIMA:
        raise ClaveDebil(
            f"La clave repite demasiado: tiene {len(set(clave))} caracteres "
            f"distintos y hacen falta {VARIEDAD_MINIMA}. El largo solo sirve "
            f"si hay algo adentro. {receta}"
        )

    if _es_secuencia(clave):
        raise ClaveDebil(
            "La clave es una secuencia corrida del teclado o del abecedario. "
            f"Es larga y no sirve. {receta}"
        )

    if _es_repeticion(clave):
        raise ClaveDebil(
            "La clave es un pedazo corto repetido. Vale lo que vale ese "
            f"pedazo, no lo que mide entera. {receta}"
        )

    if email:
        local = email.split("@")[0].strip().lower()
        dominio = email.split("@")[-1].split(".")[0].strip().lower()
        for pedazo in (email.strip().lower(), local, dominio):
            if pedazo and len(pedazo) >= 3 and pedazo in plana:
                raise ClaveDebil(
                    f"La clave contiene «{pedazo}», que es parte del email del "
                    "admin. Eso lo sabe cualquiera que vea la página. "
                    f"{receta}"
                )
