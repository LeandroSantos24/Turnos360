"""Mi cuenta: perfil propio, cambio de clave sin quedar afuera y cerrar las
demás sesiones."""

from app.core.crypto import verificar_clave
from app.models import Usuario
from app.models.enums import RolUsuario
from tests.conftest import refresh_de, token_de


# ── Perfil ────────────────────────────────────────────────────────────

def test_me_trae_el_nombre_del_negocio_y_del_local(client, armar_empresa):
    ctx = armar_empresa("Barbería Cuenta")
    r = client.get("/auth/me", headers=token_de(ctx.profesional))
    assert r.status_code == 200
    d = r.json()
    assert d["empresa_nombre"] == "Barbería Cuenta"
    assert d["sucursal_nombre"] == ctx.sede.nombre
    assert d["rol"] == "profesional"
    assert "hash_clave" not in d and "token_version" not in d


def test_cada_uno_cambia_su_nombre_y_nada_mas(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.patch(
        "/auth/me",
        json={
            "nombre": "  Lucas   Estrella ",
            "rol": "dueno",
            "email": "otro@example.com",
            "empresa_id": 999999,
        },
        headers=token_de(ctx.profesional),
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Lucas Estrella"
    db.expire_all()
    u = db.get(Usuario, ctx.profesional.id)
    assert u.nombre == "Lucas Estrella"
    assert u.rol == RolUsuario.PROFESIONAL
    assert u.email != "otro@example.com"
    assert u.empresa_id == ctx.empresa.id


def test_el_nombre_vacio_no_pasa(client, armar_empresa):
    ctx = armar_empresa()
    h = token_de(ctx.dueno)
    assert client.patch("/auth/me", json={"nombre": " "}, headers=h).status_code == 422
    assert client.patch("/auth/me", json={"nombre": "a     "}, headers=h).status_code == 400


def test_perfil_sin_sesion_da_401(client):
    assert client.patch("/auth/me", json={"nombre": "Pepe"}).status_code == 401


# ── Contraseña ────────────────────────────────────────────────────────

def test_cambiar_la_clave_devuelve_una_sesion_nueva_que_sirve(client, db, armar_empresa):
    ctx = armar_empresa()
    viejo = token_de(ctx.dueno)
    r = client.post(
        "/auth/cambiar-password",
        json={"clave_actual": ctx.clave, "clave_nueva": "OtraClave99"},
        headers=viejo,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["detalle"]
    nuevo = {"Authorization": f"Bearer {d['access_token']}"}
    # El que cambió la clave sigue adentro; el token de antes no.
    assert client.get("/auth/me", headers=nuevo).status_code == 200
    assert client.get("/auth/me", headers=viejo).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": d["refresh_token"]}).status_code == 200
    db.expire_all()
    assert verificar_clave("OtraClave99", db.get(Usuario, ctx.dueno.id).hash_clave)


def test_la_clave_nueva_tiene_que_ser_distinta(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        "/auth/cambiar-password",
        json={"clave_actual": ctx.clave, "clave_nueva": ctx.clave},
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 400


# ── Cerrar las demás sesiones ─────────────────────────────────────────

def test_cerrar_otras_sesiones_echa_a_los_demas_y_no_a_mi(client, armar_empresa):
    ctx = armar_empresa()
    otro_dispositivo = token_de(ctx.dueno)
    otro_refresh = refresh_de(ctx.dueno)
    este = token_de(ctx.dueno)

    r = client.post(
        "/auth/cerrar-otras-sesiones", json={"clave_actual": ctx.clave}, headers=este
    )
    assert r.status_code == 200
    nuevo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=nuevo).status_code == 200
    assert client.get("/auth/me", headers=otro_dispositivo).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": otro_refresh}).status_code == 401


def test_cerrar_sesiones_pide_la_clave(client, armar_empresa):
    """Con solo un token robado no se puede echar al dueño de verdad."""
    ctx = armar_empresa()
    h = token_de(ctx.dueno)
    r = client.post("/auth/cerrar-otras-sesiones", json={"clave_actual": "mala"}, headers=h)
    assert r.status_code == 400
    assert client.get("/auth/me", headers=h).status_code == 200
