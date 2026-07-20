"""Aislamiento multi-tenant (Regla 1 de la arquitectura).

La promesa central del SaaS: dos negocios en la misma base y ninguno puede ver
un solo dato del otro, ni listando, ni pidiendo por id, ni en los agregados.
"""

import datetime as dt

from tests.conftest import cargar_pagos, token_de
from app.models.enums import EstadoTurno
from app.models.turno import Turno


def test_listado_de_clientes_no_mezcla_empresas(client, armar_empresa):
    ctx_a = armar_empresa("Empresa A")
    ctx_b = armar_empresa("Empresa B")

    r = client.get("/clientes", headers=token_de(ctx_a.dueno))
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()["items"]}
    assert ctx_a.cliente.id in ids
    assert ctx_b.cliente.id not in ids


def test_cliente_ajeno_por_id_es_404(client, armar_empresa):
    """Pedir por id un cliente de otra empresa no da 403 ('existe pero no es
    tuyo'): da 404, como si no existiera. No filtramos ni la existencia."""
    ctx_a = armar_empresa()
    ctx_b = armar_empresa()

    r = client.get(f"/clientes/{ctx_b.cliente.id}", headers=token_de(ctx_a.dueno))
    assert r.status_code == 404


def test_turno_ajeno_por_id_es_404(client, db, armar_empresa):
    ctx_a = armar_empresa()
    ctx_b = armar_empresa()
    inicio = dt.datetime.now(dt.timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    turno_b = Turno(
        empresa_id=ctx_b.empresa.id,
        cliente_id=ctx_b.cliente.id,
        servicio_id=ctx_b.servicio.id,
        recurso_id=ctx_b.lucas.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=EstadoTurno.PENDIENTE,
    )
    db.add(turno_b)
    db.flush()

    r = client.get(f"/turnos/{turno_b.id}", headers=token_de(ctx_a.dueno))
    assert r.status_code == 404


def test_estadisticas_no_suman_pagos_ajenos(client, db, armar_empresa):
    """El agregado financiero de A no puede incluir un peso de B."""
    ctx_a = armar_empresa()
    ctx_b = armar_empresa()
    base = dt.datetime.now(dt.timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    cargar_pagos(db, ctx_a, ctx_a.lucas, 2, 5000, base)
    cargar_pagos(db, ctx_b, ctx_b.lucas, 4, 7777, base)

    r = client.get(
        "/estadisticas/facturacion",
        params={
            "desde": (base - dt.timedelta(days=1)).isoformat(),
            "hasta": (base + dt.timedelta(days=1)).isoformat(),
        },
        headers=token_de(ctx_a.dueno),
    ).json()
    assert r["facturado_real"] == 10000  # solo lo de A
    assert r["cantidad_pagos"] == 2
