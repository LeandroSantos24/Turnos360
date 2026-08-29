"""Fase 2: el registro público, con su candado anti-spam.

Hasta acá el alta la hacía Leandro a mano y la landing lo vendía como propuesta
de valor. Abrirlo escala, pero convierte a Turnos360 en una fábrica de páginas
web gratis con nuestro dominio si no se hace con cuidado.

EL CANDADO: la vidriera pública NO se muestra hasta que el dueño verifique su
email. El panel sí se puede usar desde el segundo cero — quien se registró de
verdad no queda esperando un email para probar el producto, que es el momento
exacto en el que la gente abandona.
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from app.models import Empresa, Rubro, Usuario
from app.services import registro as svc


@pytest.fixture()
def rubro(db) -> Rubro:
    r = Rubro(codigo=f"r-{uuid.uuid4().hex[:8]}", nombre="Barbería Test", preset={})
    db.add(r)
    db.flush()
    return r


def _alta(rubro, **extra):
    base = {
        "nombre_negocio": "Barbería El Faro",
        "slug": f"faro-{uuid.uuid4().hex[:8]}",
        "rubro_codigo": rubro.codigo,
        "nombre": "Leandro",
        "email": f"l-{uuid.uuid4().hex[:8]}@example.com",
        "clave": "clave1234",
    }
    base.update(extra)
    return base


# ══════════════════════════════════════════════════════════════════════
#  El alta
# ══════════════════════════════════════════════════════════════════════

def test_un_negocio_se_da_de_alta_solo(client, db, rubro):
    datos = _alta(rubro)
    r = client.post("/publico/registro", json=datos)
    assert r.status_code == 201, r.text

    cuerpo = r.json()
    assert cuerpo["empresa_slug"] == datos["slug"]
    assert cuerpo["email_verificado"] is False
    assert cuerpo["access_token"], "Tiene que entrar sin volver a loguearse."

    empresa = db.scalar(select(Empresa).where(Empresa.slug == datos["slug"]))
    assert empresa is not None
    assert empresa.de_registro_publico is True


def test_arranca_con_los_dias_de_prueba(client, db, rubro):
    from app.core.config import settings

    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)
    empresa = db.scalar(select(Empresa).where(Empresa.slug == datos["slug"]))
    esperado = dt.date.today() + dt.timedelta(days=settings.dias_prueba_registro)
    assert empresa.prueba_hasta == esperado


def test_el_token_deja_entrar_al_panel(client, db, rubro):
    datos = _alta(rubro)
    token = client.post("/publico/registro", json=datos).json()["access_token"]
    r = client.get("/empresa/actual", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Barbería El Faro"


# ══════════════════════════════════════════════════════════════════════
#  El candado anti-spam
# ══════════════════════════════════════════════════════════════════════

def test_la_vidriera_no_se_muestra_sin_verificar(client, rubro):
    """Este es el freno: sin él, publicar spam con nuestro dominio sale gratis."""
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)

    r = client.get(f"/publico/{datos['slug']}")
    assert r.status_code == 404, (
        "Un negocio sin verificar NO puede tener página pública."
    )


def test_se_responde_404_y_no_403(client, rubro):
    """Decir "existe pero sin verificar" le confirmaría a alguien que ese slug
    está tomado. Desde afuera, sin verificar y sin existir son lo mismo."""
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)
    r = client.get(f"/publico/{datos['slug']}")
    assert r.status_code == 404
    assert "no encontrado" in r.json()["detail"].lower()


def test_verificar_enciende_la_vidriera(client, db, rubro):
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)

    # El token viaja por email; en el test se genera uno nuevo por el servicio.
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos["email"]))
    db.expire_all()
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos["email"]))
    token = svc.reenviar(db, usuario)

    r = client.post(f"/publico/verificar-email?token={token}")
    assert r.status_code == 200, r.text
    db.expire_all()

    r = client.get(f"/publico/{datos['slug']}")
    assert r.status_code == 200, "Verificado, la página tiene que estar online."


def test_el_token_sirve_una_sola_vez(client, db, rubro):
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos["email"]))
    token = svc.reenviar(db, usuario)

    assert client.post(f"/publico/verificar-email?token={token}").status_code == 200
    assert client.post(f"/publico/verificar-email?token={token}").status_code == 400


def test_un_token_vencido_no_sirve(client, db, rubro):
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos["email"]))
    token = svc.reenviar(db, usuario)

    usuario.verif_token_expira = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    db.commit()
    assert client.post(f"/publico/verificar-email?token={token}").status_code == 400


def test_un_token_inventado_no_sirve(client, rubro):
    assert client.post("/publico/verificar-email?token=cualquiera").status_code == 400


def test_los_negocios_de_siempre_no_se_ven_afectados(client, db, armar_empresa):
    """El candado es SOLO para los del registro público.

    Sin esto, todos los negocios que ya están andando se quedarían sin página
    de un día para el otro.
    """
    ctx = armar_empresa()
    assert ctx.empresa.de_registro_publico is False
    r = client.get(f"/publico/{ctx.empresa.slug}")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  Validaciones del alta
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_registrar_un_slug_ocupado(client, db, rubro):
    datos = _alta(rubro)
    assert client.post("/publico/registro", json=datos).status_code == 201
    r = client.post("/publico/registro", json=_alta(rubro, slug=datos["slug"]))
    assert r.status_code == 409
    assert "ocupada" in r.json()["detail"].lower()


def test_no_se_puede_registrar_un_slug_del_sistema(client, rubro):
    """La lista negra de la Fase 0 se reutiliza acá, no se reescribe."""
    for slug in ["login", "admin", "api"]:
        r = client.post("/publico/registro", json=_alta(rubro, slug=slug))
        assert r.status_code == 422, f"'{slug}' no se puede registrar"


def test_un_email_ya_registrado_no_crea_una_empresa_huerfana(client, db, rubro):
    """Si se validara después de crear la empresa, quedaría un registro
    huérfano para limpiar a mano."""
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)
    antes = db.query(Empresa).count()

    r = client.post("/publico/registro", json=_alta(rubro, email=datos["email"]))
    assert r.status_code == 409
    assert db.query(Empresa).count() == antes, "No tiene que quedar una empresa a medias."


def test_una_clave_corta_se_rechaza(client, rubro):
    r = client.post("/publico/registro", json=_alta(rubro, clave="corta"))
    assert r.status_code == 422


def test_un_email_sin_arroba_se_rechaza(client, rubro):
    r = client.post("/publico/registro", json=_alta(rubro, email="pepe"))
    assert r.status_code == 422


def test_un_rubro_inventado_se_rechaza(client, rubro):
    r = client.post("/publico/registro", json=_alta(rubro, rubro_codigo="no-existe"))
    assert r.status_code == 404


def test_el_slug_se_normaliza(client, db, rubro):
    r = client.post("/publico/registro", json=_alta(rubro, slug="Barbería El Faro 2"))
    assert r.status_code == 201
    assert r.json()["empresa_slug"] == "barberia-el-faro-2"


def test_los_rubros_se_pueden_listar_sin_login(client, rubro):
    """El formulario de registro los necesita antes de que exista una cuenta."""
    r = client.get("/publico/rubros")
    assert r.status_code == 200
    assert any(x["codigo"] == rubro.codigo for x in r.json())


def test_el_registro_se_puede_cerrar_en_caliente(client, rubro, monkeypatch):
    """Por si aparece abuso: cerrar la puerta sin necesidad de un deploy."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "registro_publico_abierto", False)
    r = client.post("/publico/registro", json=_alta(rubro))
    assert r.status_code == 503


def test_el_dueno_nace_con_rol_dueno_y_sin_verificar(client, db, rubro):
    datos = _alta(rubro)
    client.post("/publico/registro", json=datos)
    u = db.scalar(select(Usuario).where(Usuario.email == datos["email"]))
    assert u.rol.value == "dueno"
    assert u.email_verificado is False
    assert u.verif_token_hash is not None, "Se guarda el hash, nunca el token."
