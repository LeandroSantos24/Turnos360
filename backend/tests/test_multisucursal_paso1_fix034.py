"""Multisucursal, paso 1: toda empresa tiene exactamente un local.

La apuesta de diseño de toda la fase está acá: `sucursal_id` deja de poder ser
NULL. A cambio, agenda, caja, disponibilidad y estadísticas van a poder filtrar
por local SIEMPRE, sin un `OR sucursal_id IS NULL` colgado de cada consulta
para no perder los datos viejos.

Lo que estos tests cuidan son las dos mitades de esa apuesta:

1. Que el invariante se cumpla por todos los caminos de alta que existen, y que
   ni siquiera un `Recurso(...)` escrito a mano pueda dejar la columna vacía.
2. Que para un negocio de UN local no cambie absolutamente nada. Ese es el
   criterio de aceptación de la fase: el plan de entrada no se toca.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Caja, Empresa, Recurso, Rubro, Sucursal, SuperAdmin, Usuario
from app.models.enums import TipoRecurso
from app.services import sucursal as sucursal_svc

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
    r = Rubro(codigo=f"r-{uuid.uuid4().hex[:8]}", nombre="Rubro Test", preset={})
    db.add(r)
    db.flush()
    return r


# ══════════════════════════════════════════════════════════════════════
#  1. Nunca cero sucursales
# ══════════════════════════════════════════════════════════════════════

def test_el_alta_del_super_admin_le_deja_su_local(client, db, admin, rubro):
    s = uuid.uuid4().hex[:6]
    r = client.post(
        "/admin/empresas",
        headers=admin,
        json={
            "nombre": "Barbería Nueva",
            "slug": f"barberia-nueva-{s}",
            "rubro_id": rubro.id,
            "dueno": {
                "nombre": "Dueño",
                "email": f"d-{s}@example.com",
                "clave": "clave1234",
            },
        },
    )
    assert r.status_code == 201, r.text
    empresa_id = r.json()["id"]

    sede = sucursal_svc.principal_de(db, empresa_id)
    assert sede is not None, "La empresa nació sin local."
    assert sede.nombre == "Barbería Nueva", (
        "El local se llama como el negocio: cuando el dueño agregue el segundo, "
        "el selector tiene que distinguirlos sin explicación."
    )


def test_el_registro_publico_tambien_deja_su_local(client, db):
    s = uuid.uuid4().hex[:6]
    rub = Rubro(codigo=f"pub-{s}", nombre="Peluquería", preset={})
    db.add(rub)
    db.commit()

    r = client.post(
        "/publico/registro",
        json={
            "nombre_negocio": f"Peluquería {s}",
            "slug": f"pelu-{s}",
            "rubro_codigo": rub.codigo,
            "nombre": "Ana",
            "email": f"ana-{s}@example.com",
            "clave": "clave1234",
        },
    )
    assert r.status_code in (200, 201), r.text

    empresa = db.scalar(select(Empresa).where(Empresa.slug == f"pelu-{s}"))
    assert sucursal_svc.principal_de(db, empresa.id) is not None


def test_el_dueno_queda_asignado_a_su_local(client, db, admin, rubro):
    """Si el dueño no pertenece a ningún local, con dos sucursales no ve nada."""
    s = uuid.uuid4().hex[:6]
    r = client.post(
        "/admin/empresas",
        headers=admin,
        json={
            "nombre": "Negocio",
            "slug": f"neg-{s}",
            "rubro_id": rubro.id,
            "dueno": {
                "nombre": "Dueño",
                "email": f"d2-{s}@example.com",
                "clave": "clave1234",
            },
        },
    )
    assert r.status_code == 201, r.text
    empresa_id = r.json()["id"]

    dueno = db.scalar(select(Usuario).where(Usuario.empresa_id == empresa_id))
    assert dueno.sucursal_id == sucursal_svc.id_principal(db, empresa_id)


# ══════════════════════════════════════════════════════════════════════
#  2. La columna no puede quedar vacía por ningún camino
# ══════════════════════════════════════════════════════════════════════

def test_un_recurso_escrito_a_mano_cae_solo_en_el_local_principal(db, armar_empresa):
    """El invariante no depende de que cada alta se acuerde del campo.

    Sin esto, alcanza con que UN alta nueva se olvide de `sucursal_id` para que
    salte un IntegrityError en producción — y es un olvido fácil, porque el
    campo no aparece en ningún formulario mientras haya un solo local.
    """
    a = armar_empresa()
    r = Recurso(empresa_id=a.empresa.id, nombre="A mano", tipo=TipoRecurso.PERSONA)
    db.add(r)
    db.flush()
    assert r.sucursal_id == a.sede.id


def test_la_caja_tambien_nace_con_local(db, armar_empresa):
    a = armar_empresa()
    c = Caja(empresa_id=a.empresa.id, saldo_inicial=0)
    db.add(c)
    db.flush()
    assert c.sucursal_id == a.sede.id


def test_el_turno_hereda_el_local_del_profesional(client, db, armar_empresa):
    """Se copia, no se joinea: el local de un turno que ya pasó no puede
    cambiar porque el profesional se mude de sucursal el mes que viene."""
    import datetime as dt

    a = armar_empresa()
    db.commit()
    cuando = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)
    r = client.post(
        "/turnos",
        headers=token_de(a.dueno),
        json={
            "cliente_id": a.cliente.id,
            "recurso_id": a.lucas.id,
            "servicio_id": a.servicio.id,
            "fecha_inicio": cuando.isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    assert r.json().get("sucursal_id", a.sede.id) == a.sede.id
    from app.models import Turno

    turno = db.get(Turno, r.json()["id"])
    assert turno.sucursal_id == a.lucas.sucursal_id


# ══════════════════════════════════════════════════════════════════════
#  3. La base rechaza el local de otra empresa
# ══════════════════════════════════════════════════════════════════════

def test_la_base_rechaza_un_recurso_en_el_local_de_otra_empresa(db, armar_empresa):
    """Regla 1 puesta donde no se puede olvidar.

    El service ya lo valida (fix-030), pero esa validación depende de que cada
    camino de código se acuerde de llamarla. La FK compuesta
    (empresa_id, sucursal_id) hace que la base misma lo rechace, venga por
    donde venga.
    """
    a = armar_empresa()
    b = armar_empresa()

    ajeno = Recurso(
        empresa_id=a.empresa.id,
        sucursal_id=b.sede.id,
        nombre="Colado",
        tipo=TipoRecurso.PERSONA,
    )
    db.add(ajeno)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_la_base_rechaza_una_caja_en_el_local_de_otra_empresa(db, armar_empresa):
    a = armar_empresa()
    b = armar_empresa()
    db.add(Caja(empresa_id=a.empresa.id, sucursal_id=b.sede.id, saldo_inicial=0))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ══════════════════════════════════════════════════════════════════════
#  4. Para un negocio de un local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_el_alta_de_profesional_no_pide_ningun_campo_nuevo(client, armar_empresa):
    """El criterio de aceptación de toda la fase, escrito como test."""
    a = armar_empresa()
    r = client.post(
        "/recursos",
        headers=token_de(a.dueno),
        json={"nombre": "Nuevo", "tipo": "persona"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["sucursal_id"] == a.sede.id


def test_una_empresa_de_un_local_reporta_una_sucursal(db, armar_empresa):
    a = armar_empresa()
    assert sucursal_svc.cuantas(db, a.empresa.id) == 1, (
        "La interfaz usa este número para decidir si esconde todo lo de "
        "sucursales. Si da distinto de 1, al barbero de una silla le aparece "
        "un menú que no necesita."
    )


def test_id_principal_repara_una_empresa_sin_local(db, rubro):
    """No debería pasar nunca. Si pasa, es mejor repararlo que romper un alta."""
    s = uuid.uuid4().hex[:6]
    emp = Empresa(nombre="Huérfana", slug=f"huerfana-{s}", rubro_id=rubro.id)
    db.add(emp)
    db.flush()
    assert sucursal_svc.principal_de(db, emp.id) is None

    sid = sucursal_svc.id_principal(db, emp.id)
    assert db.get(Sucursal, sid).empresa_id == emp.id


def test_principal_de_ignora_los_locales_desactivados(db, armar_empresa):
    a = armar_empresa()
    otra = Sucursal(empresa_id=a.empresa.id, nombre="Cerrada", activa=False)
    db.add(otra)
    db.flush()
    a.sede.activa = False
    db.flush()
    assert sucursal_svc.principal_de(db, a.empresa.id) is None


def test_mandar_sucursal_null_al_editar_no_rompe_nada(client, db, armar_empresa):
    """`{"sucursal_id": null}` antes significaba "sin local". Ahora no existe
    ese estado, y sin este cuidado el pedido terminaba en un 500."""
    a = armar_empresa()
    db.commit()
    r = client.patch(
        f"/recursos/{a.lucas.id}",
        headers=token_de(a.dueno),
        json={"sucursal_id": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sucursal_id"] == a.sede.id
