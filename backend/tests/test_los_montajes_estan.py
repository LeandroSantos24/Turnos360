"""Que los chequeos entre frontend y backend PUEDAN correr adentro del contenedor.

POR QUÉ ESTE ARCHIVO EXISTE
───────────────────────────
Siete tests de la suite comparan cosas escritas en TypeScript contra su
equivalente en Python: la grilla de precios de `precios.ts` contra `planes.py`,
las formas del logo de `tema-vidriera.ts` contra el Literal del schema. Para
eso leen archivos del frontend y de infra/ como texto.

Adentro del contenedor del backend esos archivos solo existen si están
MONTADOS. Si no están, los siete se saltean — y un salteo es silencioso: en la
salida es una `s` entre novecientas `.`, y en dos corridas ya nadie lo mira.
Los guardas quedan en la lista, parecen cubrir algo, y no cubren nada.

Ya pasó dos veces, y la segunda por un motivo que no se ve en ningún lado:
`docker compose restart` NO relee el compose. Reinicia el proceso adentro del
contenedor que ya existe, con los volúmenes que ese contenedor tenía. Para que
un volumen nuevo entre hay que RECREAR el contenedor
(`up -d --force-recreate`). Es una distinción que no se nota hasta que algo
falla, y acá lo que "fallaba" era un test que aprobaba.

QUÉ HACE ESTO
─────────────
Convierte siete salteos callados en UN test rojo que dice el comando. Solo
corre adentro del contenedor: en tu máquina, donde el repo está entero, no
tiene nada que verificar y se saltea con motivo.
"""

import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# Lo que cada montaje hace posible. El archivo es el testigo; la frase es lo
# que se pierde si falta, dicha en términos de qué deja de estar protegido.
MONTAJES = [
    (
        "/frontend/src/lib/precios.ts",
        "../frontend/src:/frontend/src:ro",
        "los precios de la landing y la forma del logo dejan de compararse "
        "contra el backend",
    ),
    (
        "/infra/docker-compose.yml",
        "../infra:/infra:ro",
        "los defaults de precio del compose dejan de compararse contra la grilla",
    ),
    (
        "/.env.example",
        "../.env.example:/.env.example:ro",
        "deja de verificarse que las variables del .env lleguen al contenedor",
    ),
]


def _adentro_del_contenedor() -> bool:
    """¿Estamos corriendo en el contenedor del backend?

    Ahí el código está montado en /app, así que `parents[2]` de este archivo
    da `/`. En la máquina da la raíz del repo, que tiene backend/ adentro.
    """
    return RAIZ == pathlib.Path("/") and pathlib.Path("/app/tests").is_dir()


def test_los_archivos_que_comparan_frontend_y_backend_estan_montados():
    """Un test rojo con el comando, en vez de siete salteos callados."""
    if not _adentro_del_contenedor():
        pytest.skip(
            "Fuera del contenedor el repo está entero y no hay nada que "
            "montar. Este chequeo es para la corrida en Docker, que es donde "
            "los archivos del frontend pueden no estar."
        )

    faltan = [
        (ruta, volumen, consecuencia)
        for ruta, volumen, consecuencia in MONTAJES
        if not pathlib.Path(ruta).exists()
    ]
    if not faltan:
        return

    detalle = "\n".join(
        f"  · falta {ruta}  (volumen {volumen})\n      sin esto, {consecuencia}"
        for ruta, volumen, consecuencia in faltan
    )
    pytest.fail(
        "Este contenedor no tiene los montajes que necesitan los chequeos "
        "entre el frontend y el backend, así que esos tests se van a saltear "
        f"sin comparar nada:\n\n{detalle}\n\n"
        "SON DOS CAUSAS POSIBLES Y SE DISTINGUEN EN UN SEGUNDO:\n\n"
        "  grep -n 'frontend/src' infra/docker-compose.yml\n\n"
        "· No aparece → al repo le falta el cambio que agrega los volúmenes. "
        "Ese es el arreglo, no tocar Docker.\n"
        "· Aparece → el contenedor es viejo. `docker compose restart` NO relee "
        "el compose: reinicia el proceso adentro del contenedor que ya existe, "
        "con los volúmenes que ese contenedor tenía. Hay que RECREARLO:\n\n"
        "    docker compose up -d --force-recreate --no-build backend\n"
    )
