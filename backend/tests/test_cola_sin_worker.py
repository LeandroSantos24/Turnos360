"""El email sale igual cuando no hay worker de Celery escuchando.

EL BUG QUE FIJAN ESTOS TESTS
────────────────────────────
`tarea.delay(...)` devuelve OK aunque no haya nadie del otro lado de la cola.
El mensaje queda en Redis para siempre, la API contesta «te lo mandamos» y el
email no sale nunca. Es el estado normal de una máquina de desarrollo sin
`docker compose up worker`, y de cualquier servidor donde el worker se cayó.

El síntoma que se ve —«el mail de verificación no llega»— manda a buscar el
problema a SMTP, a Gmail o a la carpeta de spam, cuando la tarea directamente
no se ejecutó.
"""

import pytest

from app.core import cola


@pytest.fixture(autouse=True)
def _sin_cache_de_ping():
    """El resultado del ping se cachea 15 s; entre tests hay que olvidarlo."""
    cola._ultimo_ping = None
    yield
    cola._ultimo_ping = None


class TareaFalsa:
    """Imita a una tarea de Celery: tiene .delay() y .run()."""

    name = "tarea.falsa"

    def __init__(self, delay_explota=False, run_explota=False):
        self.delay_explota = delay_explota
        self.run_explota = run_explota
        self.encolada_con = None
        self.ejecutada_con = None

    def delay(self, *a, **k):
        if self.delay_explota:
            raise RuntimeError("redis caído")
        self.encolada_con = (a, k)

    def run(self, *a, **k):
        if self.run_explota:
            raise RuntimeError("smtp rechazó")
        self.ejecutada_con = (a, k)


def test_sin_worker_la_tarea_se_ejecuta_en_linea(monkeypatch):
    """Lo importante: el trabajo se hace igual, no se pierde en la cola."""
    monkeypatch.setattr(cola, "hay_worker", lambda: False)
    tarea = TareaFalsa()

    assert cola.encolar(tarea, 7, token="abc") is cola.Resultado.EN_LINEA
    assert tarea.ejecutada_con == ((7,), {"token": "abc"})
    assert tarea.encolada_con is None


def test_con_worker_se_encola_y_no_se_ejecuta_en_el_request(monkeypatch):
    """En producción sigue yendo por la cola: un SMTP lento no bloquea la API."""
    monkeypatch.setattr(cola, "hay_worker", lambda: True)
    tarea = TareaFalsa()

    assert cola.encolar(tarea, 7) is cola.Resultado.ENCOLADA
    assert tarea.encolada_con == ((7,), {})
    assert tarea.ejecutada_con is None


def test_si_encolar_falla_igual_se_intenta_en_linea(monkeypatch):
    """El worker contestó el ping y Redis se cayó un segundo después."""
    monkeypatch.setattr(cola, "hay_worker", lambda: True)
    tarea = TareaFalsa(delay_explota=True)

    assert cola.encolar(tarea, 7) is cola.Resultado.EN_LINEA
    assert tarea.ejecutada_con == ((7,), {})


def test_si_tambien_falla_en_linea_lo_dice_en_vez_de_mentir(monkeypatch):
    """La mitad importante del arreglo: quien llama se entera de que falló."""
    monkeypatch.setattr(cola, "hay_worker", lambda: False)
    tarea = TareaFalsa(run_explota=True)

    assert cola.encolar(tarea, 7) is cola.Resultado.FALLO


def test_un_broker_inalcanzable_cuenta_como_sin_worker(monkeypatch):
    """Ante la duda, ejecutar en línea: el lado seguro para equivocarse.

    Decir que hay worker cuando no lo hay pierde el mensaje. Decir que no
    cuando sí lo hay solo lo manda por el camino lento.
    """
    class ControlRoto:
        def ping(self, timeout=None):
            raise OSError("connection refused")

    class CeleryRoto:
        control = ControlRoto()

    monkeypatch.setattr("app.celery_app.celery_app", CeleryRoto())
    assert cola.hay_worker() is False


def test_el_ping_se_cachea_para_no_preguntar_en_cada_request(monkeypatch):
    """Sin caché, cada alta pagaría un ida y vuelta contra Redis por algo que
    no cambia de un segundo al otro."""
    llamadas = {"n": 0}

    class Control:
        def ping(self, timeout=None):
            llamadas["n"] += 1
            return [{"worker@host": {"ok": "pong"}}]

    class CeleryVivo:
        control = Control()

    monkeypatch.setattr("app.celery_app.celery_app", CeleryVivo())
    assert cola.hay_worker() is True
    assert cola.hay_worker() is True
    assert cola.hay_worker() is True
    assert llamadas["n"] == 1
