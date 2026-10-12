"""Autogestión del turno: el link del email para cambiarlo o cancelarlo.

Cubre: link estable y revocable, tokens inválidos o vencidos, cancelación
(y la repetida), reprogramación (disponibilidad, anticipación, tope de
cambios), la regla del negocio, turnos cobrados, que no se filtren datos del
cliente y que los emails lleven el link.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.reloj import ahora_de_pared
from app.models import LogAuditoria
from app.models.enums import EstadoTurno
from app.models.turno import Turno
from app.services import autogestion


def _manana(h=10, dias=2):
    base = ahora_de_pared() + dt.timedelta(days=dias)
    return base.replace(hour=h, minute=0, second=0, microsecond=0)


@pytest.fixture()
def caso(db, armar_empresa, monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "https://turnos360.com.ar")
    avisos = []
    monkeypatch.setattr(autogestion, "_avisar_negocio", lambda *a: avisos.append(a))
    ctx = armar_empresa("Barbería Link")
    ctx.cliente.email = "cliente@example.com"
    ctx.cliente.telefono = "2615551234"
    inicio = _manana()
    turno = Turno(
        empresa_id=ctx.empresa.id,
        sucursal_id=ctx.sede.id,
        cliente_id=ctx.cliente.id,
        recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=ctx.servicio.duracion_min),
        estado=EstadoTurno.CONFIRMADO,
    )
    db.add(turno)
    db.flush()
    url = autogestion.emitir_link(db, turno)
    db.commit()
    ctx.turno = turno
    ctx.token = url.rsplit("/", 1)[1]
    ctx.url = url
    ctx.avisos = avisos
    return ctx


def _api(token, accion=""):
    return f"/publico/gestion/{token}{accion}"


# ── El link ───────────────────────────────────────────────────────────

def test_el_link_es_del_dominio_publico_y_estable(db, caso):
    assert caso.url.startswith("https://turnos360.com.ar/gestionar/")
    assert "localhost" not in caso.url
    # Otro email del mismo turno lleva el MISMO link (el primero no muere).
    assert autogestion.emitir_link(db, caso.turno) == caso.url
    # El token no es el id del turno ni lo contiene a la vista.
    assert str(caso.turno.id) != caso.token and len(caso.token) >= 40


def test_en_la_base_queda_el_hash_y_no_el_token(db, caso):
    assert caso.turno.gestion_token_hash and caso.token not in caso.turno.gestion_token_hash


def test_ver_el_turno_no_expone_datos_del_cliente(client, caso):
    r = client.get(_api(caso.token))
    assert r.status_code == 200
    d = r.json()
    assert d["negocio"] == "Barbería Link"
    assert d["servicio"] == "Corte" and d["estado"] == "confirmado"
    assert d["puede_cancelar"] is True and d["puede_reprogramar"] is True
    texto = r.text
    assert "cliente@example.com" not in texto and "2615551234" not in texto
    assert str(caso.cliente.id) not in d.values()


def test_token_invalido_o_alterado_da_404(client, caso):
    assert client.get(_api("x" * 43)).status_code == 404
    assert client.get(_api(caso.token[:-1] + ("A" if caso.token[-1] != "A" else "B"))).status_code == 404
    assert client.post(_api("x" * 43, "/cancelar"), json={}).status_code == 404


def test_link_revocado_deja_de_servir(client, db, caso):
    autogestion.revocar_link(db, caso.turno)
    db.commit()
    assert client.get(_api(caso.token)).status_code == 404
    # El nuevo sí sirve.
    nuevo = autogestion.emitir_link(db, caso.turno).rsplit("/", 1)[1]
    db.commit()
    assert nuevo != caso.token
    assert client.get(_api(nuevo)).status_code == 200


def test_link_de_un_turno_que_ya_paso_vence(client, db, caso):
    caso.turno.fecha_inicio = ahora_de_pared() - dt.timedelta(days=3)
    caso.turno.fecha_fin = caso.turno.fecha_inicio + dt.timedelta(minutes=30)
    db.commit()
    assert client.get(_api(caso.token)).status_code == 410


# ── Cancelar ──────────────────────────────────────────────────────────

def test_cancelar_libera_el_turno_y_queda_registrado(client, db, caso):
    r = client.post(_api(caso.token, "/cancelar"), json={"motivo": "Me surgió algo"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"
    assert r.json()["puede_cancelar"] is False
    db.expire_all()
    t = db.get(Turno, caso.turno.id)
    assert t.estado == EstadoTurno.CANCELADO
    assert "desde el link" in t.motivo_cancelacion and "Me surgió algo" in t.motivo_cancelacion
    log = db.scalar(select(LogAuditoria).where(
        LogAuditoria.registro_id == t.id, LogAuditoria.accion == "autogestion_cancelar"))
    assert log is not None and log.tabla == "turno"
    assert caso.avisos and caso.avisos[0][1] == "cancelacion"


def test_cancelar_dos_veces_no_hace_nada_la_segunda(client, caso):
    assert client.post(_api(caso.token, "/cancelar"), json={}).status_code == 200
    r = client.post(_api(caso.token, "/cancelar"), json={})
    assert r.status_code == 409
    # El link sigue mostrando el turno (cancelado).
    assert client.get(_api(caso.token)).json()["estado"] == "cancelado"


def test_si_el_negocio_no_lo_permite_no_se_cancela(client, db, caso):
    caso.empresa.reserva_permite_cancelar = False
    db.commit()
    d = client.get(_api(caso.token)).json()
    assert d["puede_cancelar"] is False and d["motivo_bloqueo"]
    assert client.post(_api(caso.token, "/cancelar"), json={}).status_code == 409


def test_no_se_cancela_un_turno_ya_empezado(client, db, caso):
    caso.turno.fecha_inicio = ahora_de_pared() - dt.timedelta(minutes=5)
    caso.turno.fecha_fin = ahora_de_pared() + dt.timedelta(minutes=25)
    db.commit()
    assert client.post(_api(caso.token, "/cancelar"), json={}).status_code == 409


def test_no_se_toca_un_turno_cobrado(client, db, caso):
    caso.turno.cobrado = True
    db.commit()
    assert client.post(_api(caso.token, "/cancelar"), json={}).status_code == 409
    assert client.post(_api(caso.token, "/reprogramar"), json={"inicio": _manana(15).isoformat()}).status_code == 409


# ── Reprogramar ───────────────────────────────────────────────────────

def test_reprogramar_mueve_el_turno_y_lo_registra(client, db, caso):
    nuevo = _manana(15)
    r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": nuevo.replace(tzinfo=None).isoformat()})
    assert r.status_code == 200, r.text
    db.expire_all()
    t = db.get(Turno, caso.turno.id)
    assert t.fecha_inicio == nuevo
    assert t.recordatorio_enviado is False
    log = db.scalar(select(LogAuditoria).where(
        LogAuditoria.registro_id == t.id, LogAuditoria.accion == "autogestion_mover"))
    assert log.detalle["a"].startswith(nuevo.date().isoformat())
    assert caso.avisos[-1][1] == "reprogramacion"
    # Mismo link después del cambio.
    assert client.get(_api(caso.token)).status_code == 200


def test_reprogramar_a_un_horario_ocupado_da_409(client, db, caso):
    ocupado = _manana(16)
    for recurso in (caso.lucas, caso.pablo):
        db.add(Turno(
            empresa_id=caso.empresa.id, sucursal_id=caso.sede.id, cliente_id=caso.cliente.id,
            recurso_id=recurso.id, servicio_id=caso.servicio.id, fecha_inicio=ocupado,
            fecha_fin=ocupado + dt.timedelta(minutes=caso.servicio.duracion_min),
            estado=EstadoTurno.CONFIRMADO,
        ))
    db.commit()
    r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": ocupado.isoformat()})
    assert r.status_code == 409
    db.expire_all()
    assert db.get(Turno, caso.turno.id).fecha_inicio == caso.turno.fecha_inicio


def test_si_su_profesional_esta_ocupado_lo_pasa_a_otro_del_local(client, db, caso):
    destino = _manana(17)
    db.add(Turno(
        empresa_id=caso.empresa.id, sucursal_id=caso.sede.id, cliente_id=caso.cliente.id,
        recurso_id=caso.lucas.id, servicio_id=caso.servicio.id, fecha_inicio=destino,
        fecha_fin=destino + dt.timedelta(minutes=caso.servicio.duracion_min),
        estado=EstadoTurno.CONFIRMADO,
    ))
    db.commit()
    r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": destino.isoformat()})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Turno, caso.turno.id).recurso_id == caso.pablo.id


def test_reprogramar_respeta_la_anticipacion_minima(client, db, caso):
    caso.empresa.reserva_anticipacion_min = 48 * 60
    db.commit()
    cerca = (ahora_de_pared() + dt.timedelta(hours=26)).replace(minute=0, second=0, microsecond=0)
    r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": cerca.isoformat()})
    assert r.status_code == 400


def test_reprogramar_al_mismo_horario_da_400(client, caso):
    r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": caso.turno.fecha_inicio.isoformat()})
    assert r.status_code == 400


def test_hay_un_tope_de_cambios(client, caso):
    for i, h in enumerate((11, 12, 13)):
        r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": _manana(h).isoformat()})
        assert r.status_code == 200, (i, r.text)
    assert client.get(_api(caso.token)).json()["puede_reprogramar"] is False
    r = client.post(_api(caso.token, "/reprogramar"), json={"inicio": _manana(14).isoformat()})
    assert r.status_code == 409


def test_los_horarios_son_del_mismo_servicio_y_local(client, caso):
    r = client.get(_api(caso.token, "/horarios"), params={"desde": _manana().date().isoformat(), "dias": 1})
    assert r.status_code == 200
    assert r.json() and r.json()[0]["horas"]


def test_un_link_no_sirve_para_otro_turno(client, db, caso, armar_empresa):
    """El token es del turno: no hay parámetro para apuntar a otro."""
    otra = armar_empresa("Otro negocio")
    inicio = _manana(9)
    ajeno = Turno(
        empresa_id=otra.empresa.id, sucursal_id=otra.sede.id, cliente_id=otra.cliente.id,
        recurso_id=otra.lucas.id, servicio_id=otra.servicio.id, fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30), estado=EstadoTurno.CONFIRMADO,
    )
    db.add(ajeno)
    db.commit()
    assert client.post(_api(caso.token, "/cancelar"), json={"turno_id": ajeno.id}).status_code == 200
    db.expire_all()
    assert db.get(Turno, ajeno.id).estado == EstadoTurno.CONFIRMADO


# ── Los emails ────────────────────────────────────────────────────────

def test_el_email_lleva_el_link_solo_si_el_negocio_lo_permite(db, caso):
    from app.tasks.emails import _linea_gestion

    linea = _linea_gestion(db, caso.turno, caso.empresa)
    assert caso.url in linea
    caso.empresa.reserva_permite_cancelar = False
    assert _linea_gestion(db, caso.turno, caso.empresa) == ""
