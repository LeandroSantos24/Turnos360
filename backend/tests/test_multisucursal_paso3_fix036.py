"""Multisucursal, paso 3a: el profesional pertenece a un local.

El backend ya aceptaba `sucursal_id` al crear y editar un recurso (fix-030 le
puso la validación por tenant). Lo que faltaba era que sirviera para algo: que
mover a alguien de local cambie de verdad quién trabaja dónde, y que el
recuento que mira el dueño antes de cerrar un local diga la verdad.

El criterio de aceptación sigue siendo el mismo: para un negocio de un solo
local, nada de esto se nota.
"""

import pytest

from app.core import planes
from app.models import Recurso, Sucursal

from .conftest import token_de


@pytest.fixture()
def dos_locales(db, armar_empresa):
    """Una empresa en plan Multi con un segundo local vacío."""
    a = armar_empresa()
    a.empresa.plan = planes.Plan.MULTI.value
    a.empresa.limite_sucursales = 5
    otra = Sucursal(empresa_id=a.empresa.id, nombre="Centro", activa=True)
    db.add(otra)
    db.flush()
    a.centro = otra
    db.commit()
    return a


# ══════════════════════════════════════════════════════════════════════
#  1. Asignar y mover
# ══════════════════════════════════════════════════════════════════════

def test_se_puede_dar_de_alta_un_profesional_en_el_segundo_local(client, dos_locales):
    a = dos_locales
    r = client.post(
        "/recursos",
        headers=token_de(a.dueno),
        json={"nombre": "Sofía", "tipo": "persona", "sucursal_id": a.centro.id},
    )
    assert r.status_code == 201, r.text
    assert r.json()["sucursal_id"] == a.centro.id


def test_mover_un_profesional_de_local_cambia_los_recuentos(client, db, dos_locales):
    """Es lo que el dueño mira antes de cerrar un local: si el número no se
    mueve, no tiene forma de saber que ya puede cerrarlo."""
    a = dos_locales

    antes = client.get("/sucursales", headers=token_de(a.dueno)).json()["sucursales"]
    assert {s["id"]: s["profesionales"] for s in antes}[a.sede.id] == 2

    r = client.patch(
        f"/recursos/{a.lucas.id}",
        headers=token_de(a.dueno),
        json={"sucursal_id": a.centro.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sucursal_id"] == a.centro.id

    despues = client.get("/sucursales", headers=token_de(a.dueno)).json()["sucursales"]
    conteo = {s["id"]: s["profesionales"] for s in despues}
    assert conteo[a.sede.id] == 1
    assert conteo[a.centro.id] == 1


def test_vaciar_un_local_lo_habilita_a_cerrarse(client, db, dos_locales):
    """El circuito completo tal como lo vive el dueño: intenta cerrar, le dicen
    que mueva a la gente, la mueve, y ahora sí puede."""
    a = dos_locales
    cab = token_de(a.dueno)

    primero = client.patch(f"/sucursales/{a.sede.id}", headers=cab, json={"activa": False})
    assert primero.status_code == 409
    assert "2 profesionales" in primero.json()["detail"]

    for recurso in (a.lucas, a.pablo):
        client.patch(
            f"/recursos/{recurso.id}", headers=cab, json={"sucursal_id": a.centro.id}
        )

    segundo = client.patch(f"/sucursales/{a.sede.id}", headers=cab, json={"activa": False})
    assert segundo.status_code == 200, segundo.text


def test_un_profesional_desactivado_no_traba_el_cierre(client, db, dos_locales):
    """Se cuentan los activos: alguien que ya no trabaja acá no puede impedir
    que se cierre el local."""
    a = dos_locales
    cab = token_de(a.dueno)
    for recurso in (a.lucas, a.pablo):
        client.delete(f"/recursos/{recurso.id}", headers=cab)

    r = client.patch(f"/sucursales/{a.sede.id}", headers=cab, json={"activa": False})
    assert r.status_code == 200, r.text


# ══════════════════════════════════════════════════════════════════════
#  2. Tenencia
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_mover_a_alguien_al_local_de_otra_empresa(
    client, db, armar_empresa
):
    a = armar_empresa()
    b = armar_empresa()
    db.commit()

    r = client.patch(
        f"/recursos/{a.lucas.id}",
        headers=token_de(a.dueno),
        json={"sucursal_id": b.sede.id},
    )
    assert r.status_code == 404, r.text
    db.expire_all()
    assert db.get(Recurso, a.lucas.id).sucursal_id == a.sede.id


# ══════════════════════════════════════════════════════════════════════
#  3. Para un solo local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_con_un_solo_local_el_alta_sigue_sin_pedir_nada(client, armar_empresa):
    a = armar_empresa()
    r = client.post(
        "/recursos", headers=token_de(a.dueno), json={"nombre": "Nuevo", "tipo": "persona"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["sucursal_id"] == a.sede.id


def test_todo_recurso_devuelve_su_local(client, armar_empresa):
    """La pantalla muestra la columna "Local" solo con varios locales, pero el
    dato viaja siempre: si fuera opcional, habría que defenderse del null en
    cada lugar que lo lee."""
    a = armar_empresa()
    r = client.get("/recursos", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    assert r.json()["items"], "El fixture crea dos recursos."
    for item in r.json()["items"]:
        assert item["sucursal_id"] == a.sede.id
