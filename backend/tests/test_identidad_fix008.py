"""Regresión del fix-008: identidad y recuperación de contraseña.

Cubre el hallazgo 3.4 de la auditoría (el email no era único entre empresas,
así que la misma persona dada de alta en dos negocios quedaba sin poder
entrar a uno de los dos, en silencio) y el módulo nuevo de equipo.
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import LogAuditoria, SuperAdmin, Usuario
from app.models.enums import RolUsuario
from app.services.equipo import _email_sirve_para_recuperar

from .conftest import token_de


def _cabecera_superadmin(db) -> dict:
    """Un super-admin real en la base + su token."""
    sa = SuperAdmin(
        nombre="Admin Test",
        email=f"sa-{dt.datetime.now().timestamp()}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


# ══════════════════════════════════════════════════════════════════════
# El email es único en todo el sistema
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_crear_un_usuario_con_el_email_de_otra_empresa(
    client, db, armar_empresa
):
    """El caso que dejaba a una persona sin poder entrar, sin ningún error."""
    a = armar_empresa("Barbería A")
    b = armar_empresa("Peluquería B")
    cab = _cabecera_superadmin(db)
    db.commit()

    r = client.post(
        f"/admin/empresas/{b.empresa.id}/usuarios",
        headers=cab,
        json={
            "nombre": "Juan",
            "email": a.profesional.email,  # ya existe en la empresa A
            "clave": "clave1234",
            "rol": "profesional",
        },
    )
    assert r.status_code == 409, (
        "Se creó un usuario con un email que ya existía en otra empresa. "
        "Esa persona queda sin poder entrar a una de sus dos cuentas."
    )
    assert "otro negocio" in r.json()["detail"].lower()


def test_el_mensaje_distingue_si_el_email_repetido_es_del_propio_negocio(
    client, db, armar_empresa
):
    a = armar_empresa("Barbería A")
    cab = _cabecera_superadmin(db)
    db.commit()

    r = client.post(
        f"/admin/empresas/{a.empresa.id}/usuarios",
        headers=cab,
        json={
            "nombre": "Otro",
            "email": a.dueno.email,
            "clave": "clave1234",
            "rol": "recepcion",
        },
    )
    assert r.status_code == 409
    assert "este negocio" in r.json()["detail"].lower()


def test_el_email_repetido_no_deja_una_empresa_huerfana(client, db, armar_empresa):
    """Si el email del dueño ya existe, la empresa NO se crea.

    Antes se validaba después de crear la empresa: quedaba un negocio sin
    dueño, imposible de usar y que hay que limpiar a mano.
    """
    a = armar_empresa("Barbería A")
    cab = _cabecera_superadmin(db)
    db.commit()

    from app.models import Empresa, Rubro

    rubro = db.scalar(select(Rubro).limit(1))
    antes = db.scalar(select(Empresa).where(Empresa.slug == "negocio-huerfano"))
    assert antes is None

    r = client.post(
        "/admin/empresas",
        headers=cab,
        json={
            "nombre": "Negocio Huerfano",
            "slug": "negocio-huerfano",
            "rubro_id": rubro.id,
            "dueno": {
                "nombre": "Repetido",
                "email": a.dueno.email,
                "clave": "clave1234",
                "rol": "dueno",
            },
        },
    )
    assert r.status_code == 409
    despues = db.scalar(select(Empresa).where(Empresa.slug == "negocio-huerfano"))
    assert despues is None, "Quedó una empresa creada sin dueño."


def test_un_email_invalido_no_se_acepta(client, db, armar_empresa):
    """Antes el campo era `str` pelado: se podía cargar "barbero1" y esa
    persona no podía recuperar su contraseña nunca."""
    a = armar_empresa()
    cab = _cabecera_superadmin(db)
    db.commit()

    r = client.post(
        f"/admin/empresas/{a.empresa.id}/usuarios",
        headers=cab,
        json={"nombre": "Barbero", "email": "barbero1", "clave": "clave1234", "rol": "profesional"},
    )
    assert r.status_code == 422


def test_el_email_se_guarda_en_minusculas(client, db, armar_empresa):
    a = armar_empresa()
    cab = _cabecera_superadmin(db)
    db.commit()

    # Sufijo al azar: el índice de emails es global, así que un literal fijo
    # choca con 409 en cualquier base que ya tenga esa dirección.
    s = uuid.uuid4().hex[:8]
    r = client.post(
        f"/admin/empresas/{a.empresa.id}/usuarios",
        headers=cab,
        json={
            "nombre": "Mayus",
            "email": f"  Juan.Perez.{s}@GMAIL.com  ",
            "clave": "clave1234",
            "rol": "recepcion",
        },
    )
    assert r.status_code == 201
    assert r.json()["email"] == f"juan.perez.{s}@gmail.com"


# ══════════════════════════════════════════════════════════════════════
# Login y recuperación sin distinguir mayúsculas
# ══════════════════════════════════════════════════════════════════════

def test_se_puede_entrar_escribiendo_el_email_con_mayusculas(client, db, armar_empresa):
    """Para una persona Juan@Gmail.com y juan@gmail.com son lo mismo."""
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        "/auth/login",
        json={"email": ctx.dueno.email.upper(), "clave": ctx.clave},
    )
    assert r.status_code == 200, "El login distinguía mayúsculas."
    assert r.json()["access_token"]


def test_olvide_password_encuentra_la_cuenta_con_mayusculas(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()

    r = client.post("/auth/olvide-password", json={"email": ctx.dueno.email.upper()})
    assert r.status_code == 200

    db.refresh(ctx.dueno)
    assert ctx.dueno.reset_token_hash is not None, (
        "No se generó el token: la búsqueda distinguía mayúsculas."
    )


# ══════════════════════════════════════════════════════════════════════
# El equipo del negocio
# ══════════════════════════════════════════════════════════════════════

def test_el_dueno_ve_su_equipo(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()

    r = client.get("/equipo/usuarios", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    nombres = {u["nombre"] for u in r.json()}
    assert ctx.dueno.nombre in nombres
    assert ctx.profesional.nombre in nombres


def test_el_equipo_solo_muestra_gente_del_propio_negocio(client, db, armar_empresa):
    a = armar_empresa("Barbería A")
    b = armar_empresa("Peluquería B")
    db.commit()

    r = client.get("/equipo/usuarios", headers=token_de(a.dueno))
    emails = {u["email"] for u in r.json()}
    assert b.dueno.email not in emails, "Se filtró un usuario de otra empresa."


def test_recepcion_no_ve_el_equipo(client, db, armar_empresa):
    ctx = armar_empresa()
    recepcion = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Recepción",
        email=f"recep-{ctx.empresa.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recepcion)
    db.commit()

    r = client.get("/equipo/usuarios", headers=token_de(recepcion))
    assert r.status_code == 403


def test_el_equipo_marca_quien_no_puede_recuperar_su_clave(client, db, armar_empresa):
    """El dato que necesita el dueño: quién depende de él para entrar."""
    ctx = armar_empresa()
    ctx.profesional.email = "barbero1"  # el clásico email que no es un email
    db.commit()

    r = client.get("/equipo/usuarios", headers=token_de(ctx.dueno))
    porNombre = {u["nombre"]: u for u in r.json()}
    assert porNombre[ctx.dueno.nombre]["email_recuperable"] is True
    assert porNombre[ctx.profesional.nombre]["email_recuperable"] is False


@pytest.mark.parametrize(
    "email,esperado",
    [
        ("juan@gmail.com", True),
        ("j.perez+turnos@sub.dominio.com.ar", True),
        ("barbero1", False),
        ("juan@nada", False),
        ("", False),
        (None, False),
        ("@gmail.com", False),
        ("juan@", False),
        ("juan@.com", False),
    ],
)
def test_deteccion_de_emails_que_no_sirven(email, esperado):
    assert _email_sirve_para_recuperar(email) is esperado


# ══════════════════════════════════════════════════════════════════════
# El link de restablecimiento que genera el dueño
# ══════════════════════════════════════════════════════════════════════

def test_el_link_del_dueno_sirve_para_cambiar_la_clave_de_verdad(
    client, db, armar_empresa
):
    """Prueba de punta a punta: se genera el link y se usa el token."""
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.profesional.id}/link-restablecer",
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 200
    datos = r.json()
    assert datos["usuario"] == ctx.profesional.nombre
    assert datos["vence_en_minutos"] == 60
    assert "/restablecer?token=" in datos["url"]

    token = datos["url"].split("token=")[1]

    # El token del link tiene que funcionar en el flujo normal.
    r = client.post(
        "/auth/restablecer-password",
        json={"token": token, "clave_nueva": "claveNueva123"},
    )
    assert r.status_code == 200, r.text

    # Y la clave nueva tiene que servir para entrar.
    r = client.post(
        "/auth/login",
        json={"email": ctx.profesional.email, "clave": "claveNueva123"},
    )
    assert r.status_code == 200


def test_el_link_es_de_un_solo_uso(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.profesional.id}/link-restablecer",
        headers=token_de(ctx.dueno),
    )
    token = r.json()["url"].split("token=")[1]

    primera = client.post(
        "/auth/restablecer-password", json={"token": token, "clave_nueva": "claveNueva123"}
    )
    assert primera.status_code == 200

    segunda = client.post(
        "/auth/restablecer-password", json={"token": token, "clave_nueva": "otraClave456"}
    )
    assert segunda.status_code == 400, "El token se pudo usar dos veces."


def test_el_token_no_se_guarda_en_claro(client, db, armar_empresa):
    """En la base queda solo el hash, igual que en olvidé-mi-contraseña."""
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.profesional.id}/link-restablecer",
        headers=token_de(ctx.dueno),
    )
    token = r.json()["url"].split("token=")[1]

    db.refresh(ctx.profesional)
    assert ctx.profesional.reset_token_hash != token
    assert len(ctx.profesional.reset_token_hash) == 64  # sha256 en hexadecimal


def test_un_dueno_no_puede_restablecerle_la_clave_a_otro_dueno(
    client, db, armar_empresa
):
    """Sería una escalada de privilegios dentro del mismo negocio."""
    ctx = armar_empresa()
    otro = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Socio",
        email=f"socio-{ctx.empresa.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.DUENO,
    )
    db.add(otro)
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{otro.id}/link-restablecer", headers=token_de(ctx.dueno)
    )
    assert r.status_code == 403


def test_el_dueno_no_se_puede_generar_un_link_a_si_mismo(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.dueno.id}/link-restablecer", headers=token_de(ctx.dueno)
    )
    assert r.status_code == 400
    assert "Mi cuenta" in r.json()["detail"]


def test_no_se_puede_generar_un_link_para_alguien_de_otra_empresa(
    client, db, armar_empresa
):
    a = armar_empresa("Barbería A")
    b = armar_empresa("Peluquería B")
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{b.profesional.id}/link-restablecer",
        headers=token_de(a.dueno),
    )
    assert r.status_code == 404


def test_no_se_puede_generar_un_link_para_un_usuario_desactivado(
    client, db, armar_empresa
):
    ctx = armar_empresa()
    ctx.profesional.activo = False
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.profesional.id}/link-restablecer",
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 400


def test_recepcion_no_puede_generar_links(client, db, armar_empresa):
    ctx = armar_empresa()
    recepcion = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Recepción",
        email=f"recep2-{ctx.empresa.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recepcion)
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.profesional.id}/link-restablecer",
        headers=token_de(recepcion),
    )
    assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════
# La auditoría, que hasta hoy no se escribía nunca
# ══════════════════════════════════════════════════════════════════════

def test_el_restablecimiento_queda_registrado_en_la_auditoria(
    client, db, armar_empresa
):
    """log_auditoria existía desde la primera migración y no se escribía una
    sola fila. Esta es la primera acción que la usa, y es la más delicada que
    un dueño puede hacer sobre la cuenta de otra persona."""
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        f"/equipo/usuarios/{ctx.profesional.id}/link-restablecer",
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 200

    registro = db.scalar(
        select(LogAuditoria).where(
            LogAuditoria.empresa_id == ctx.empresa.id,
            LogAuditoria.accion == "reset_password",
        )
    )
    assert registro is not None, "No quedó registro de quién generó el link."
    assert registro.usuario_id == ctx.dueno.id
    assert registro.registro_id == ctx.profesional.id
    assert registro.detalle["objetivo_nombre"] == ctx.profesional.nombre


def test_el_link_muestra_el_recurso_que_opera_cada_profesional(
    client, db, armar_empresa
):
    """Dato útil en la lista: 'Profe Test — atiende en Lucas Estrella'."""
    ctx = armar_empresa()
    db.commit()

    r = client.get("/equipo/usuarios", headers=token_de(ctx.dueno))
    porNombre = {u["nombre"]: u for u in r.json()}
    assert porNombre[ctx.profesional.nombre]["recurso"] == ctx.lucas.nombre
    assert porNombre[ctx.dueno.nombre]["recurso"] is None
