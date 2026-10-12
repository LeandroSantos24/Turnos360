"""Sesiones en el servidor, último ingreso y alta de usuarios por invitación."""

import datetime as dt
import uuid

import pytest

from app.core import cola
from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import AuditoriaAdmin, InvitacionUsuario, SesionUsuario, SuperAdmin, Usuario
from app.services import sesiones

from .conftest import token_de

UA_CHROME_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
)


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(nombre="Admin Test", email=f"sa-{uuid.uuid4().hex}@turnos360.test", hash_clave=hash_clave("clave1234"))
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


@pytest.fixture()
def sin_worker(monkeypatch):
    monkeypatch.setattr(cola, "hay_worker", lambda: False)


def _login(client, ctx, ua=UA_CHROME_ANDROID):
    r = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave}, headers={"User-Agent": ua}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _cab(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ══════════════════════════════════════════════════════════════════════
# Sesiones
# ══════════════════════════════════════════════════════════════════════

def test_login_crea_sesion_con_dispositivo_y_ultimo_ingreso(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _login(client, ctx)
    s = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).one()
    assert s.dispositivo == "Chrome en Android"
    assert s.revocada_en is None and s.refresh_jti
    db.refresh(ctx.dueno)
    assert ctx.dueno.ultimo_ingreso_en is not None
    # No se guarda el user-agent completo.
    assert not hasattr(s, "user_agent")
    assert client.get("/auth/me", headers=_cab(t)).status_code == 200


def test_ultimo_uso_se_actualiza_como_mucho_una_vez_por_minuto(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _login(client, ctx)
    s = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).one()
    viejo = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)
    s.ultimo_uso_en = viejo
    db.commit()
    client.get("/auth/me", headers=_cab(t))
    db.refresh(s)
    assert s.ultimo_uso_en > viejo
    marca = s.ultimo_uso_en
    client.get("/auth/me", headers=_cab(t))
    db.refresh(s)
    assert s.ultimo_uso_en == marca


def test_revocar_una_sesion_corta_esa_y_no_las_demas(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    a = _login(client, ctx)
    b = _login(client, ctx, ua="Mozilla/5.0 (Windows NT 10.0) Gecko/20100101 Firefox/130.0")
    sa = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).order_by(SesionUsuario.id).all()
    assert len(sa) == 2

    r = client.post(
        f"/admin/usuarios/{ctx.dueno.id}/sesiones/{sa[0].id}/revocar",
        headers=admin, json={"motivo": "Celular perdido"},
    )
    assert r.status_code == 200, r.text
    estados = {x["id"]: x["estado"] for x in r.json()["sesiones"]}
    assert estados[sa[0].id] == "revocada" and estados[sa[1].id] == "activa"

    # La revocada no sirve ni para un request ni para renovar.
    assert client.get("/auth/me", headers=_cab(a)).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": a["refresh_token"]}).status_code == 401
    # La otra sigue.
    assert client.get("/auth/me", headers=_cab(b)).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": b["refresh_token"]}).status_code == 200
    assert db.query(AuditoriaAdmin).filter_by(accion="revocar_sesion", empresa_id=ctx.empresa.id).count() == 1


def test_revocar_dos_veces_o_sesion_de_otro_usuario(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    otro = armar_empresa()
    _login(client, ctx)
    s = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).one()
    # La sesión de un usuario no se puede cerrar desde la ficha de otro.
    r = client.post(
        f"/admin/usuarios/{otro.dueno.id}/sesiones/{s.id}/revocar", headers=admin, json={"motivo": "prueba"}
    )
    assert r.status_code == 404
    url = f"/admin/usuarios/{ctx.dueno.id}/sesiones/{s.id}/revocar"
    assert client.post(url, headers=admin, json={"motivo": "prueba"}).status_code == 200
    assert client.post(url, headers=admin, json={"motivo": "prueba"}).status_code == 409
    # Motivo obligatorio.
    assert client.post(url, headers=admin, json={"motivo": ""}).status_code == 422


