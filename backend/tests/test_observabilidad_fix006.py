"""Regresión del fix-006: observabilidad.

La auditoría encontró que el sistema era ciego en producción: sin logging
configurado, sin manejador global de excepciones, sin alertas, y con un
/health que devolvía "ok" incondicionalmente —o sea, que mentía— mientras
Postgres estuviera caído.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import observabilidad as obs
from app.core.logging import configurar_logging, nuevo_request_id, request_id_var

from .conftest import token_de


# ══════════════════════════════════════════════════════════════════════
# /health y /ready
# ══════════════════════════════════════════════════════════════════════

def test_health_responde_siempre_sin_mirar_dependencias(client):
    """Es liveness: si mirara la base, un Postgres caído reiniciaría el
    backend en bucle, borrando los logs que explicarían el problema."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_consulta_la_base_de_verdad(client):
    """Antes /health devolvía ok sin consultar nada."""
    r = client.get("/ready")
    cuerpo = r.json()
    assert "base" in cuerpo and "redis" in cuerpo
    assert cuerpo["base"] == "ok", (
        "La base está disponible en los tests: /ready tiene que decirlo."
    )


def test_ready_avisa_cuando_la_base_no_responde(client, monkeypatch):
    """El caso que importa: que NO diga 'ok' cuando algo está roto."""
    monkeypatch.setattr(obs, "_base_responde", lambda: (False, "OperationalError"))
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degradado"
    assert r.json()["base"] == "OperationalError"


def test_ready_avisa_cuando_redis_no_responde(client, monkeypatch):
    monkeypatch.setattr(obs, "_base_responde", lambda: (True, "ok"))
    monkeypatch.setattr(obs, "_redis_responde", lambda: (False, "ConnectionError"))
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["redis"] == "ConnectionError"


# ══════════════════════════════════════════════════════════════════════
# Identificador de pedido
# ══════════════════════════════════════════════════════════════════════

def test_toda_respuesta_trae_un_id_de_pedido(client):
    """Es lo que el usuario te pasa cuando reporta 'me tiró error'."""
    r = client.get("/health")
    assert r.headers.get("X-Request-Id"), "Falta el header X-Request-Id"


def test_se_respeta_el_id_que_manda_el_proxy(client):
    """Permite seguir una traza de punta a punta."""
    r = client.get("/health", headers={"X-Request-Id": "traza-de-prueba"})
    assert r.headers["X-Request-Id"] == "traza-de-prueba"


def test_cada_pedido_tiene_un_id_distinto(client):
    a = client.get("/health").headers["X-Request-Id"]
    b = client.get("/health").headers["X-Request-Id"]
    assert a != b


def test_el_id_de_pedido_se_recorta_si_es_absurdo(client):
    """Un header gigante no puede terminar en el log ni en la respuesta."""
    r = client.get("/health", headers={"X-Request-Id": "x" * 500})
    assert len(r.headers["X-Request-Id"]) <= 64


# ══════════════════════════════════════════════════════════════════════
# Manejador global de excepciones
# ══════════════════════════════════════════════════════════════════════

def _app_que_explota() -> TestClient:
    """Una app mínima con la observabilidad enganchada y una ruta que falla."""
    mini = FastAPI()
    obs.registrar_observabilidad(mini)

    @mini.get("/explota")
    def explota():
        raise RuntimeError("secreto: la tabla pago de la empresa 7")

    return TestClient(mini, raise_server_exceptions=False)


def test_un_error_no_controlado_devuelve_500_con_id_rastreable():
    r = _app_que_explota().get("/explota")
    assert r.status_code == 500
    cuerpo = r.json()
    assert cuerpo.get("request_id"), "El 500 tiene que traer el id para rastrearlo"
    assert cuerpo["request_id"] in cuerpo["detalle"]


def test_un_error_no_controlado_no_filtra_el_detalle_al_cliente():
    """El mensaje de una excepción puede traer nombres de tablas, consultas
    o valores de otra empresa. No sale nunca."""
    r = _app_que_explota().get("/explota")
    texto = r.text
    assert "secreto" not in texto
    assert "RuntimeError" not in texto
    assert "Traceback" not in texto


