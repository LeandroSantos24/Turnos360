"""/estado: lo que mira el monitor externo.

Protege que:
  · responda 200 SOLO si base, Redis y las tareas programadas andan;
  · un worker o beat caído (latido viejo o ausente) dé 503 — antes nadie se
    enteraba: la web andaba y los recordatorios dejaban de salir;
  · no haya falsa alarma en los primeros minutos después de un deploy;
  · el cuerpo no exponga nombres de excepciones, versiones ni hosts;
  · la tarea `latido` esté en beat y deje la marca que /estado lee.
"""

import time

import pytest
import redis

from app.celery_app import celery_app
from app.core import observabilidad as obs
from app.core.config import settings


@pytest.fixture()
def r():
    cliente = redis.from_url(settings.redis_url)
    cliente.delete(obs.LATIDO_CLAVE)
    yield cliente
    cliente.delete(obs.LATIDO_CLAVE)


def _estado(client):
    resp = client.get("/estado")
    return resp.status_code, resp.json()


def test_todo_andando_da_200_y_solo_ok_falla(client, r):
    r.set(obs.LATIDO_CLAVE, str(time.time()))
    codigo, cuerpo = _estado(client)
    assert codigo == 200
    assert cuerpo == {"status": "ok", "base": "ok", "redis": "ok", "tareas": "ok"}


def test_base_caida_da_503_sin_detalles_tecnicos(client, r, monkeypatch):
    r.set(obs.LATIDO_CLAVE, str(time.time()))
    monkeypatch.setattr(obs, "_base_responde", lambda: (False, "OperationalError"))
    codigo, cuerpo = _estado(client)
    assert codigo == 503
    assert cuerpo["status"] == "falla" and cuerpo["base"] == "falla"
    assert "OperationalError" not in str(cuerpo)


def test_redis_caido_da_503(client, monkeypatch):
    monkeypatch.setattr(obs, "_redis_responde", lambda: (False, "ConnectionError"))
    codigo, cuerpo = _estado(client)
    assert codigo == 503
    assert cuerpo["redis"] == "falla" and cuerpo["tareas"] == "falla"
    assert "ConnectionError" not in str(cuerpo)


def test_worker_o_beat_parados_dan_503(client, r):
    r.set(obs.LATIDO_CLAVE, str(time.time() - obs.LATIDO_VENCE_S - 60))
    codigo, cuerpo = _estado(client)
    assert codigo == 503
    assert cuerpo["tareas"] == "atrasadas"


def test_sin_latido_recien_desplegado_no_es_falsa_alarma(client, r, monkeypatch):
    monkeypatch.setattr(obs, "_ARRANQUE", time.time())
    codigo, cuerpo = _estado(client)
    assert codigo == 200
    assert cuerpo["tareas"] == "esperando"


def test_sin_latido_pasado_el_margen_es_caida(client, r, monkeypatch):
    monkeypatch.setattr(obs, "_ARRANQUE", time.time() - obs.LATIDO_VENCE_S - 60)
    codigo, cuerpo = _estado(client)
    assert codigo == 503
    assert cuerpo["tareas"] == "sin latido"


def test_la_tarea_latido_deja_la_marca_que_lee_estado(client, r, monkeypatch):
    monkeypatch.setattr(obs, "_ARRANQUE", time.time() - obs.LATIDO_VENCE_S - 60)
    from app.tasks.latido import latido

    latido()
    assert 0 < r.ttl(obs.LATIDO_CLAVE) <= 3600, "La marca tiene que expirar sola."
    assert _estado(client)[0] == 200


def test_beat_dispara_el_latido_bien_dentro_del_margen():
    entrada = celery_app.conf.beat_schedule["latido"]
    assert entrada["task"] == "app.tasks.latido.latido"
    # Con tres latidos perdidos recién se declara caído: un reintento o una
    # cola cargada no alcanza para una falsa alarma.
    assert entrada["schedule"] * 3 <= obs.LATIDO_VENCE_S


def test_ready_sigue_sin_mirar_las_tareas(client, r, monkeypatch):
    """El healthcheck del contenedor usa /ready: un worker caído no puede
    marcar al backend como enfermo."""
    monkeypatch.setattr(obs, "_ARRANQUE", time.time() - obs.LATIDO_VENCE_S - 60)
    assert client.get("/ready").status_code == 200
