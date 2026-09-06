"""Que las variables del .env realmente lleguen al backend.

EL BUG QUE ORIGINÓ ESTO, Y POR QUÉ ES DIFÍCIL DE VER
────────────────────────────────────────────────────
Leandro tenía sus datos de cobro en el .env —CBU, alias, titular, CUIT— y el
circuito de transferencia no funcionaba: «quise subir de plan y no me mandó a
MP o transferir». La pantalla decide si mostrar «Cómo pagar» mirando si hay CBU
o alias; sin ellos, el botón avisa que hay que transferir y después no muestra
a dónde.

Las variables estaban. Lo que faltaba era el puente: el `.env` alimenta la
SUSTITUCIÓN del docker-compose, no se copia solo adentro del contenedor. Una
variable que no está listada en el bloque `environment:` simplemente no existe
para el proceso, y no hay ningún error — `settings.cobro_cbu` es "" y todo
sigue andando, mal.

Eran DOCE las que no llegaban: las seis de cobro, dos de la firma del webhook
de Mercado Pago y cuatro de WhatsApp.

Este test compara .env.example (que documenta lo que el sistema entiende)
contra lo que el compose realmente pasa. Lee los archivos como texto: sin
docker, sin parsear YAML, y falla nombrando la variable que falta.
"""

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# Las que no van al backend a propósito: son del motor de la base, del
# navegador, o las arma el compose por su cuenta.
NO_VAN = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "DATABASE_URL",
    "REDIS_URL",
    "CORS_ORIGINS",
    "NEXT_PUBLIC_API_URL",
    "CELERY_CONCURRENCY",
}


def _claves_del_env(ruta: pathlib.Path) -> set[str]:
    if not ruta.exists():
        return set()
    return {
        linea.split("=", 1)[0].strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#") and "=" in linea
    }


def _claves_del_backend(ruta: pathlib.Path) -> set[str]:
    """Las variables que el compose le pasa al servicio `backend`."""
    texto = ruta.read_text(encoding="utf-8")
    # Del `backend:` hasta el siguiente servicio de primer nivel.
    m = re.search(r"^  backend:\n(.*?)(?=^  [a-z_]+:|\Z)", texto, re.S | re.M)
    if not m:
        return set()
    return set(re.findall(r"^      ([A-Z_][A-Z0-9_]*):", m.group(1), re.M))


def _exigir(ruta: pathlib.Path) -> None:
    """Saltea con motivo si el archivo no está, en vez de aprobar en silencio.

    ESTE TEST NO COMPARABA NADA ADENTRO DEL CONTENEDOR. `RAIZ` se calcula como
    `parents[2]` del archivo de test: en la máquina da la raíz del repo, pero
    en el contenedor —donde el backend está montado en /app— da `/`, y ahí no
    existía ni /infra ni /.env.example. El `if not existe: return` convertía
    eso en un punto verde. Un test que no puede fallar ocupa el lugar del que
    sí protegía, y este es justo el que cuida las catorce variables que no
    llegaban.

    Ahora los dos archivos van montados (ver infra/docker-compose.yml), así que
    esto corre de verdad en los dos lados. Si igual faltan, se ve.
    """
    if not ruta.exists():
        pytest.skip(
            f"No encuentro {ruta}. Adentro del contenedor tiene que estar "
            "montado (volúmenes ../infra:/infra y ../.env.example en "
            "infra/docker-compose.yml). Este chequeo no corrió."
        )


def test_todo_lo_documentado_llega_al_backend_en_desarrollo():
    compose = RAIZ / "infra/docker-compose.yml"
    _exigir(RAIZ / ".env.example")
    _exigir(compose)

    documentadas = _claves_del_env(RAIZ / ".env.example") - NO_VAN
    llegan = _claves_del_backend(compose)
    faltan = sorted(documentadas - llegan)

    assert not faltan, (
        "Estas variables están en .env.example pero el compose NO se las pasa "
        f"al backend, así que el proceso las ve vacías: {faltan}. "
        "Agregalas al bloque `environment:` del servicio backend."
    )


def test_ninguna_variable_esta_repetida():
    """Una clave repetida en el mismo `environment:` es YAML ambiguo: gana una
    de las dos y no hay forma de saber cuál sin probarlo."""
    _exigir(RAIZ / "infra/docker-compose.yml")
    for nombre in ("infra/docker-compose.yml", "infra/docker-compose.prod.yml"):
        ruta = RAIZ / nombre
        if not ruta.exists():
            continue
        texto = ruta.read_text(encoding="utf-8")
        for m in re.finditer(r"^  ([a-z_]+):\n(.*?)(?=^  [a-z_]+:|\Z)", texto, re.S | re.M):
            claves = re.findall(r"^      ([A-Z_][A-Z0-9_]*):", m.group(2), re.M)
            repetidas = sorted({k for k in claves if claves.count(k) > 1})
            assert not repetidas, f"{nombre} · servicio {m.group(1)}: {repetidas}"


def test_el_worker_recibe_lo_mismo_que_el_backend():
    """El worker manda los emails y aplica las bajas. Con menos variables que
    el backend, una tarea puede fallar por una config que en la API está —y el
    síntoma aparece en otro lado, horas después."""
    compose = RAIZ / "infra/docker-compose.yml"
    _exigir(compose)

    texto = compose.read_text(encoding="utf-8")
    def claves(servicio: str) -> set[str]:
        m = re.search(rf"^  {servicio}:\n(.*?)(?=^  [a-z_]+:|\Z)", texto, re.S | re.M)
        return set(re.findall(r"^      ([A-Z_][A-Z0-9_]*):", m.group(1), re.M)) if m else set()

    # Estas SÍ son solo del backend, y no por olvido:
    #  · API_BASE_URL: el worker no arma URLs para el navegador.
    #  · SUPERADMIN_*: las lee `docker compose exec backend python -m
    #    app.seeds_minimo`, un comando que se corre a mano en ESE contenedor.
    #    Copiarlas al worker sería repartir la clave del super-admin por
    #    procesos que no la usan.
    solo_del_backend = {"API_BASE_URL", "SUPERADMIN_EMAIL", "SUPERADMIN_PASS"}
    faltan = sorted(claves("backend") - claves("worker") - solo_del_backend)
    assert not faltan, f"Al worker le faltan variables que el backend sí tiene: {faltan}"
