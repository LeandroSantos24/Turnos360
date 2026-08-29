"""Fase 1: los planes dejan de ser decorativos.

Hasta acá el "plan" era un string libre y el tope de profesionales se pintaba
en ámbar en el panel del super-admin sin bloquear absolutamente nada: una
empresa del plan de tres podía cargar cuarenta. Y pagar la cuota no cambiaba el
plan, así que se podía pagar por Mercado Pago un año entero y seguir figurando
en "gratuito", con los límites de la prueba.

La grilla acordada:
    Básico  $14.990 →  3 profesionales · 1 local
    Pro     $24.990 → 10 profesionales · 1 local
    Multi   $35.990 → ilimitados       · 5 locales
"""

import uuid

import pytest

from app.core import planes
from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Empresa, Recurso, SuperAdmin
from app.models.enums import TipoRecurso

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


def _plan(db, ctx, plan: str, *, override=None):
    ctx.empresa.plan = plan
    ctx.empresa.limite_recursos = override
    db.commit()


def _profesionales(db, empresa_id) -> int:
    return (
        db.query(Recurso)
        .filter_by(empresa_id=empresa_id, activo=True, tipo=TipoRecurso.PERSONA)
        .count()
    )


def _crear_prof(client, ctx, nombre="Nuevo"):
    return client.post(
        "/recursos", headers=token_de(ctx.dueno), json={"nombre": nombre, "tipo": "persona"}
    )


# ══════════════════════════════════════════════════════════════════════
#  La grilla
# ══════════════════════════════════════════════════════════════════════

def test_la_grilla_es_la_acordada():
    g = planes.GRILLA
    assert g[planes.Plan.BASICO].precio == 14990
    assert g[planes.Plan.BASICO].profesionales == 3
    assert g[planes.Plan.BASICO].sucursales == 1

    assert g[planes.Plan.PRO].precio == 24990
    assert g[planes.Plan.PRO].profesionales == 10
    assert g[planes.Plan.PRO].sucursales == 1

    assert g[planes.Plan.MULTI].precio == 35990
    assert g[planes.Plan.MULTI].profesionales is None, "Multi = ilimitados"
    assert g[planes.Plan.MULTI].sucursales == 5


def test_un_plan_desconocido_cae_al_mas_restrictivo():
    """La columna estuvo meses aceptando texto libre: puede haber cualquier cosa.

    Equivocarse hacia arriba sería regalar un plan que nadie pagó.
    """
    assert planes.plan_de("cualquier-cosa") is planes.Plan.GRATUITO
    assert planes.plan_de(None) is planes.Plan.GRATUITO
    assert planes.plan_de("") is planes.Plan.GRATUITO
    assert planes.plan_de("  PRO  ") is planes.Plan.PRO


def test_la_prueba_no_se_ofrece_como_plan_a_la_venta():
    codigos = [p["codigo"] for p in planes.para_mostrar()]
    assert "gratuito" not in codigos
    assert codigos == ["basico", "pro", "multi"]


# ══════════════════════════════════════════════════════════════════════
#  El tope BLOQUEA
# ══════════════════════════════════════════════════════════════════════

def test_el_plan_basico_frena_en_el_cuarto_profesional(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "basico")
    # armar_empresa ya deja 2 profesionales cargados.
    while _profesionales(db, ctx.empresa.id) < 3:
        assert _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}").status_code == 201
        db.expire_all()

    r = _crear_prof(client, ctx, "El cuarto")
    assert r.status_code == 409, "El plan de 3 tiene que frenar en el cuarto."
    assert "Básico" in r.json()["detail"]
    assert "Mi suscripción" in r.json()["detail"], (
        "El mensaje tiene que decir a dónde ir, no solo que no se puede."
    )


def test_el_plan_pro_deja_llegar_a_diez(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "pro")
    while _profesionales(db, ctx.empresa.id) < 10:
        r = _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        assert r.status_code == 201, r.text
        db.expire_all()
    assert _crear_prof(client, ctx, "El once").status_code == 409


def test_el_plan_multi_no_tiene_tope_de_profesionales(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    for i in range(12):
        assert _crear_prof(client, ctx, f"Multi{i}").status_code == 201


def test_un_box_no_ocupa_asiento_del_plan(client, db, armar_empresa):
    """El cupo es de PROFESIONALES. Un box o un equipo no paga asiento."""
    ctx = armar_empresa()
    _plan(db, ctx, "basico")
    while _profesionales(db, ctx.empresa.id) < 3:
        _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        db.expire_all()

    r = client.post(
        "/recursos", headers=token_de(ctx.dueno), json={"nombre": "Box 1", "tipo": "box"}
    )
    assert r.status_code == 201, r.text


def test_desactivar_a_alguien_libera_su_lugar(client, db, armar_empresa):
    """El que se fue del negocio no tiene que seguir ocupando un asiento."""
    ctx = armar_empresa()
    _plan(db, ctx, "basico")
    while _profesionales(db, ctx.empresa.id) < 3:
        _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        db.expire_all()
    assert _crear_prof(client, ctx, "Sobra").status_code == 409

    client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": False}
    )
    db.expire_all()
    assert _crear_prof(client, ctx, "Ahora si").status_code == 201


def test_no_se_puede_esquivar_el_cupo_reactivando(client, db, armar_empresa):
    """Desactivar a uno, crear al cuarto, y volver a activar al primero."""
    ctx = armar_empresa()
    _plan(db, ctx, "basico")
    while _profesionales(db, ctx.empresa.id) < 3:
        _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        db.expire_all()

    client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": False}
    )
    _crear_prof(client, ctx, "El cuarto")
    db.expire_all()

    r = client.patch(
        f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno), json={"activo": True}
    )
    assert r.status_code == 409, "Reactivar ocupa un asiento igual que dar de alta."