def test_cerrar_todas_corta_tambien_los_tokens_viejos_sin_sesion(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    nueva = _login(client, ctx)
    viejo = token_de(ctx.dueno)  # emitido como antes de las sesiones: sin 'sid'
    assert client.get("/auth/me", headers=viejo).status_code == 200

    r = client.post(f"/admin/usuarios/{ctx.dueno.id}/cerrar-sesiones", headers=admin, json={"motivo": "Sospecha de acceso ajeno"})
    assert r.status_code == 200, r.text
    assert r.json()["activas"] == 0
    assert client.get("/auth/me", headers=_cab(nueva)).status_code == 401
    assert client.get("/auth/me", headers=viejo).status_code == 401
    assert db.query(AuditoriaAdmin).filter_by(accion="cerrar_sesiones", empresa_id=ctx.empresa.id).count() == 1


def test_refresh_rota_y_un_refresh_reutilizado_cierra_la_sesion(client, db, armar_empresa):
    ctx = armar_empresa()
    t1 = _login(client, ctx)
    t2 = client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]}).json()
    assert client.get("/auth/me", headers=_cab(t2)).status_code == 200
    # Dentro de la gracia, el anterior todavía sirve (dos pestañas a la vez).
    assert client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]}).status_code == 200
    # Pasada la gracia, reusar un refresh viejo se trata como robo.
    s = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).one()
    s.rotado_en = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    db.commit()
    r = client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert r.status_code == 401
    db.refresh(s)
    assert s.revocada_en is not None and "refresh" in s.motivo_revocacion


def test_refresh_de_token_viejo_lo_pasa_a_una_sesion(client, db, armar_empresa):
    from .conftest import refresh_de

    ctx = armar_empresa()
    r = client.post("/auth/refresh", json={"refresh_token": refresh_de(ctx.dueno)})
    assert r.status_code == 200
    assert db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).count() == 1
    assert client.get("/auth/me", headers=_cab(r.json())).status_code == 200


def test_logout_cierra_la_sesion_en_el_servidor(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _login(client, ctx)
    assert client.post("/auth/logout", headers=_cab(t)).status_code == 200
    assert client.get("/auth/me", headers=_cab(t)).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


def test_cambiar_clave_deja_solo_la_sesion_nueva(client, db, armar_empresa):
    ctx = armar_empresa()
    otra = _login(client, ctx)
    actual = _login(client, ctx)
    r = client.post(
        "/auth/cambiar-password", headers=_cab(actual),
        json={"clave_actual": ctx.clave, "clave_nueva": "otraClave987"},
    )
    assert r.status_code == 200, r.text
    assert client.get("/auth/me", headers=_cab(otra)).status_code == 401
    assert client.get("/auth/me", headers=_cab(r.json())).status_code == 200
    filas = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).all()
    assert sum(1 for s in filas if sesiones.estado_de(s, ctx.dueno) == "activa") == 1


