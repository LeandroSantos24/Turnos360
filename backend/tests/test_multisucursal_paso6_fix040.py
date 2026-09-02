"""Multisucursal, paso 6: cada uno ve su local.

Este es el permiso que hace que el plan Multi valga la plata. Sin él, la
recepcionista del centro ve la agenda, la caja y la facturación del barrio, y
un negocio con dos locales no tiene ningún motivo para pagar el plan de
arriba.

El criterio de las respuestas: se ignora el local pedido, o se contesta 404.
Nunca 403 — decir "no autorizado" confirmaría que ese local, ese profesional o
ese arqueo existen, que es exactamente lo que no queremos contarle a alguien
que está probando ids a mano.

Y como siempre: para un negocio de un solo local esto no cambia nada, porque
el único local es el de todos.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.core import planes
from app.core.crypto import hash_clave
from app.models import (
    Caja,
    HorarioRecurso,
    Recurso,
    ServicioSucursal,
    Sucursal,
    Usuario,
)
from app.models.enums import RolUsuario, TipoRecurso

from .conftest import token_de


@pytest.fixture()
def dos_locales(db, armar_empresa):
    a = armar_empresa()
    a.empresa.plan = planes.Plan.MULTI.value
    a.empresa.limite_sucursales = 5
    centro = Sucursal(empresa_id=a.empresa.id, nombre="Centro", activa=True)
    db.add(centro)
    db.flush()

    sofia = Recurso(
        empresa_id=a.empresa.id,
        sucursal_id=centro.id,
        nombre="Sofía",
        tipo=TipoRecurso.PERSONA,
    )
    db.add(sofia)
    db.flush()
    for dia in range(7):
        db.add(
            HorarioRecurso(
                empresa_id=a.empresa.id,
                recurso_id=sofia.id,
                dia_semana=dia,
                hora_desde=dt.time(0, 0),
                hora_hasta=dt.time(23, 59),
            )
        )
    a.servicio.recursos.append(sofia)
    db.add(
        ServicioSucursal(
            empresa_id=a.empresa.id, servicio_id=a.servicio.id, sucursal_id=centro.id
        )
    )

    recep = Usuario(
        empresa_id=a.empresa.id,
        sucursal_id=centro.id,
        nombre="Recepción Centro",
        email=f"rc6-{centro.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recep)
    db.flush()

    a.centro = centro
    a.sofia = sofia
    a.recep_centro = recep
    db.commit()
    return a


# ══════════════════════════════════════════════════════════════════════
#  1. Recepción ve solo su local
# ══════════════════════════════════════════════════════════════════════

def test_recepcion_solo_ve_los_profesionales_de_su_local(client, dos_locales):
    a = dos_locales
    r = client.get("/recursos", headers=token_de(a.recep_centro))
    assert r.status_code == 200, r.text
    assert [x["nombre"] for x in r.json()["items"]] == ["Sofía"]


def test_pedir_otro_local_no_le_sirve_de_nada(client, dos_locales):
    """Se ignora lo pedido en vez de contestar 403: un 403 confirmaría que ese
    local existe."""
    a = dos_locales
    r = client.get(
        f"/recursos?sucursal_id={a.sede.id}", headers=token_de(a.recep_centro)
    )
    assert r.status_code == 200, r.text
    assert [x["nombre"] for x in r.json()["items"]] == ["Sofía"]


def test_el_dueno_si_ve_todos_los_locales(client, dos_locales):
    """Es lo que hace que el plan Multi valga la plata."""
    a = dos_locales
    r = client.get("/recursos", headers=token_de(a.dueno))
    assert {x["nombre"] for x in r.json()["items"]} == {
        "Lucas Estrella",
        "Pablo Vega",
        "Sofía",
    }


# ══════════════════════════════════════════════════════════════════════
#  2. La agenda
# ══════════════════════════════════════════════════════════════════════

def _reservar(client, ctx, recurso, quien, dias=3):
    cuando = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=dias)
    return client.post(
        "/turnos",
        headers=token_de(quien),
        json={
            "cliente_id": ctx.cliente.id,
            "recurso_id": recurso.id,
            "servicio_id": ctx.servicio.id,
            "fecha_inicio": cuando.isoformat(),
        },
    )


def test_recepcion_solo_ve_los_turnos_de_su_local(client, db, dos_locales):
    a = dos_locales
    assert _reservar(client, a, a.lucas, a.dueno, 3).status_code == 201
    assert _reservar(client, a, a.sofia, a.dueno, 4).status_code == 201

    r = client.get("/turnos", headers=token_de(a.recep_centro)).json()
    assert r["total"] == 1
    assert r["items"][0]["recurso_id"] == a.sofia.id


def test_recepcion_no_puede_agendar_en_otro_local(client, dos_locales):
    """La pantalla no le ofrece a Lucas; llegar a su id es a mano."""
    a = dos_locales
    r = _reservar(client, a, a.lucas, a.recep_centro)
    assert r.status_code == 404, r.text
    assert "no trabaja en tu local" in r.json()["detail"]


def test_recepcion_si_puede_agendar_en_el_suyo(client, dos_locales):
    a = dos_locales
    assert _reservar(client, a, a.sofia, a.recep_centro).status_code == 201


def test_recepcion_no_puede_mover_un_turno_a_otro_local(client, dos_locales):
    a = dos_locales
    creado = _reservar(client, a, a.sofia, a.recep_centro)
    assert creado.status_code == 201

    r = client.patch(
        f"/turnos/{creado.json()['id']}/mover",
        headers=token_de(a.recep_centro),
        json={
            "recurso_id": a.lucas.id,
            "fecha_inicio": (
                dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5)
            ).isoformat(),
        },
    )
    assert r.status_code == 404, r.text


# ══════════════════════════════════════════════════════════════════════
#  3. La plata: lo más sensible
# ══════════════════════════════════════════════════════════════════════

def test_recepcion_no_ve_la_caja_de_otro_local(client, db, dos_locales):
    a = dos_locales
    client.post(
        "/caja/abrir", headers=token_de(a.dueno), json={"saldo_inicial": 111}
    )
    client.post(
        "/caja/abrir", headers=token_de(a.recep_centro), json={"saldo_inicial": 222}
    )

    # Pide explícitamente la de la sede: recibe la suya igual.
    r = client.get(
        f"/caja/actual?sucursal_id={a.sede.id}", headers=token_de(a.recep_centro)
    ).json()
    assert float(r["caja"]["saldo_inicial"]) == 222


def test_recepcion_no_ve_los_movimientos_de_otro_local(client, db, dos_locales):
    a = dos_locales
    client.post("/caja/abrir", headers=token_de(a.dueno), json={"saldo_inicial": 0})
    client.post(
        "/caja/abrir", headers=token_de(a.recep_centro), json={"saldo_inicial": 0}
    )
    turno = _reservar(client, a, a.lucas, a.dueno, 3).json()
    client.post(
        f"/turnos/{turno['id']}/cobro",
        headers=token_de(a.dueno),
        json={"pagos": [{"metodo_pago_id": a.metodo.id, "monto": 9000}]},
    )

    r = client.get(
        f"/movimientos?sucursal_id={a.sede.id}", headers=token_de(a.recep_centro)
    ).json()
    assert r["total"] == 0, (
        "Recepción del centro está viendo la facturación de la sede."
    )
    assert (
        client.get("/movimientos", headers=token_de(a.dueno)).json()["total"] == 1
    ), "El dueño sí tiene que verla."


def test_recepcion_no_puede_abrir_el_arqueo_de_otro_local(client, db, dos_locales):
    """Sin esto el filtro del listado sería decorativo: bastaba probar ids."""
    a = dos_locales
    client.post("/caja/abrir", headers=token_de(a.dueno), json={"saldo_inicial": 0})
    ajena = db.scalar(select(Caja).where(Caja.sucursal_id == a.sede.id))
    r = client.get(
        f"/cajas/{ajena.id}/detalle", headers=token_de(a.recep_centro)
    )
    assert r.status_code == 404, r.text


def test_el_historial_de_cajas_de_recepcion_es_el_de_su_local(
    client, db, dos_locales
):
    a = dos_locales
    client.post("/caja/abrir", headers=token_de(a.dueno), json={"saldo_inicial": 0})
    client.post(
        "/caja/abrir", headers=token_de(a.recep_centro), json={"saldo_inicial": 0}
    )

    suyas = client.get("/cajas", headers=token_de(a.recep_centro)).json()
    assert {c["sucursal_id"] for c in suyas} == {a.centro.id}

    todas = client.get("/cajas", headers=token_de(a.dueno)).json()
    assert {c["sucursal_id"] for c in todas} == {a.sede.id, a.centro.id}


# ══════════════════════════════════════════════════════════════════════
#  4. Con un solo local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_con_un_solo_local_recepcion_ve_todo_como_siempre(
    client, db, armar_empresa
):
    a = armar_empresa()
    recep = Usuario(
        empresa_id=a.empresa.id,
        sucursal_id=a.sede.id,
        nombre="Recepción",
        email=f"r1-{a.empresa.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recep)
    db.commit()

    assert _reservar(client, a, a.lucas, recep).status_code == 201
    r = client.get("/recursos", headers=token_de(recep)).json()
    assert {x["nombre"] for x in r["items"]} == {"Lucas Estrella", "Pablo Vega"}
    assert client.get("/turnos", headers=token_de(recep)).json()["total"] == 1


def test_el_administrador_puede_ver_la_lista_de_locales(client, db, dos_locales):
    """Mira la plata de todos los locales: sin la lista no tendría con qué
    elegir cuál. Abrir y cerrar un local sigue siendo solo del dueño."""
    a = dos_locales
    admin = Usuario(
        empresa_id=a.empresa.id,
        sucursal_id=a.sede.id,
        nombre="Admin",
        email=f"adm-{a.empresa.id}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.ADMIN,
    )
    db.add(admin)
    db.commit()

    assert client.get("/sucursales", headers=token_de(admin)).status_code == 200
    assert (
        client.post(
            "/sucursales", headers=token_de(admin), json={"nombre": "Otro"}
        ).status_code
        == 403
    )
    assert client.get("/sucursales", headers=token_de(a.recep_centro)).status_code == 403
