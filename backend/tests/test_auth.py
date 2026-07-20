"""Auth: login, tipos de token, y el guard de empresa pausada.

Acá viven las garantías que ya verificamos a mano en la auditoría pre-deploy;
estos tests las dejan vigiladas para siempre.
"""

from tests.conftest import refresh_de, token_de


def test_login_ok_y_me(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave}
    )
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == ctx.dueno.email


def test_login_clave_incorrecta_no_revela_nada(client, armar_empresa):
    """Clave mala y email inexistente responden EXACTAMENTE igual (401 mismo
    detalle): que un atacante no pueda enumerar qué emails están registrados."""
    ctx = armar_empresa()
    mala = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": "incorrecta9"}
    )
    inexistente = client.post(
        "/auth/login", json={"email": "nadie@example.com", "clave": "incorrecta9"}
    )
    assert mala.status_code == inexistente.status_code == 401
    assert mala.json()["detail"] == inexistente.json()["detail"]


def test_empresa_pausada_no_puede_loguear(client, db, armar_empresa):
    ctx = armar_empresa()
    ctx.empresa.activa = False
    db.flush()
    r = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave}
    )
    assert r.status_code == 403
    assert "pausad" in r.json()["detail"].lower()


def test_pausar_empresa_corta_tokens_ya_emitidos(client, db, armar_empresa):
    """El guard de empresa activa corre en CADA request: pausar desde el
    super-admin mata las sesiones vivas, no solo los logins nuevos."""
    ctx = armar_empresa()
    headers = token_de(ctx.dueno)

    assert client.get("/clientes", headers=headers).status_code == 200

    ctx.empresa.activa = False
    db.flush()

    assert client.get("/clientes", headers=headers).status_code == 403


def test_access_token_no_sirve_como_refresh(client, armar_empresa):
    """Claim de tipo: cada token sirve SOLO para lo suyo. Un access robado no
    puede usarse para mintear sesiones nuevas en /auth/refresh."""
    ctx = armar_empresa()
    login = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave}
    ).json()

    r = client.post("/auth/refresh", json={"refresh_token": login["access_token"]})
    assert r.status_code == 401


def test_refresh_de_usuario_desactivado_muere(client, db, armar_empresa):
    ctx = armar_empresa()
    refresh = refresh_de(ctx.dueno)

    ctx.dueno.activo = False
    db.flush()

    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


def test_gates_de_rol_en_endpoints_de_dueno(client, armar_empresa):
    """gate_dueno: el profesional no crea servicios ni toca finanzas; el dueño sí."""
    ctx = armar_empresa()
    payload = {"nombre": "Tintura", "duracion_min": 45, "precio": 20000}

    como_profesional = client.post(
        "/servicios", json=payload, headers=token_de(ctx.profesional)
    )
    assert como_profesional.status_code == 403

    como_dueno = client.post("/servicios", json=payload, headers=token_de(ctx.dueno))
    assert como_dueno.status_code == 201
    assert como_dueno.json()["nombre"] == "Tintura"