def test_sesiones_solo_para_super_admin(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _login(client, ctx)
    assert client.get(f"/admin/usuarios/{ctx.dueno.id}/sesiones", headers=_cab(t)).status_code == 401
    assert client.get(f"/admin/usuarios/{ctx.dueno.id}/sesiones").status_code in (401, 403)


def test_ficha_de_actividad(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    _login(client, ctx)
    r = client.get(f"/admin/usuarios/{ctx.dueno.id}/sesiones", headers=admin)
    assert r.status_code == 200
    d = r.json()
    assert d["usuario"]["ultimo_ingreso_en"] and d["activas"] == 1
    assert d["historial"][0]["tipo"] == "ingreso"
    assert "sid" not in d["sesiones"][0] and "refresh_jti" not in d["sesiones"][0]


def test_cortar_acceso_marca_las_sesiones(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    _login(client, ctx)
    r = client.post(f"/admin/usuarios/{ctx.dueno.id}/acceso", headers=admin, json={"activo": False})
    assert r.status_code == 200
    s = db.query(SesionUsuario).filter_by(usuario_id=ctx.dueno.id).one()
    assert s.revocada_en is not None and s.motivo_revocacion == "Se cortó el acceso"


# ══════════════════════════════════════════════════════════════════════
# Invitaciones
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture()
def capturar(monkeypatch):
    """Intercepta el email: guarda el token en vez de mandarlo."""
    enviados: list[tuple[int, str]] = []

    def falso_encolar(tarea, *args, **kwargs):
        enviados.append(args)
        return cola.Resultado.EN_LINEA

    monkeypatch.setattr(cola, "encolar", falso_encolar)
    return enviados


def _invitar(client, admin, ctx, email=None):
    email = email or f"nuevo-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/usuarios",
        headers=admin, json={"nombre": "Nuevo Usuario", "email": email, "rol": "recepcion"},
    )
    assert r.status_code == 201, r.text
    return r.json(), email


def test_invitacion_de_punta_a_punta(client, db, armar_empresa, admin, capturar):
    ctx = armar_empresa()
    u, email = _invitar(client, admin, ctx)
    assert u["activacion_pendiente"] is True
    assert "clave" not in u and "token" not in str(u)
    inv_id, token = capturar[-1]
    inv = db.get(InvitacionUsuario, inv_id)
    assert inv.token_hash != token and len(inv.token_hash) == 64

    # Antes de activar no entra ni puede pedir «olvidé mi contraseña».
    assert client.post("/auth/login", json={"email": email, "clave": "cualquiera123"}).status_code == 401
    usuario = db.get(Usuario, u["id"])
    client.post("/auth/olvide-password", json={"email": email})
    db.refresh(usuario)
    assert usuario.reset_token_hash is None

    v = client.post("/auth/invitacion", json={"token": token})
    assert v.status_code == 200 and v.json()["negocio"] == ctx.empresa.nombre
    assert "@" in v.json()["email"] and email not in v.json()["email"]

    a = client.post("/auth/activar", json={"token": token, "clave": "miClaveNueva1"})
    assert a.status_code == 200, a.text
    db.refresh(usuario)
    assert not usuario.activacion_pendiente and usuario.email_verificado
    assert client.post("/auth/login", json={"email": email, "clave": "miClaveNueva1"}).status_code == 200
    # Uso único.
    assert client.post("/auth/activar", json={"token": token, "clave": "otraClave999"}).status_code == 400


def test_token_invalido_o_vencido_responden_igual(client, db, armar_empresa, admin, capturar):
    ctx = armar_empresa()
    _invitar(client, admin, ctx)
    inv_id, token = capturar[-1]
    malo = client.post("/auth/invitacion", json={"token": "x" * 43})
    inv = db.get(InvitacionUsuario, inv_id)
    inv.expira_en = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    db.commit()
    vencido = client.post("/auth/invitacion", json={"token": token})
    assert malo.status_code == vencido.status_code == 400
    assert malo.json() == vencido.json()
    assert client.post("/auth/activar", json={"token": token, "clave": "miClaveNueva1"}).status_code == 400


def test_reenviar_revoca_el_link_anterior(client, db, armar_empresa, admin, capturar):
    ctx = armar_empresa()
    u, _ = _invitar(client, admin, ctx)
    _, viejo = capturar[-1]
    r = client.post(f"/admin/usuarios/{u['id']}/invitacion/reenviar", headers=admin)
    assert r.status_code == 200, r.text
    _, nuevo = capturar[-1]
    assert nuevo != viejo
    assert client.post("/auth/invitacion", json={"token": viejo}).status_code == 400
    assert client.post("/auth/invitacion", json={"token": nuevo}).status_code == 200
    vigentes = db.query(InvitacionUsuario).filter(
        InvitacionUsuario.usuario_id == u["id"], InvitacionUsuario.revocada_en.is_(None), InvitacionUsuario.usada_en.is_(None)
    ).count()
    assert vigentes == 1


def test_revocar_invitacion(client, db, armar_empresa, admin, capturar):
    ctx = armar_empresa()
    u, _ = _invitar(client, admin, ctx)
    _, token = capturar[-1]
    r = client.post(f"/admin/usuarios/{u['id']}/invitacion/revocar", headers=admin)
    assert r.status_code == 200 and r.json()["estado"] == "sin_invitacion"
    assert client.post("/auth/activar", json={"token": token, "clave": "miClaveNueva1"}).status_code == 400
    # Una cuenta ya activa no tiene invitación que reenviar.
    assert client.post(f"/admin/usuarios/{ctx.dueno.id}/invitacion/reenviar", headers=admin).status_code == 409


def test_si_el_mail_falla_queda_anotado_y_se_puede_reenviar(client, db, armar_empresa, admin, sin_worker, monkeypatch):
    from app.core import mailer

    def roto(*a, **k):
        raise OSError("SMTP caído")

    import contextlib

    from app.tasks import emails

    # La tarea abre su propia sesión de base; acá tiene que ver la del test.
    monkeypatch.setattr(emails, "SessionLocal", lambda: contextlib.nullcontext(db))
    monkeypatch.setattr(mailer, "enviar", roto)
    ctx = armar_empresa()
    u, _ = _invitar(client, admin, ctx)
    lista = client.get(f"/admin/empresas/{ctx.empresa.id}/usuarios", headers=admin).json()
    fila = next(x for x in lista if x["id"] == u["id"])
    assert fila["invitacion"]["estado"] == "envio_fallido"
    assert "SMTP" not in fila["invitacion"]["envio_error"]  # no se expone el error crudo

    monkeypatch.setattr(mailer, "enviar", lambda *a, **k: None)
    r = client.post(f"/admin/usuarios/{u['id']}/invitacion/reenviar", headers=admin)
    assert r.status_code == 200 and r.json()["estado"] == "enviada"


def test_invitar_requiere_super_admin_y_respeta_emails(client, db, armar_empresa, admin, capturar):
    ctx = armar_empresa()
    otro = armar_empresa()
    cab_dueno = token_de(ctx.dueno)
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/usuarios", headers=cab_dueno,
        json={"nombre": "X", "email": "x@example.com", "rol": "recepcion"},
    )
    assert r.status_code in (401, 403)
    # El email de alguien de otra empresa no se puede reusar.
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/usuarios", headers=admin,
        json={"nombre": "Xavier", "email": otro.dueno.email, "rol": "recepcion"},
    )
    assert r.status_code == 409


