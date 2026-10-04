"""Sentry: reporta errores sin llevarse datos sensibles y sin volverse crítico.

Qué protege cada test:
  · sin DSN no se inicia nada (el estado de hoy en desarrollo y en tests);
  · un DSN mal escrito NO tumba la API (antes: sentry_sdk.init levantaba
    BadDsn en el import de main.py y el backend no arrancaba);
  · un error no controlado llega a Sentry con tipo, ruta y stack trace, y SIN
    cuerpo, query, Authorization, emails ni tokens de MP;
  · con Sentry caído la API responde igual y rápido;
  · el worker y beat se reportan con su propio componente.

No sale nada a la red: los eventos van a un transporte en memoria, y el test
de "Sentry caído" apunta a un puerto cerrado de localhost.
"""

import json
import time

import pytest
import sentry_sdk
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.core import observabilidad
from app.core.config import settings

DSN_FALSO = "https://clavepublica@o0.ingest.sentry.io/0"

# Valores que NUNCA pueden aparecer en lo que se manda a Sentry.
CLAVE = "MiClaveSecreta2026"
EMAIL = "ana.perez@gmail.com"
TOKEN_MP = "APP_USR-1234567890123456-abcdef-ghijkl"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0MiJ9.firmaFalsaDelToken123"
TOKEN_QS = "tokenDeVerificacion987654"
CBU = "0110012340001234567890"


class _EnMemoria(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.eventos: list[dict] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type in ("event", "transaction"):
                self.eventos.append(item.payload.json)


@pytest.fixture()
def capturador(monkeypatch):
    """Sentry con DSN y transporte en memoria; al final lo deja apagado."""
    transporte = _EnMemoria()
    original = sentry_sdk.init

    def init_en_memoria(*a, **k):
        k["transport"] = transporte
        return original(*a, **k)

    monkeypatch.setattr(sentry_sdk, "init", init_en_memoria)
    monkeypatch.setattr(settings, "sentry_dsn", DSN_FALSO)
    yield transporte
    sentry_sdk.get_client().close(timeout=0)
    original()  # sin DSN: cliente apagado para el resto de la suite


def _app_que_falla() -> FastAPI:
    app = FastAPI()
    observabilidad.registrar_observabilidad(app)

    @app.post("/cobrar")
    def cobrar(datos: dict):
        raise RuntimeError(
            f"MP rechazó el cobro de {EMAIL} con token {TOKEN_MP} (CBU {CBU})"
        )

    @app.get("/no-existe")
    def no_existe():
        raise HTTPException(status_code=404, detail="no")

    @app.get("/sano")
    def sano():
        return {"ok": True}

    return app


def _pegar(cliente: TestClient):
    return cliente.post(
        f"/cobrar?token={TOKEN_QS}&pagina=2",
        json={"email": EMAIL, "clave": CLAVE, "access_token": TOKEN_MP},
        headers={"Authorization": f"Bearer {JWT}", "Cookie": f"sesion={JWT}"},
    )


def test_sin_dsn_no_se_inicia(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "")
    assert observabilidad.iniciar_sentry() is False


def test_un_dsn_mal_escrito_no_tumba_la_api(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "esto no es un dsn")
    assert observabilidad.iniciar_sentry() is False  # y no levantó


def test_un_error_llega_a_sentry_sin_datos_sensibles(capturador):
    assert observabilidad.iniciar_sentry("api") is True
    r = _pegar(TestClient(_app_que_falla(), raise_server_exceptions=False))
    assert r.status_code == 500
    assert "request_id" in r.json()
    sentry_sdk.flush(timeout=2)

    assert capturador.eventos, "El error no controlado tiene que llegar a Sentry."
    crudo = json.dumps(capturador.eventos, ensure_ascii=False)

    # Lo que sirve para depurar, está.
    assert "RuntimeError" in crudo
    assert "/cobrar" in crudo
    assert "test_sentry_observabilidad.py" in crudo  # stack trace
    assert '"componente": "api"' in crudo

    # Lo sensible, no.
    for secreto in (CLAVE, EMAIL, TOKEN_MP, JWT, TOKEN_QS, CBU):
        assert secreto not in crudo, f"Se filtró a Sentry: {secreto[:12]}…"
    for evento in capturador.eventos:
        pedido = evento.get("request", {})
        assert "data" not in pedido, "El cuerpo del pedido no se manda."
        assert "cookies" not in pedido
        assert "user" not in evento
        for frame in _frames(evento):
            assert "vars" not in frame, "Las variables locales no se mandan."


def test_un_4xx_no_es_un_error_de_sentry(capturador):
    observabilidad.iniciar_sentry("api")
    r = TestClient(_app_que_falla()).get("/no-existe")
    assert r.status_code == 404
    sentry_sdk.flush(timeout=2)
    assert capturador.eventos == []


def test_con_sentry_caido_la_api_responde_igual(monkeypatch):
    # Puerto 9 (discard) de localhost: nadie escucha, la conexión se rechaza.
    monkeypatch.setattr(settings, "sentry_dsn", "http://clave@127.0.0.1:9/1")
    try:
        assert observabilidad.iniciar_sentry("api") is True
        cliente = TestClient(_app_que_falla(), raise_server_exceptions=False)
        inicio = time.perf_counter()
        for _ in range(5):
            assert _pegar(cliente).status_code == 500
            assert cliente.get("/sano").status_code == 200
        assert time.perf_counter() - inicio < 3, "Sentry caído no puede frenar pedidos."
    finally:
        sentry_sdk.get_client().close(timeout=0)
        sentry_sdk.init()


def test_el_worker_y_beat_se_reportan_con_su_componente(capturador):
    from celery.signals import beat_init, celeryd_init

    import app.celery_app  # noqa: F401 — registra las señales

    for senal, componente in ((celeryd_init, "worker"), (beat_init, "beat")):
        senal.send(sender=None)
        sentry_sdk.capture_message(f"prueba {componente}")
        sentry_sdk.flush(timeout=2)
        assert capturador.eventos[-1]["tags"]["componente"] == componente


def test_limpiar_evento_tapa_lo_que_otros_caminos_podrian_traer():
    evento = {
        "request": {
            "url": f"https://turnos360.com.ar/api/x?token={TOKEN_QS}",
            "query_string": f"token={TOKEN_QS}&id=5",
            "headers": {"Authorization": f"Bearer {JWT}", "X-Real-IP": "1.2.3.4",
                        "User-Agent": "Mozilla"},
            "data": {"clave": CLAVE},
        },
        "extra": {"cliente_email": EMAIL, "detalle": f"falló con {TOKEN_MP}"},
        "breadcrumbs": {"values": [{"message": f"login de {EMAIL}", "data": {"cbu": CBU}}]},
        "user": {"ip_address": "1.2.3.4"},
    }
    limpio = observabilidad.limpiar_evento(evento)
    crudo = json.dumps(limpio)
    for secreto in (TOKEN_QS, JWT, CLAVE, EMAIL, TOKEN_MP, CBU, "1.2.3.4"):
        assert secreto not in crudo
    assert limpio["request"]["query_string"] == "token=[Filtrado]&id=[Filtrado]"
    assert limpio["request"]["headers"]["User-Agent"] == "Mozilla"


def _frames(evento):
    for exc in (evento.get("exception") or {}).get("values", []):
        yield from (exc.get("stacktrace") or {}).get("frames", [])
