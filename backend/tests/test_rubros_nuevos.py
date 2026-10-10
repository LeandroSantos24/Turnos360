"""Rubros nuevos (peluquería, lavadero, gimnasio, otros) y su presentación.

- Cada rubro del catálogo nace con servicios y terminología completos.
- El alta siembra exactamente los servicios del preset.
- /publico/rubros trae lo que necesita la vista previa del registro y no
  lista rubros inactivos.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Empresa, Rubro
from app.models.agenda import Servicio
from app.presets import PRESET_GIMNASIO, PRESET_LAVADERO, PRESET_OTROS, PRESET_PELUQUERIA
from app.seeds_minimo import RUBROS
from app.services import catalogo_inicial, sucursal as sucursal_svc


@pytest.mark.parametrize("codigo,nombre,preset", RUBROS, ids=[r[0] for r in RUBROS])
def test_cada_rubro_del_catalogo_esta_completo(codigo, nombre, preset):
    term = preset["terminologia"]
    assert term["turno"] and term["recurso"] and term["cliente"]
    assert preset["servicios"], f"{codigo} nacería sin servicios"
    for s in preset["servicios"]:
        assert s["nombre"] and s["duracion_min"] > 0 and s["precio"] >= 0


def test_los_codigos_no_se_repiten():
    codigos = [c for c, _, _ in RUBROS]
    assert len(codigos) == len(set(codigos))
    assert {"peluqueria", "lavadero", "gimnasio", "otros"} <= set(codigos)


@pytest.mark.parametrize(
    "preset", [PRESET_PELUQUERIA, PRESET_LAVADERO, PRESET_GIMNASIO, PRESET_OTROS],
    ids=["peluqueria", "lavadero", "gimnasio", "otros"],
)
def test_el_alta_siembra_los_servicios_del_rubro(db, preset):
    s = uuid.uuid4().hex[:8]
    rubro = Rubro(codigo=f"r-{s}", nombre="Rubro", preset=preset)
    db.add(rubro)
    db.flush()
    emp = Empresa(nombre=f"Negocio {s}", slug=f"n-{s}", rubro_id=rubro.id)
    db.add(emp)
    db.flush()
    sucursal_svc.crear_principal(db, emp)
    catalogo_inicial.sembrar(db, emp.id)
    nombres = {
        x.nombre for x in db.scalars(select(Servicio).where(Servicio.empresa_id == emp.id))
    }
    assert nombres == {x["nombre"] for x in preset["servicios"]}


def test_publico_rubros_trae_la_vista_previa_y_oculta_inactivos(client, db):
    s = uuid.uuid4().hex[:8]
    db.add_all([
        Rubro(codigo=f"lav-{s}", nombre=f"Lavadero {s}", preset=PRESET_LAVADERO, activo=True),
        Rubro(codigo=f"off-{s}", nombre=f"Apagado {s}", preset=PRESET_OTROS, activo=False),
    ])
    db.commit()
    r = client.get("/publico/rubros")
    assert r.status_code == 200
    por_codigo = {x["codigo"]: x for x in r.json()}
    assert f"off-{s}" not in por_codigo
    lav = por_codigo[f"lav-{s}"]
    assert lav["recurso"] == "box"
    assert lav["servicios"][0] == "Lavado exterior"
    assert set(lav) == {"codigo", "nombre", "recurso", "cliente", "turno", "servicios"}
