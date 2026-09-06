"""El logo de Turnos360, cambiable sin desplegar.

QUÉ CUIDA ESTE ARCHIVO
──────────────────────
El logo lo carga el super-admin por URL y termina adentro del `src` de un
`<img>` de la landing: es lo primero que ve cualquiera que entra, servido
desde el origen de Turnos360. Eso lo convierte en un lugar donde una URL que
no es una URL de imagen —un `javascript:`, un `data:` con HTML adentro— sería
un script corriendo en nuestro dominio, puesto por la sesión más poderosa del
sistema.

Y lo otro que cuida es la vuelta atrás: vaciar el campo tiene que volver al
archivo del repo. Si deshacerlo fuera más difícil que ponerlo, el gorrito de
Navidad se queda hasta marzo.
"""

import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import AjusteGlobal, SuperAdmin
from app.services import marca


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin Marca",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


# ══════════════════════════════════════════════════════════════════════
#  1. Guardar, leer y deshacer
# ══════════════════════════════════════════════════════════════════════

def test_sin_configurar_no_hay_override(db):
    """El caso normal. None significa «usá el archivo del repo», y el
    frontend ya lo está mostrando: un None no cambia nada en pantalla."""
    db.query(AjusteGlobal).filter(AjusteGlobal.clave == marca.CLAVE_LOGO).delete()
    db.flush()
    assert marca.logo_url(db) is None


def test_se_guarda_y_se_lee(db):
    marca.guardar_logo(db, "https://cdn.test/logo-navidad.png", quien="admin@test")
    assert marca.logo_url(db) == "https://cdn.test/logo-navidad.png"


def test_vaciar_vuelve_al_logo_del_repo(db):
    """LA vuelta atrás. Tiene que ser tan fácil como ponerlo."""
    marca.guardar_logo(db, "https://cdn.test/logo-navidad.png", quien="admin@test")
    assert marca.logo_url(db) is not None

    marca.guardar_logo(db, "", quien="admin@test")
    assert marca.logo_url(db) is None, (
        "Vaciar el campo tiene que borrar el override, no guardar una cadena "
        "vacía que después se pinte como un `src` roto."
    )


def test_guardar_de_nuevo_pisa_y_no_acumula(db):
    """Una fila por ajuste. Si acumulara, `logo_url` devolvería cualquiera de
    las dos y el logo cambiaría solo entre recargas."""
    marca.guardar_logo(db, "https://cdn.test/uno.png", quien="a@test")
    marca.guardar_logo(db, "https://cdn.test/dos.png", quien="a@test")

    filas = (
        db.query(AjusteGlobal)
        .filter(AjusteGlobal.clave == marca.CLAVE_LOGO)
        .count()
    )
    assert filas == 1
    assert marca.logo_url(db) == "https://cdn.test/dos.png"


# ══════════════════════════════════════════════════════════════════════
#  2. Qué URLs se aceptan — la parte que importa
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "veneno",
    [
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        'https://cdn.test/x.png" onerror="alert(1)',
        "https://cdn.test/con espacio.png",
        "//cdn.test/protocolo-relativo.png",
    ],
)
def test_una_url_que_no_es_una_url_de_imagen_se_rechaza(client, admin, veneno):
    """Esto termina en el `src` de un <img> de la landing, servido desde
    nuestro origen. Un `javascript:` acá es un script en nuestro dominio."""
    r = client.put("/admin/marca", headers=admin, json={"logo_url": veneno})
    assert r.status_code == 422, f"Se aceptó {veneno!r}: {r.text[:200]}"


def test_una_url_https_normal_se_acepta(client, admin):
    r = client.put(
        "/admin/marca",
        headers=admin,
        json={"logo_url": "https://res.cloudinary.com/demo/image/upload/logo.png"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["logo_url"].endswith("logo.png")


# ══════════════════════════════════════════════════════════════════════
#  3. Quién puede tocarlo
# ══════════════════════════════════════════════════════════════════════

def test_sin_ser_super_admin_no_se_cambia(client):
    """Es el logo de la marca en la página de ventas: lo cambia el dueño de
    Turnos360 y nadie más."""
    r = client.put("/admin/marca", json={"logo_url": "https://cdn.test/x.png"})
    assert r.status_code in (401, 403)


def test_el_endpoint_publico_no_pide_login(client, db, admin):
    """La landing lo consulta sin sesión: es el logo, lo ve cualquiera."""
    client.put(
        "/admin/marca", headers=admin, json={"logo_url": "https://cdn.test/logo.png"}
    )
    r = client.get("/publico/marca")
    assert r.status_code == 200
    assert r.json()["logo_url"] == "https://cdn.test/logo.png"


def test_el_endpoint_publico_solo_devuelve_el_logo(client, admin):
    """Un endpoint sin login tiene que devolver EXACTAMENTE lo que hace falta.
    Si mañana se agregan ajustes globales —una clave, un token—, este test
    falla y obliga a pensar antes de exponerlos."""
    r = client.get("/publico/marca")
    assert set(r.json()) == {"logo_url"}
