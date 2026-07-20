"""Estadísticas de facturación: el filtro por profesional y sus candados.

El primer test es la REGRESIÓN del bug del 19/07/2026: el panel mandaba
recurso_id, el service lo soportaba, pero el router no lo declaraba y FastAPI
lo descartaba en silencio. Las tarjetas mostraban el total del negocio con el
filtro puesto. Si alguien vuelve a borrar el parámetro del router, este test
lo agarra.
"""

import datetime as dt

from tests.conftest import cargar_pagos, token_de

RUTA = "/estadisticas/facturacion"


def _rango(base: dt.datetime) -> dict:
    return {
        "desde": (base - dt.timedelta(days=1)).isoformat(),
        "hasta": (base + dt.timedelta(days=1)).isoformat(),
    }


def test_filtro_por_profesional_aplica_en_todo_el_panel(client, db, armar_empresa):
    """Con recurso_id, tarjetas, por_método y por_profesional se filtran de verdad."""
    ctx = armar_empresa()
    base = dt.datetime.now(dt.timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    # Los números de las capturas del bug: 10×14.960 (Lucas) + 2×13.500 (Pablo).
    cargar_pagos(db, ctx, ctx.lucas, 10, 14960, base)
    cargar_pagos(db, ctx, ctx.pablo, 2, 13500, base + dt.timedelta(hours=8))
    headers = token_de(ctx.dueno)

    sin_filtro = client.get(RUTA, params=_rango(base), headers=headers).json()
    assert sin_filtro["facturado_real"] == 176600
    assert sin_filtro["cantidad_pagos"] == 12
    assert {p["recurso"] for p in sin_filtro["por_profesional"]} == {
        "Lucas Estrella",
        "Pablo Vega",
    }

    lucas = client.get(
        RUTA, params={**_rango(base), "recurso_id": ctx.lucas.id}, headers=headers
    ).json()
    assert lucas["facturado_real"] == 149600
    assert lucas["cantidad_pagos"] == 10
    assert lucas["ticket_promedio"] == 14960
    assert [p["recurso"] for p in lucas["por_profesional"]] == ["Lucas Estrella"]
    # El desglose por método también queda filtrado (suma lo de Lucas, no el total).
    assert sum(m["total"] for m in lucas["por_metodo"]) == 149600

    pablo = client.get(
        RUTA, params={**_rango(base), "recurso_id": ctx.pablo.id}, headers=headers
    ).json()
    assert pablo["facturado_real"] == 27000
    assert pablo["cantidad_pagos"] == 2


def test_recurso_de_otra_empresa_devuelve_vacio(client, db, armar_empresa):
    """Tenancy del filtro: un recurso_id ajeno no filtra 'raro', devuelve cero.

    El service cruza siempre por empresa_id, así que pedir las estadísticas con
    el id de un barbero de OTRO negocio no puede traer datos de nadie.
    """
    ctx_a = armar_empresa("Empresa A")
    ctx_b = armar_empresa("Empresa B")
    base = dt.datetime.now(dt.timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    cargar_pagos(db, ctx_a, ctx_a.lucas, 3, 10000, base)
    cargar_pagos(db, ctx_b, ctx_b.lucas, 5, 9000, base)

    r = client.get(
        RUTA,
        params={**_rango(base), "recurso_id": ctx_b.lucas.id},
        headers=token_de(ctx_a.dueno),
    ).json()
    assert r["facturado_real"] == 0
    assert r["cantidad_pagos"] == 0
    assert r["por_profesional"] == []


def test_estadisticas_son_dueno_only(client, armar_empresa):
    """Finanzas sensibles: el profesional no las ve, y sin token tampoco."""
    ctx = armar_empresa()
    base = dt.datetime.now(dt.timezone.utc)

    como_profesional = client.get(
        RUTA, params=_rango(base), headers=token_de(ctx.profesional)
    )
    assert como_profesional.status_code == 403

    sin_token = client.get(RUTA, params=_rango(base))
    assert sin_token.status_code == 401