def test_el_token_de_invitacion_no_sirve_para_restablecer(client, db, armar_empresa, admin, capturar):
    ctx = armar_empresa()
    _invitar(client, admin, ctx)
    _, token = capturar[-1]
    r = client.post("/auth/restablecer-password", json={"token": token, "clave_nueva": "otraClave999"})
    assert r.status_code == 400


def test_alta_con_clave_sigue_andando_por_compatibilidad(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    email = f"viejo-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/usuarios", headers=admin,
        json={"nombre": "Alta Vieja", "email": email, "clave": "clave12345", "rol": "recepcion"},
    )
    assert r.status_code == 201 and r.json()["activacion_pendiente"] is False


def test_limites_de_pedidos_configurados():
    import app.main  # noqa: F401
    from app.core.rate_limit import limiter

    marcados = set(limiter._Limiter__marked_for_limiting.keys())
    esperados = {
        "app.routers.auth.ver_invitacion",
        "app.routers.auth.activar_cuenta",
        "app.routers.auth.logout",
        "app.routers.admin.crear_usuario",
        "app.routers.admin_finanzas.reenviar_invitacion",
        "app.routers.admin_finanzas.revocar_invitacion",
        "app.routers.admin_finanzas.revocar_sesion",
        "app.routers.admin_finanzas.cerrar_sesiones",
    }
    assert not esperados - marcados, sorted(esperados - marcados)
