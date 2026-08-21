"""Regresión del fix-014: los hallazgos de seguridad que quedaban abiertos.

Cuatro cosas, y cada una tiene un porqué concreto:

  · el seed de demo publicaba un usuario y una clave de super-admin en un
    repo PÚBLICO, sin ninguna guarda de producción
  · un profesional veía la facturación del local en cada fila de su agenda
  · las lecturas de historia clínica no dejaban rastro, aunque el comentario
    del modelo prometía desde E1 que sí
  · el webhook de Mercado Pago no miraba la firma
"""

import datetime as dt
import hashlib
import hmac
import pathlib

import pytest
from sqlalchemy import select

from app.core import firma_mp
from app.core.config import settings
from app.core.crypto import hash_clave
from app.models import LogAuditoria, Usuario
from app.models.enums import EstadoTurno, RolUsuario
from app.models.turno import Turno

from .conftest import token_de


# ══════════════════════════════════════════════════════════════════════════
#  1. El seed ya no publica una clave
# ══════════════════════════════════════════════════════════════════════════


def test_la_clave_vieja_ya_no_esta_escrita_en_el_codigo():
    """`superadmin360` estaba en un repo público. Que no vuelva nunca."""
    import app.seeds as seeds_mod

    fuente = pathlib.Path(seeds_mod.__file__).read_text(encoding="utf-8")
    # Ni en el código ni en un comentario: una clave que estuvo publicada no
    # se vuelve a escribir "de ejemplo", porque el próximo que lea el archivo
    # la va a probar.
    assert "superadmin360" not in fuente
    # Y el super-admin usa la del entorno, no un literal.
    assert "hash_clave(sa_clave)" in fuente
    # (Los usuarios de las empresas ficticias sí conservan su clave de demo:
    # son negocios inventados dentro de un seed que ya no corre en producción.)


def test_el_super_admin_del_seed_sale_del_entorno(monkeypatch):
    from app.seeds import _credenciales_superadmin

    monkeypatch.setenv("SUPERADMIN_EMAIL", "jefe@turnos360.com")
    monkeypatch.setenv("SUPERADMIN_PASS", "una-clave-larga-y-propia")
    email, clave, generada = _credenciales_superadmin()

    assert email == "jefe@turnos360.com"
    assert clave == "una-clave-larga-y-propia"
    assert generada is False


def test_sin_clave_en_el_entorno_se_genera_una_al_azar(monkeypatch):
    from app.seeds import _credenciales_superadmin

    monkeypatch.delenv("SUPERADMIN_PASS", raising=False)
    _, clave1, generada = _credenciales_superadmin()
    _, clave2, _ = _credenciales_superadmin()

    assert generada is True
    assert len(clave1) >= 20
    assert clave1 != clave2            # aleatoria de verdad
    assert clave1 != "superadmin360"


def test_el_seed_de_demo_no_corre_en_produccion(monkeypatch):
    """Carga negocios ficticios: en una base real es basura indistinguible."""
    import app.seeds as seeds_mod

    monkeypatch.setattr(type(settings), "es_produccion", property(lambda self: True))
    with pytest.raises(SystemExit) as e:
        seeds_mod.run()
    assert "producción" in str(e.value)
    assert "seeds_minimo" in str(e.value)


def test_en_desarrollo_el_seed_sigue_corriendo(monkeypatch):
    """La guarda no puede romperle el flujo de trabajo a nadie."""
    import app.seeds as seeds_mod

    monkeypatch.setattr(type(settings), "es_produccion", property(lambda self: False))
    llamadas = {}

    class _SesionFalsa:
        def query(self, *a):
            llamadas["consulto"] = True
            return self

        def count(self):
            return 1        # "ya hay rubros": el seed corta solo, sin escribir

        def close(self):
            pass

    monkeypatch.setattr(seeds_mod, "SessionLocal", lambda: _SesionFalsa())
    seeds_mod.run()          # no tiene que levantar
    assert llamadas.get("consulto") is True


# ══════════════════════════════════════════════════════════════════════════
#  2. La plata del negocio no es del profesional
# ══════════════════════════════════════════════════════════════════════════