def test_el_error_queda_logueado_con_el_id(caplog):
    import logging

    with caplog.at_level(logging.ERROR, logger="turnos360"):
        r = _app_que_explota().get("/explota")
    rid = r.json()["request_id"]
    registros = [x for x in caplog.records if x.levelno >= logging.ERROR]
    assert registros, "El error no quedó logueado"
    assert any(getattr(x, "request_id", None) == rid for x in registros), (
        "El log del error no lleva el id del pedido: sin eso no se puede "
        "asociar el reclamo del cliente con la traza."
    )


# ══════════════════════════════════════════════════════════════════════
# La tarea de reseteo de contraseña, que no existía
# ══════════════════════════════════════════════════════════════════════

def test_la_tarea_de_reseteo_de_contrasena_existe():
    """routers/auth.py la importaba y no estaba definida: el ImportError caía
    en un except que solo loguea, así que el mail NUNCA salía."""
    from app.tasks.emails import enviar_reset_password

    assert callable(enviar_reset_password)


def test_la_tarea_de_reseteo_esta_registrada_en_celery():
    from app.celery_app import celery_app

    assert "app.tasks.emails.enviar_reset_password" in celery_app.tasks, (
        "La tarea existe pero Celery no la conoce: el .delay() del router "
        "seguiría fallando."
    )


def test_olvide_password_no_revela_si_la_cuenta_existe(client, db, armar_empresa):
    """Se mantiene el comportamiento: misma respuesta exista o no el email."""
    ctx = armar_empresa()
    db.commit()

    r1 = client.post("/auth/olvide-password", json={"email": ctx.dueno.email})
    r2 = client.post("/auth/olvide-password", json={"email": "noexiste@ejemplo.com"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()


# ══════════════════════════════════════════════════════════════════════
# Celery: no perder tareas
# ══════════════════════════════════════════════════════════════════════

def test_celery_confirma_las_tareas_despues_de_ejecutarlas():
    """Sin acks_late, un worker que muere a mitad pierde la tarea en silencio."""
    from app.celery_app import celery_app

    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_celery_reintenta_ante_fallas_transitorias():
    """Antes no había ningún reintento: el primer error de Gmail era un email
    perdido para siempre."""
    from app.celery_app import celery_app

    anotaciones = celery_app.conf.task_annotations or {}
    reglas = anotaciones.get("*", {})
    assert reglas.get("max_retries", 0) >= 1
    assert reglas.get("retry_backoff")


# ══════════════════════════════════════════════════════════════════════
# El módulo de logging
# ══════════════════════════════════════════════════════════════════════

def test_el_formato_json_incluye_el_contexto():
    import json
    import logging

    from app.core.logging import ContextoFilter, FormatoJSON

    token = request_id_var.set("abc123")
    registro = logging.LogRecord(
        "turnos360", logging.INFO, "x.py", 1, "hola %s", ("mundo",), None
    )
    ContextoFilter().filter(registro)
    salida = json.loads(FormatoJSON().format(registro))
    request_id_var.reset(token)

    assert salida["mensaje"] == "hola mundo"
    assert salida["request_id"] == "abc123"
    assert salida["nivel"] == "INFO"


def test_configurar_logging_no_rompe_al_llamarse_dos_veces():
    """Se llama al importar app.main; que un import doble no explote."""
    configurar_logging(nivel="INFO", json_salida=False)
    configurar_logging(nivel="INFO", json_salida=True)
    configurar_logging(nivel="INFO", json_salida=False)


def test_los_ids_de_pedido_son_unicos():
    ids = {nuevo_request_id() for _ in range(500)}
    assert len(ids) == 500


def test_los_logs_de_un_pedido_autenticado_llevan_la_empresa(
    client, db, armar_empresa, caplog
):
    """Sin esto, un error dice "falló un pedido". Con esto dice de quién."""
    import logging

    ctx = armar_empresa()
    db.commit()

    with caplog.at_level(logging.INFO, logger="turnos360"):
        r = client.get("/clientes", headers=token_de(ctx.dueno))
    assert r.status_code == 200

    accesos = [x for x in caplog.records if getattr(x, "ruta", None) == "/clientes"]
    assert accesos, "No quedó línea de acceso para el pedido"
    assert any(
        getattr(x, "empresa_id", "-") == str(ctx.empresa.id) for x in accesos
    ), "La línea de acceso no lleva el empresa_id del pedido"
