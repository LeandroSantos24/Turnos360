"""Multisucursal, paso 2: el ABM de locales y el tope del plan.

Dos cosas se cuidan acá, y la segunda importa más que la primera:

1. Que el tope de sucursales BLOQUEE. `limite_recursos` existió meses sin
   bloquear nada: se pintaba en ámbar en el panel del super-admin y una empresa
   del plan de 3 podía cargar 40 profesionales. Un límite que no frena no es un
   límite, es un adorno, y un plan que no se puede hacer cumplir no se puede
   vender.

2. Que cerrar un local no pueda romper el negocio. Son dos candados: que nunca
   quede en cero (el invariante del paso 1) y que no se cierre un local con
   gente trabajando adentro.
"""

import uuid

import pytest

from app.core import planes
from app.models import Recurso, Sucursal
from app.models.enums import TipoRecurso

from .conftest import token_de


def _crear(client, ctx, nombre="Centro", **extra):
    return client.post(
        "/sucursales",
        headers=token_de(ctx.dueno),
        json={"nombre": nombre, **extra},
    )


def _multi(db, ctx, tope=5):
    """Pone a la empresa en un plan que permita varios locales."""
    ctx.empresa.plan = planes.Plan.MULTI.value
    ctx.empresa.limite_sucursales = tope
    db.flush()


# ══════════════════════════════════════════════════════════════════════
#  1. El tope del plan bloquea de verdad
# ══════════════════════════════════════════════════════════════════════

def test_el_plan_basico_no_puede_abrir_un_segundo_local(client, db, armar_empresa):
    a = armar_empresa()
    a.empresa.plan = planes.Plan.BASICO.value
    db.commit()

    r = _crear(client, a)
    assert r.status_code == 409, r.text
    assert "Básico" in r.json()["detail"], (
        "El mensaje tiene que decir QUÉ plan tiene y cuál necesita: si no, el "
        "dueño no sabe qué hacer con el error."
    )
    assert "Multi" in r.json()["detail"]


def test_el_plan_multi_puede_abrir_locales_hasta_su_tope(client, db, armar_empresa):
    a = armar_empresa()
    _multi(db, a, tope=3)
    db.commit()

    assert _crear(client, a, "Centro").status_code == 201
    assert _crear(client, a, "Norte").status_code == 201
    # Ya son tres con la principal: el cuarto rebota.
    r = _crear(client, a, "Sur")
    assert r.status_code == 409, r.text


def test_el_override_de_la_ficha_comercial_manda_sobre_la_grilla(
    client, db, armar_empresa
):
    """Un cliente con un trato especial no obliga a inventar un plan nuevo."""
    a = armar_empresa()
    a.empresa.plan = planes.Plan.BASICO.value
    a.empresa.limite_sucursales = 2
    db.commit()

    assert _crear(client, a, "Centro").status_code == 201
    assert _crear(client, a, "Norte").status_code == 409


def test_un_local_cerrado_no_ocupa_cupo(client, db, armar_empresa):
    """Mismo criterio que un profesional desactivado: no ocupa asiento."""
    a = armar_empresa()
    _multi(db, a, tope=2)
    db.commit()

    creado = _crear(client, a, "Centro")
    assert creado.status_code == 201
    assert _crear(client, a, "Norte").status_code == 409

    cerrar = client.patch(
        f"/sucursales/{creado.json()['id']}",
        headers=token_de(a.dueno),
        json={"activa": False},
    )
    assert cerrar.status_code == 200, cerrar.text
    assert _crear(client, a, "Norte").status_code == 201


def test_reabrir_un_local_tambien_pasa_por_el_cupo(client, db, armar_empresa):
    """Si no, el tope se esquiva cerrando uno, abriendo otro y reabriendo."""
    a = armar_empresa()
    _multi(db, a, tope=2)
    db.commit()

    centro = _crear(client, a, "Centro").json()
    client.patch(
        f"/sucursales/{centro['id']}",
        headers=token_de(a.dueno),
        json={"activa": False},
    )
    assert _crear(client, a, "Norte").status_code == 201

    r = client.patch(
        f"/sucursales/{centro['id']}",
        headers=token_de(a.dueno),
        json={"activa": True},
    )
    assert r.status_code == 409, r.text


# ══════════════════════════════════════════════════════════════════════
#  2. Cerrar un local no puede romper el negocio
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_cerrar_el_unico_local(client, db, armar_empresa):
    """Si llega a cero, las altas siguientes no tienen dónde caer."""
    a = armar_empresa()
    db.commit()

    r = client.patch(
        f"/sucursales/{a.sede.id}", headers=token_de(a.dueno), json={"activa": False}
    )
    assert r.status_code == 409, r.text
    assert "único local" in r.json()["detail"]


def test_no_se_puede_cerrar_un_local_con_gente_adentro(client, db, armar_empresa):
    """El profesional no desaparecería de la base, pero sí de la agenda."""
    a = armar_empresa()
    _multi(db, a)
    otra = Sucursal(empresa_id=a.empresa.id, nombre="Centro", activa=True)
    db.add(otra)
    db.flush()
    db.add(
        Recurso(
            empresa_id=a.empresa.id,
            sucursal_id=otra.id,
            nombre="Sofía",
            tipo=TipoRecurso.PERSONA,
        )
    )
    db.commit()

    r = client.patch(
        f"/sucursales/{otra.id}", headers=token_de(a.dueno), json={"activa": False}
    )
    assert r.status_code == 409, r.text
    assert "Sofía" not in r.json()["detail"]  # dice cuántos, no los nombra
    assert "1 profesional" in r.json()["detail"]