def _turno_con_plata(db, ctx) -> Turno:
    inicio = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)
    t = Turno(
        empresa_id=ctx.empresa.id,
        cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id,
        recurso_id=ctx.lucas.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=EstadoTurno.CONFIRMADO,
        importe_previsto=15000,
        sena_monto=5000,
        sena_estado="pagada",
    )
    db.add(t)
    db.flush()
    return t


def test_el_profesional_ve_su_agenda_sin_un_solo_importe(client, db, armar_empresa):
    """El barbero no tiene por qué saber cuánto factura el local."""
    ctx = armar_empresa()
    _turno_con_plata(db, ctx)

    r = client.get("/turnos", headers=token_de(ctx.profesional))
    assert r.status_code == 200
    fila = r.json()["items"][0]

    assert fila["total"] == 0
    assert fila["senado"] == 0
    assert fila["pagado_total"] == 0
    assert fila["saldo"] is None
    assert fila["sena_monto"] is None
    assert fila["importe_previsto"] is None


def test_el_profesional_sigue_viendo_lo_que_necesita(client, db, armar_empresa):
    """Ocultar la plata no puede dejarlo sin poder trabajar."""
    ctx = armar_empresa()
    turno = _turno_con_plata(db, ctx)

    fila = client.get("/turnos", headers=token_de(ctx.profesional)).json()["items"][0]

    assert fila["id"] == turno.id
    assert fila["cliente_nombre"]
    assert fila["estado"] == "confirmado"
    # `cobrado` es un booleano operativo, no un importe: lo necesita para no
    # pedirle plata de nuevo a alguien que ya pagó.
    assert "cobrado" in fila


def test_el_dueno_si_ve_los_importes(client, db, armar_empresa):
    """Control: el filtro tiene que aplicar SOLO al profesional."""
    ctx = armar_empresa()
    _turno_con_plata(db, ctx)

    fila = client.get("/turnos", headers=token_de(ctx.dueno)).json()["items"][0]
    assert fila["importe_previsto"] == 15000
    assert fila["sena_monto"] == 5000


def test_el_detalle_de_un_turno_tambien_va_sin_plata(client, db, armar_empresa):
    """La agenda pide el turno suelto al abrir el detalle."""
    ctx = armar_empresa()
    turno = _turno_con_plata(db, ctx)

    r = client.get(f"/turnos/{turno.id}", headers=token_de(ctx.profesional))
    assert r.status_code == 200
    assert r.json()["importe_previsto"] is None
    assert r.json()["saldo"] is None

    del_dueno = client.get(f"/turnos/{turno.id}", headers=token_de(ctx.dueno)).json()
    assert del_dueno["importe_previsto"] == 15000


