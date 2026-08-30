"""Fase 0: tres agujeros que hay que cerrar ANTES del registro público.

Los tres son inofensivos hoy y dejan de serlo apenas se abra el alta
self-service o empiece multisucursal. Van juntos porque los tres están en el
camino crítico de lo que sigue.
"""

import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Recurso, Rubro, Sucursal, SuperAdmin, Usuario
from app.schemas.admin import SLUGS_RESERVADOS

from .conftest import token_de


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin Test",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


@pytest.fixture()
def rubro(db) -> Rubro:
    r = Rubro(codigo=f"r-{uuid.uuid4().hex[:8]}", nombre="Barbería Test", preset={})
    db.add(r)
    db.flush()
    return r


def _empresa(rubro, *, slug=None, email=None):
    # El email por defecto es único a propósito. El índice de emails es
    # GLOBAL (una persona = una dirección en todo el sistema), así que un
    # literal fijo hace que el test dependa de que esa dirección no exista
    # en la base contra la que corre, y revienta con 409 en cualquier
    # entorno con datos reales.
    email = email or f"dueno-{uuid.uuid4().hex[:8]}@example.com"
    return {
        "nombre": "Negocio de prueba",
        "slug": slug or f"n-{uuid.uuid4().hex[:8]}",
        "rubro_id": rubro.id,
        "dueno": {"nombre": "Dueño", "email": email, "clave": "clave1234"},
    }


# ══════════════════════════════════════════════════════════════════════
#  1. El email del dueño
# ══════════════════════════════════════════════════════════════════════

def test_un_dueno_sin_email_valido_se_rechaza(client, admin, rubro):
    """Antes entraba: y esa persona no podía recuperar su clave NUNCA."""
    r = client.post(
        "/admin/empresas", headers=admin, json=_empresa(rubro, email="pepe")
    )
    assert r.status_code == 422, (
        "Un email sin @ tiene que rebotar: el link de reseteo no tendría a "
        "dónde llegar."
    )


def test_el_email_del_dueno_se_normaliza(client, db, admin, rubro):
    """Sin el .lower(), entra al índice único de emails sin normalizar."""
    s = uuid.uuid4().hex[:8]
    r = client.post(
        "/admin/empresas",
        headers=admin,
        json=_empresa(rubro, email=f"  Pepe.{s}@Gmail.COM "),
    )
    assert r.status_code == 201, r.text
    creado = db.query(Usuario).filter_by(email=f"pepe.{s}@gmail.com").first()
    assert creado is not None, "El email tiene que quedar en minúsculas y sin espacios."


# ══════════════════════════════════════════════════════════════════════
#  2. Slugs reservados
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("slug", ["login", "admin", "api", "registro", "turnos360"])
def test_los_slugs_del_sistema_se_rechazan(client, admin, rubro, slug):
    """Next resuelve la ruta estática antes que /{slug}: la vidriera quedaría
    inalcanzable para siempre, y no hay forma de editar el slug después."""
    r = client.post("/admin/empresas", headers=admin, json=_empresa(rubro, slug=slug))
    assert r.status_code == 422, f"El slug '{slug}' no tendría que poder crearse."


def test_el_slug_reservado_se_detecta_despues_de_normalizar(client, admin, rubro):
    """La lista se chequea DESPUÉS de normalizar, no sobre el texto crudo.

    Ojo con el alcance: "Log-In" normaliza a "log-in" (con guión), que es un
    slug distinto y perfectamente válido. Lo que se bloquea es lo que termina
    siendo exactamente una ruta del sistema.
    """
    for crudo in ["LOGIN", "  login  ", "login!", "Lógin"]:
        r = client.post(
            "/admin/empresas", headers=admin, json=_empresa(rubro, slug=crudo)
        )
        assert r.status_code == 422, f"'{crudo}' normaliza a un slug reservado."


def test_un_slug_normal_sigue_funcionando(client, admin, rubro):
    # El sufijo al azar es a propósito: sin él el test depende de que la base
    # no tenga ya una "Barbería El Faro" y falla con 409 en cualquier entorno
    # con datos reales. Lo que se prueba es el normalizador (tilde, mayúscula,
    # espacio), y eso se prueba igual con el sufijo pegado.
    sufijo = uuid.uuid4().hex[:6]
    r = client.post(
        "/admin/empresas",
        headers=admin,
        json=_empresa(rubro, slug=f"Barbería El Faro {sufijo}"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == f"barberia-el-faro-{sufijo}"


def test_la_lista_cubre_las_rutas_que_existen_hoy():
    """Si mañana alguien agrega una pantalla, que este test recuerde la lista."""
    for ruta in ["login", "admin", "agenda", "clientes", "caja", "suscripcion"]:
        assert ruta in SLUGS_RESERVADOS


# ══════════════════════════════════════════════════════════════════════
#  3. sucursal_id por tenant
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_crear_un_recurso_en_la_sucursal_de_otra_empresa(
    client, db, armar_empresa
):
    """Regla 1: toda consulta filtra por empresa_id. Este campo se escapaba."""
    a = armar_empresa()
    b = armar_empresa()
    ajena = Sucursal(empresa_id=b.empresa.id, nombre="Local de B")
    db.add(ajena)
    db.flush()

    r = client.post(
        "/recursos",
        headers=token_de(a.dueno),
        json={"nombre": "Colado", "tipo": "persona", "sucursal_id": ajena.id},
    )
    assert r.status_code == 404, (
        "Se pudo asignar un recurso a la sucursal de otra empresa. Hoy es "
        "inofensivo porque nadie lee la columna; deja de serlo con multisucursal."
    )
    assert db.query(Recurso).filter_by(nombre="Colado").first() is None


def test_tampoco_se_puede_mover_un_recurso_a_una_sucursal_ajena(
    client, db, armar_empresa
):
    a = armar_empresa()
    b = armar_empresa()
    ajena = Sucursal(empresa_id=b.empresa.id, nombre="Local de B")
    db.add(ajena)
    db.flush()

    r = client.patch(
        f"/recursos/{a.lucas.id}",
        headers=token_de(a.dueno),
        json={"sucursal_id": ajena.id},
    )
    assert r.status_code == 404
    db.expire_all()
    assert db.get(Recurso, a.lucas.id).sucursal_id != ajena.id


def test_la_sucursal_propia_si_se_puede_asignar(client, db, armar_empresa):
    a = armar_empresa()
    propia = Sucursal(empresa_id=a.empresa.id, nombre="Centro")
    db.add(propia)
    db.flush()

    r = client.post(
        "/recursos",
        headers=token_de(a.dueno),
        json={"nombre": "Ana", "tipo": "persona", "sucursal_id": propia.id},
    )
    assert r.status_code == 201, r.text
    assert r.json()["sucursal_id"] == propia.id


def test_sin_sucursal_el_alta_lo_manda_al_local_principal(client, armar_empresa):
    """El alta sin sucursal tiene que seguir funcionando igual de simple.

    Cambió lo que pasa por debajo: antes quedaba en NULL, ahora cae en el local
    principal (paso 1 de multisucursal). Para quien usa la aplicación no cambia
    nada —no hay ningún campo nuevo que completar—, que es exactamente el
    criterio de aceptación de esta fase.
    """
    a = armar_empresa()
    r = client.post(
        "/recursos", headers=token_de(a.dueno), json={"nombre": "Sin local", "tipo": "persona"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["sucursal_id"] == a.sede.id