def test_un_local_vacio_si_se_puede_cerrar(client, db, armar_empresa):
    a = armar_empresa()
    _multi(db, a)
    db.commit()

    creado = _crear(client, a, "Centro").json()
    r = client.patch(
        f"/sucursales/{creado['id']}",
        headers=token_de(a.dueno),
        json={"activa": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["activa"] is False


# ══════════════════════════════════════════════════════════════════════
#  3. Tenencia: el local de otro negocio no existe
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_editar_el_local_de_otra_empresa(client, db, armar_empresa):
    a = armar_empresa()
    b = armar_empresa()
    db.commit()

    r = client.patch(
        f"/sucursales/{b.sede.id}",
        headers=token_de(a.dueno),
        json={"nombre": "Robado"},
    )
    assert r.status_code == 404, r.text
    db.refresh(b.sede)
    assert b.sede.nombre != "Robado"


def test_la_lista_solo_trae_los_locales_propios(client, db, armar_empresa):
    a = armar_empresa()
    b = armar_empresa()
    db.commit()

    r = client.get("/sucursales", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    ids = {s["id"] for s in r.json()["sucursales"]}
    assert a.sede.id in ids
    assert b.sede.id not in ids


# ══════════════════════════════════════════════════════════════════════
#  4. Solo el dueño
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("accion", ["listar", "crear", "editar"])
def test_recepcion_no_toca_los_locales(client, db, armar_empresa, accion):
    """Abrir o cerrar un local es una decisión comercial, como cambiar de plan."""
    a = armar_empresa()
    db.commit()
    cab = token_de(a.profesional)

    if accion == "listar":
        r = client.get("/sucursales", headers=cab)
    elif accion == "crear":
        r = client.post("/sucursales", headers=cab, json={"nombre": "Centro"})
    else:
        r = client.patch(
            f"/sucursales/{a.sede.id}", headers=cab, json={"nombre": "Otro"}
        )
    assert r.status_code == 403, r.text


# ══════════════════════════════════════════════════════════════════════
#  5. Lo que la pantalla necesita para esconderse sola
# ══════════════════════════════════════════════════════════════════════

def test_el_panel_sabe_cuantos_locales_permite_el_plan(client, db, armar_empresa):
    """Con tope 1 el menú «Sucursales» no se muestra. Es lo que protege al
    plan de entrada: el barbero de una silla nunca ve la palabra."""
    a = armar_empresa()
    a.empresa.plan = planes.Plan.BASICO.value
    db.commit()

    r = client.get("/empresa/actual", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    assert r.json()["limite_sucursales"] == 1

    _multi(db, a, tope=5)
    db.commit()
    r = client.get("/empresa/actual", headers=token_de(a.dueno))
    assert r.json()["limite_sucursales"] == 5


def test_la_lista_dice_cuanta_gente_trabaja_en_cada_local(client, db, armar_empresa):
    """Es lo que el dueño mira antes de cerrar uno."""
    a = armar_empresa()
    db.commit()

    r = client.get("/sucursales", headers=token_de(a.dueno))
    fila = next(s for s in r.json()["sucursales"] if s["id"] == a.sede.id)
    assert fila["profesionales"] == 2, "El fixture crea a Lucas y a Pablo."
    assert fila["es_principal"] is True


def test_el_nombre_se_limpia_y_no_puede_quedar_vacio(client, db, armar_empresa):
    a = armar_empresa()
    _multi(db, a)
    db.commit()

    assert _crear(client, a, "   ").status_code == 422
    r = _crear(client, a, "  Centro  ")
    assert r.status_code == 201, r.text
    assert r.json()["nombre"] == "Centro"


def test_editar_no_pisa_lo_que_no_vino(client, db, armar_empresa):
    a = armar_empresa()
    _multi(db, a)
    db.commit()

    creado = _crear(client, a, "Centro", direccion="San Martín 100").json()
    r = client.patch(
        f"/sucursales/{creado['id']}",
        headers=token_de(a.dueno),
        json={"telefono": "2614000000"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["direccion"] == "San Martín 100", (
        "Mandar solo el teléfono no puede borrar la dirección."
    )
    assert r.json()["nombre"] == "Centro"


def test_un_local_cerrado_sigue_apareciendo_en_la_lista(client, db, armar_empresa):
    """Un local cerrado tiene turnos y caja: esconderlo haría creer que esa
    plata desapareció."""
    a = armar_empresa()
    _multi(db, a)
    db.commit()

    creado = _crear(client, a, f"Centro {uuid.uuid4().hex[:4]}").json()
    client.patch(
        f"/sucursales/{creado['id']}",
        headers=token_de(a.dueno),
        json={"activa": False},
    )
    r = client.get("/sucursales", headers=token_de(a.dueno))
    fila = next(s for s in r.json()["sucursales"] if s["id"] == creado["id"])
    assert fila["activa"] is False
    assert r.json()["usadas"] == 1, "El cerrado no cuenta para el cupo."