def test_al_marcar_el_turno_en_curso_tampoco_le_vuelve_la_plata(
    client, db, armar_empresa
):
    """Es la respuesta que recibe cuando toca «empezar» en su pantalla."""
    ctx = armar_empresa()
    turno = _turno_con_plata(db, ctx)

    r = client.patch(
        f"/turnos/{turno.id}/estado",
        json={"estado": "en_curso"},
        headers=token_de(ctx.profesional),
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "en_curso"
    assert r.json()["importe_previsto"] is None
    assert r.json()["total"] == 0


# ══════════════════════════════════════════════════════════════════════════
#  3. Quién leyó la historia clínica de quién
# ══════════════════════════════════════════════════════════════════════════


def _logs_de(db, empresa_id) -> list[LogAuditoria]:
    return list(
        db.scalars(
            select(LogAuditoria).where(
                LogAuditoria.empresa_id == empresa_id,
                LogAuditoria.accion == "leer_ficha",
            )
        )
    )


def test_leer_la_ficha_de_un_paciente_deja_rastro(client, db, armar_empresa):
    """El comentario del modelo lo prometía desde E1 y no se registraba nada."""
    ctx = armar_empresa("Consultorio")

    client.get(
        f"/pacientes/{ctx.cliente.id}/ficha", headers=token_de(ctx.dueno)
    )

    fila = _logs_de(db, ctx.empresa.id)[0]
    assert fila.usuario_id == ctx.dueno.id
    assert fila.registro_id == ctx.cliente.id
    assert fila.tabla == "ficha_clinica"
    assert fila.detalle["que"] == "ficha"
    assert fila.detalle["rol"] == "dueno"


def test_se_registra_incluso_si_el_paciente_no_tiene_ficha(client, db, armar_empresa):
    """El daño de este dato es que alguien lo MIRE. El intento también cuenta."""
    ctx = armar_empresa("Consultorio")

    r = client.get(f"/pacientes/{ctx.cliente.id}/ficha", headers=token_de(ctx.dueno))

    assert r.status_code == 404          # no tiene ficha todavía
    assert len(_logs_de(db, ctx.empresa.id)) == 1


@pytest.mark.parametrize(
    "recurso,que",
    [("entradas", "entradas"), ("mediciones", "mediciones"), ("adjuntos", "adjuntos")],
)
def test_tambien_se_auditan_controles_mediciones_y_adjuntos(
    client, db, armar_empresa, recurso, que
):
    ctx = armar_empresa("Consultorio")

    r = client.get(
        f"/pacientes/{ctx.cliente.id}/{recurso}", headers=token_de(ctx.dueno)
    )

    assert r.status_code == 200
    fila = _logs_de(db, ctx.empresa.id)[0]
    assert fila.detalle["que"] == que


def test_queda_registrado_el_profesional_que_mira(client, db, armar_empresa):
    """El caso real: el empleado que se fija los antecedentes de la vecina."""
    ctx = armar_empresa("Consultorio")

    client.get(f"/pacientes/{ctx.cliente.id}/ficha", headers=token_de(ctx.profesional))

    fila = _logs_de(db, ctx.empresa.id)[0]
    assert fila.usuario_id == ctx.profesional.id
    assert fila.detalle["rol"] == "profesional"


def test_recepcion_sigue_sin_poder_leer_la_ficha(client, db, armar_empresa):
    """Control: el fix no puede haber abierto una puerta."""
    ctx = armar_empresa("Consultorio")
    recepcion = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Recepción",
        email=f"recep14-{ctx.empresa.slug}@example.com",
        hash_clave=hash_clave("x"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recepcion)
    db.flush()

    r = client.get(f"/pacientes/{ctx.cliente.id}/ficha", headers=token_de(recepcion))

    assert r.status_code == 403
    assert _logs_de(db, ctx.empresa.id) == []   # ni siquiera llegó a auditar


# ══════════════════════════════════════════════════════════════════════════
#  4. La firma de Mercado Pago
# ══════════════════════════════════════════════════════════════════════════


SECRETO = "secreto-de-mp"


def _firma_valida(data_id: str, ts: str = "1704908010", req_id: str = "abc-123") -> dict:
    texto = firma_mp.manifiesto(data_id, req_id, ts)
    v1 = hmac.new(SECRETO.encode(), texto.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": req_id}


def test_el_manifiesto_se_arma_como_lo_documenta_mp():
    assert (
        firma_mp.manifiesto("123456", "req-1", "1704908010")
        == "id:123456;request-id:req-1;ts:1704908010;"
    )


def test_el_id_con_letras_va_en_minusculas():
    """Los de pago son numéricos, pero si alguna vez trae letras y no lo
    bajamos, la firma no cierra y no hay forma de darse cuenta."""
    assert firma_mp.manifiesto("AbC9", None, "1") == "id:abc9;ts:1;"


def test_los_segmentos_que_no_vienen_se_omiten():
    assert firma_mp.manifiesto("9", None, None) == "id:9;"


def test_sin_secreto_configurado_no_se_puede_opinar(client, monkeypatch):
    monkeypatch.setattr(settings, "mp_webhook_secret", "")
    pedido = _pedido_falso({})
    assert firma_mp.verificar(pedido, "123") is None


class _PedidoFalso:
    def __init__(self, headers):
        self.headers = headers


def _pedido_falso(headers) -> _PedidoFalso:
    return _PedidoFalso(headers)


def test_una_firma_correcta_verifica(monkeypatch):
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.verificar(_pedido_falso(_firma_valida("999")), "999") is True


def test_una_firma_de_otro_pago_no_verifica(monkeypatch):
    """La firma ata el secreto AL payment_id: no se puede reusar."""
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.verificar(_pedido_falso(_firma_valida("999")), "111") is False


def test_sin_encabezado_de_firma_no_verifica(monkeypatch):
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.verificar(_pedido_falso({}), "999") is False


def test_una_firma_inventada_no_verifica(monkeypatch):
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    cabeceras = {"x-signature": "ts=1,v1=" + "0" * 64, "x-request-id": "abc-123"}
    assert firma_mp.verificar(_pedido_falso(cabeceras), "999") is False


def test_en_modo_off_pasa_todo(monkeypatch):
    """El default. Se tiene que comportar EXACTAMENTE como antes del fix."""
    monkeypatch.setattr(settings, "mp_firma_modo", "off")
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.acepta(_pedido_falso({}), "999") is True


def test_en_modo_log_avisa_pero_deja_pasar(monkeypatch):
    """Es el punto del modo: confirmar contra tráfico real sin cortar señas."""
    monkeypatch.setattr(settings, "mp_firma_modo", "log")
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.acepta(_pedido_falso({}), "999") is True


def test_en_modo_enforce_una_firma_mala_no_pasa(monkeypatch):
    monkeypatch.setattr(settings, "mp_firma_modo", "enforce")
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.acepta(_pedido_falso({}), "999") is False


def test_en_modo_enforce_una_firma_buena_pasa(monkeypatch):
    monkeypatch.setattr(settings, "mp_firma_modo", "enforce")
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    assert firma_mp.acepta(_pedido_falso(_firma_valida("999")), "999") is True


def test_enforce_sin_secreto_no_corta_las_senas(monkeypatch):
    """Cortar todos los pagos por un .env incompleto sería peor que el ataque."""
    monkeypatch.setattr(settings, "mp_firma_modo", "enforce")
    monkeypatch.setattr(settings, "mp_webhook_secret", "")
    assert firma_mp.acepta(_pedido_falso({}), "999") is True


def test_el_webhook_en_enforce_ignora_una_notificacion_sin_firma(
    client, db, armar_empresa, monkeypatch
):
    """De punta a punta: sin firma no se toca ni la base ni la red."""
    monkeypatch.setattr(settings, "mp_firma_modo", "enforce")
    monkeypatch.setattr(settings, "mp_webhook_secret", SECRETO)
    ctx = armar_empresa()

    tocado = {}
    import app.routers.publico as publico_mod

    monkeypatch.setattr(
        publico_mod,
        "_procesar_notificacion_mp",
        lambda *a, **k: tocado.setdefault("si", True),
    )

    r = client.post(
        f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=123456789"
    )

    assert r.status_code == 200          # siempre 200, o MP reintenta para siempre
    assert tocado == {}                  # pero no procesó nada


def test_el_webhook_en_off_procesa_como_siempre(
    client, db, armar_empresa, monkeypatch
):
    """Control de no-regresión: con el default, nada cambió."""
    monkeypatch.setattr(settings, "mp_firma_modo", "off")
    ctx = armar_empresa()

    tocado = {}
    import app.routers.publico as publico_mod

    monkeypatch.setattr(
        publico_mod,
        "_procesar_notificacion_mp",
        lambda *a, **k: tocado.setdefault("si", True),
    )

    client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=123456789")

    assert tocado == {"si": True}


def test_un_id_que_no_es_numerico_sigue_muriendo_antes(client, armar_empresa, monkeypatch):
    """La defensa del fix-005 contra el amplificador sigue en pie."""
    monkeypatch.setattr(settings, "mp_firma_modo", "off")
    ctx = armar_empresa()

    tocado = {}
    import app.routers.publico as publico_mod

    monkeypatch.setattr(
        publico_mod, "_procesar_notificacion_mp", lambda *a, **k: tocado.setdefault("si", True)
    )

    client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=abc")
    assert tocado == {}