def test_el_override_del_super_admin_pisa_al_plan(client, db, armar_empresa):
    """Para hacerle un cupo especial a un cliente sin inventar un plan."""
    ctx = armar_empresa()
    _plan(db, ctx, "basico", override=6)
    while _profesionales(db, ctx.empresa.id) < 6:
        r = _crear_prof(client, ctx, f"P{uuid.uuid4().hex[:5]}")
        assert r.status_code == 201, r.text
        db.expire_all()
    assert _crear_prof(client, ctx, "El septimo").status_code == 409


def test_lo_que_ya_existe_no_se_rompe(client, db, armar_empresa):
    """Enforcement solo al ALTA: nadie pierde lo que ya tenía cargado."""
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    for i in range(8):
        _crear_prof(client, ctx, f"Viejo{i}")
    _plan(db, ctx, "basico")  # lo bajan de plan
    db.expire_all()

    # Los 10 siguen ahí y siguen funcionando.
    assert _profesionales(db, ctx.empresa.id) == 10
    r = client.get("/recursos", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    # Pero no puede sumar uno más.
    assert _crear_prof(client, ctx, "Uno mas").status_code == 409


# ══════════════════════════════════════════════════════════════════════
#  Pagar cambia el plan
# ══════════════════════════════════════════════════════════════════════

def test_registrar_un_pago_saca_a_la_empresa_de_la_prueba(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    _plan(db, ctx, "gratuito")

    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 14990, "metodo": "transferencia", "renovar": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).plan == "basico"


def test_renovar_30_dias_pasa_al_plan_de_entrada_no_al_del_medio(
    client, db, armar_empresa, admin
):
    """Antes saltaba directo a "pro": una cortesía regalaba el cupo de 10."""
    ctx = armar_empresa()
    _plan(db, ctx, "gratuito")

    client.patch(
        f"/admin/empresas/{ctx.empresa.id}/suscripcion",
        headers=admin,
        json={"renovar_30": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).plan == "basico"


def test_un_pago_no_baja_de_plan_a_quien_ya_tenia_uno_mejor(
    client, db, armar_empresa, admin
):
    ctx = armar_empresa()
    _plan(db, ctx, "multi")
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 35990, "metodo": "transferencia", "renovar": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).plan == "multi"


def test_el_plan_ya_no_acepta_texto_libre(client, armar_empresa, admin):
    ctx = armar_empresa()
    r = client.patch(
        f"/admin/empresas/{ctx.empresa.id}/suscripcion",
        headers=admin,
        json={"plan": "plan-inventado"},
    )
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════
#  El dueño ve su cupo antes de chocarse con él
# ══════════════════════════════════════════════════════════════════════

def test_mi_suscripcion_muestra_el_cupo_y_la_grilla(client, db, armar_empresa):
    ctx = armar_empresa()
    _plan(db, ctx, "basico")

    r = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["plan_etiqueta"] == "Básico"
    assert d["profesionales_tope"] == 3
    assert d["profesionales_usados"] == 2
    assert len(d["grilla"]) == 3


# ══════════════════════════════════════════════════════════════════════
#  El dueño administra su propio equipo
# ══════════════════════════════════════════════════════════════════════

def test_el_dueno_puede_dar_de_alta_a_su_equipo(client, db, armar_empresa):
    """Antes había que escribirle al super-admin para sumar una recepcionista."""
    ctx = armar_empresa()
    r = client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.dueno),
        json={
            "nombre": "Sofía Recepción",
            "email": f"sofi-{uuid.uuid4().hex[:6]}@example.com",
            "clave": "clave1234",
            "rol": "recepcion",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["rol"] == "recepcion"
    assert r.json()["email_recuperable"] is True


def test_el_dueno_puede_corregir_un_nombre(client, armar_empresa):
    ctx = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"nombre": "Nombre Corregido"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Nombre Corregido"


def test_el_dueno_no_puede_crear_otro_dueno(client, armar_empresa):
    """Un rol que toca la facturación no se regala desde una pantalla."""
    ctx = armar_empresa()
    r = client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.dueno),
        json={
            "nombre": "Otro Dueño",
            "email": f"otro-{uuid.uuid4().hex[:6]}@example.com",
            "clave": "clave1234",
            "rol": "dueno",
        },
    )
    assert r.status_code == 422


def test_el_dueno_no_se_puede_desactivar_a_si_mismo(client, armar_empresa):
    """Quedaría afuera de su panel y nadie podría reactivarlo."""
    ctx = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{ctx.dueno.id}",
        headers=token_de(ctx.dueno),
        json={"activo": False},
    )
    assert r.status_code == 409


def test_no_se_puede_pisar_el_email_de_otra_cuenta(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{ctx.profesional.id}",
        headers=token_de(ctx.dueno),
        json={"email": ctx.dueno.email},
    )
    assert r.status_code == 409


def test_no_se_puede_tocar_al_equipo_de_otra_empresa(client, armar_empresa):
    a = armar_empresa()
    b = armar_empresa()
    r = client.patch(
        f"/equipo/usuarios/{b.profesional.id}",
        headers=token_de(a.dueno),
        json={"nombre": "Hackeado"},
    )
    assert r.status_code == 404


def test_recepcion_no_administra_el_equipo(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        "/equipo/usuarios",
        headers=token_de(ctx.profesional),
        json={
            "nombre": "Colado",
            "email": f"c-{uuid.uuid4().hex[:6]}@example.com",
            "clave": "clave1234",
            "rol": "profesional",
        },
    )
    assert r.status_code in (401, 403)
