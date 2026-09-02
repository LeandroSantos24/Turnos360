"""Multisucursal, paso 8: estadísticas comparadas entre locales.

El último paso de la fase. Responde la pregunta que se hace un dueño con dos
sucursales: cuál factura más, cuál tiene el ticket más alto, cuál se está
quedando atrás. Es, junto con los permisos del paso 6, lo que hace que el plan
Multi tenga sentido para él.

La decisión de diseño que hay que cuidar: la comparación (`por_sucursal`)
viene SIEMPRE con todos los locales, aunque el panel esté filtrado a uno.
Filtrarla sería sacarle aquello con lo que se compara — un gráfico de
comparación con una sola barra no compara nada.
"""

import datetime as dt

import pytest

from app.core import planes
from app.models import (
    HorarioRecurso,
    Recurso,
    ServicioSucursal,
    Sucursal,
)
from app.models.enums import TipoRecurso

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
    a.centro = centro
    a.sofia = sofia
    db.commit()
    return a


def _cobrar(client, ctx, recurso, monto, dias):
    cuando = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=dias)
    turno = client.post(
        "/turnos",
        headers=token_de(ctx.dueno),
        json={
            "cliente_id": ctx.cliente.id,
            "recurso_id": recurso.id,
            "servicio_id": ctx.servicio.id,
            "fecha_inicio": cuando.isoformat(),
        },
    )
    assert turno.status_code == 201, turno.text
    r = client.post(
        f"/turnos/{turno.json()['id']}/cobro",
        headers=token_de(ctx.dueno),
        json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": monto}]},
    )
    assert r.status_code == 201, r.text


def _rango():
    ahora = dt.datetime.now(dt.timezone.utc)
    return {
        "desde": (ahora - dt.timedelta(days=1)).isoformat(),
        "hasta": (ahora + dt.timedelta(days=30)).isoformat(),
    }


def _stats(client, ctx, **extra):
    r = client.get(
        "/estadisticas/facturacion",
        headers=token_de(ctx.dueno),
        params={**_rango(), **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════
#  1. La comparación entre locales
# ══════════════════════════════════════════════════════════════════════

def test_compara_la_facturacion_de_los_dos_locales(client, db, dos_locales):
    a = dos_locales
    _cobrar(client, a, a.lucas, 7000, 3)   # sede
    _cobrar(client, a, a.sofia, 3000, 4)   # centro

    filas = {f["sucursal"]: f for f in _stats(client, a)["por_sucursal"]}
    assert filas[a.empresa.nombre]["total"] == 7000
    assert filas["Centro"]["total"] == 3000
    assert filas[a.empresa.nombre]["pct"] == 70.0
    assert filas["Centro"]["pct"] == 30.0


def test_la_comparacion_trae_el_ticket_de_cada_local(client, db, dos_locales):
    """Un local puede facturar menos y tener mejor ticket: es justo el dato
    que no se ve en el total."""
    a = dos_locales
    _cobrar(client, a, a.lucas, 4000, 3)
    _cobrar(client, a, a.lucas, 4000, 4)
    _cobrar(client, a, a.sofia, 6000, 5)

    filas = {f["sucursal"]: f for f in _stats(client, a)["por_sucursal"]}
    assert filas[a.empresa.nombre]["turnos"] == 2
    assert filas[a.empresa.nombre]["ticket"] == 4000
    assert filas["Centro"]["turnos"] == 1
    assert filas["Centro"]["ticket"] == 6000


def test_un_local_sin_facturacion_igual_aparece_en_cero(client, db, dos_locales):
    """Si desapareciera, un local que no vendió nada se leería como si no
    existiera — y esa es justamente la información importante."""
    a = dos_locales
    _cobrar(client, a, a.lucas, 5000, 3)

    filas = {f["sucursal"]: f for f in _stats(client, a)["por_sucursal"]}
    assert filas["Centro"]["total"] == 0
    assert filas["Centro"]["ticket"] == 0


# ══════════════════════════════════════════════════════════════════════
#  2. El filtro por local
# ══════════════════════════════════════════════════════════════════════

def test_filtrar_por_local_acota_todo_el_panel(client, db, dos_locales):
    a = dos_locales
    _cobrar(client, a, a.lucas, 7000, 3)
    _cobrar(client, a, a.sofia, 3000, 4)

    solo_centro = _stats(client, a, sucursal_id=a.centro.id)
    assert solo_centro["facturado_real"] == 3000
    assert solo_centro["cantidad_pagos"] == 1
    assert [p["recurso"] for p in solo_centro["por_profesional"]] == ["Sofía"]


def test_la_comparacion_NO_se_filtra(client, db, dos_locales):
    """La decisión de diseño del paso: aunque el dueño esté mirando un local,
    la comparación tiene que mostrarle los dos. Si se filtrara, elegir un
    local haría desaparecer aquello con lo que se compara."""
    a = dos_locales
    _cobrar(client, a, a.lucas, 7000, 3)
    _cobrar(client, a, a.sofia, 3000, 4)

    solo_centro = _stats(client, a, sucursal_id=a.centro.id)
    assert len(solo_centro["por_sucursal"]) == 2
    filas = {f["sucursal"]: f["total"] for f in solo_centro["por_sucursal"]}
    assert filas[a.empresa.nombre] == 7000


def test_un_local_de_otra_empresa_no_devuelve_nada(client, db, dos_locales, armar_empresa):
    a = dos_locales
    b = armar_empresa()
    _cobrar(client, a, a.lucas, 7000, 3)
    db.commit()

    ajeno = _stats(client, a, sucursal_id=b.sede.id)
    assert ajeno["facturado_real"] == 0
    assert [f["sucursal"] for f in ajeno["por_sucursal"]] != [], (
        "La comparación sigue siendo la de SU empresa."
    )
    assert b.sede.id not in {f["sucursal_id"] for f in ajeno["por_sucursal"]}


# ══════════════════════════════════════════════════════════════════════
#  3. Con un solo local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_con_un_solo_local_la_comparacion_trae_una_fila(client, db, armar_empresa):
    """El panel no la muestra, pero el dato viene: el día que abra el segundo
    local, la pantalla ya sabe qué hacer sin migrar nada."""
    a = armar_empresa()
    db.commit()
    _cobrar(client, a, a.lucas, 9000, 3)

    datos = _stats(client, a)
    assert len(datos["por_sucursal"]) == 1
    assert datos["por_sucursal"][0]["total"] == 9000
    assert datos["por_sucursal"][0]["pct"] == 100.0
    assert datos["facturado_real"] == 9000


def test_el_filtro_por_profesional_sigue_andando(client, db, dos_locales):
    """No se rompió lo que ya había."""
    a = dos_locales
    _cobrar(client, a, a.lucas, 7000, 3)
    _cobrar(client, a, a.pablo, 2000, 4)

    solo_lucas = _stats(client, a, recurso_id=a.lucas.id)
    assert solo_lucas["facturado_real"] == 7000
