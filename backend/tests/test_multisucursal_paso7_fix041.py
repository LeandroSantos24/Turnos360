"""Multisucursal, paso 7: el cliente elige a qué local va.

Es el único paso de la fase que ve el cliente final, y el que tiene la falla
más cara de todas: reservar creyendo que vas a una dirección y que te atiendan
en la otra. Nadie vuelve después de eso.

Por eso, con dos locales abiertos, reservar SIN elegir local es un 400 y no un
default silencioso. "Sin preferencia" puede elegir profesional, nunca local.

Y como siempre: para un negocio de un solo local, el wizard no muestra el paso
y la reserva funciona exactamente igual que antes.
"""

import datetime as dt

import pytest

from app.core import planes
from app.models import HorarioRecurso, Recurso, ServicioSucursal, Sucursal, Turno
from app.models.enums import TipoRecurso


@pytest.fixture()
def negocio(db, armar_empresa):
    """Empresa Multi: la sede con Lucas y Pablo, el Centro con Sofía."""
    a = armar_empresa()
    a.empresa.activa = True
    a.empresa.plan = planes.Plan.MULTI.value
    a.empresa.limite_sucursales = 5
    a.sede.direccion = "El Trapiche 2961"
    centro = Sucursal(
        empresa_id=a.empresa.id,
        nombre="Centro",
        direccion="Belgrano 48",
        activa=True,
    )
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
            empresa_id=a.empresa.id,
            servicio_id=a.servicio.id,
            sucursal_id=centro.id,
            precio=6500,  # más barato que en el centro histórico
        )
    )
    a.centro = centro
    a.sofia = sofia
    db.commit()
    return a


def _cuando():
    base = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)
    return base.replace(hour=10, minute=0, second=0, microsecond=0)


def _reservar(client, ctx, **extra):
    return client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json={
            "servicio_id": ctx.servicio.id,
            "inicio": _cuando().isoformat(),
            "cliente": {
                "nombre": "Ana Cliente",
                "telefono": "2611234567",
                "email": "ana@example.com",
            },
            **extra,
        },
    )


# ══════════════════════════════════════════════════════════════════════
#  1. La vidriera ofrece los locales
# ══════════════════════════════════════════════════════════════════════

def test_la_vidriera_lista_los_locales_con_su_direccion(client, negocio):
    a = negocio
    r = client.get(f"/publico/{a.empresa.slug}")
    assert r.status_code == 200, r.text
    locales = {s["nombre"]: s for s in r.json()["sucursales"]}
    assert set(locales) == {a.empresa.nombre, "Centro"}
    assert locales["Centro"]["direccion"] == "Belgrano 48", (
        "Con varios locales, la dirección que importa es la del local: es a "
        "dónde tiene que ir el cliente."
    )


def test_el_local_cerrado_no_se_ofrece(client, db, negocio):
    a = negocio
    a.centro.activa = False
    db.commit()
    r = client.get(f"/publico/{a.empresa.slug}")
    assert [s["nombre"] for s in r.json()["sucursales"]] == [a.empresa.nombre]


def test_elegir_un_local_acota_el_equipo(client, negocio):
    a = negocio
    r = client.get(f"/publico/{a.empresa.slug}?sucursal_id={a.centro.id}")
    assert [x["nombre"] for x in r.json()["recursos"]] == ["Sofía"]


def test_elegir_un_local_muestra_el_precio_de_ese_local(client, negocio):
    a = negocio
    general = client.get(f"/publico/{a.empresa.slug}").json()["servicios"][0]
    delCentro = client.get(
        f"/publico/{a.empresa.slug}?sucursal_id={a.centro.id}"
    ).json()["servicios"][0]

    assert general["precio"] == 10000
    assert delCentro["precio"] == 6500


def test_un_local_de_otro_negocio_no_existe(client, db, negocio, armar_empresa):
    a = negocio
    b = armar_empresa()
    db.commit()
    r = client.get(f"/publico/{a.empresa.slug}?sucursal_id={b.sede.id}")
    assert r.status_code == 404, r.text


# ══════════════════════════════════════════════════════════════════════
#  2. Los horarios son los de ese local
# ══════════════════════════════════════════════════════════════════════

def test_los_horarios_exigen_elegir_local(client, negocio):
    """Sin esto, "cualquiera" mezclaría los huecos de los dos locales."""
    a = negocio
    r = client.get(
        f"/publico/{a.empresa.slug}/horarios", params={"servicio_id": a.servicio.id}
    )
    assert r.status_code == 400, r.text
    assert "Elegí en qué local" in r.json()["detail"]


def test_con_el_local_elegido_los_horarios_salen(client, negocio):
    a = negocio
    r = client.get(
        f"/publico/{a.empresa.slug}/horarios",
        params={"servicio_id": a.servicio.id, "sucursal_id": a.centro.id},
    )
    assert r.status_code == 200, r.text
    assert r.json(), "El Centro tiene a Sofía con horario 0-24."


def test_un_servicio_que_no_se_presta_ahi_no_tiene_horarios(client, db, negocio):
    a = negocio
    db.query(ServicioSucursal).filter(
        ServicioSucursal.servicio_id == a.servicio.id,
        ServicioSucursal.sucursal_id == a.centro.id,
    ).delete()
    db.commit()

    r = client.get(
        f"/publico/{a.empresa.slug}/horarios",
        params={"servicio_id": a.servicio.id, "sucursal_id": a.centro.id},
    )
    assert r.status_code == 200, r.text
    assert r.json() == []


# ══════════════════════════════════════════════════════════════════════
#  3. La reserva: la falla más cara de todas
# ══════════════════════════════════════════════════════════════════════

def test_reservar_sin_elegir_local_no_se_permite(client, negocio):
    """Reservar creyendo que vas a una dirección y que te atiendan en la otra
    es de lo peor que le puede pasar a un cliente. Mejor un error claro."""
    r = _reservar(client, negocio)
    assert r.status_code == 400, r.text
    assert "Elegí en qué local" in r.json()["detail"]


def test_reservar_en_un_local_asigna_a_alguien_de_ese_local(client, db, negocio):
    a = negocio
    r = _reservar(client, a, sucursal_id=a.centro.id)
    assert r.status_code in (200, 201), r.text

    turno = db.get(Turno, r.json()["turno_id"] if "turno_id" in r.json() else r.json()["id"])
    assert turno.recurso_id == a.sofia.id
    assert turno.sucursal_id == a.centro.id


def test_pedir_un_profesional_de_otro_local_no_cuela(client, negocio):
    a = negocio
    r = _reservar(client, a, sucursal_id=a.centro.id, recurso_id=a.lucas.id)
    assert r.status_code == 400, r.text


def test_un_servicio_que_no_se_presta_en_ese_local_se_rechaza(client, db, negocio):
    a = negocio
    db.query(ServicioSucursal).filter(
        ServicioSucursal.servicio_id == a.servicio.id,
        ServicioSucursal.sucursal_id == a.centro.id,
    ).delete()
    db.commit()

    r = _reservar(client, a, sucursal_id=a.centro.id)
    assert r.status_code == 409, r.text
    assert "no se ofrece en el local" in r.json()["detail"]


# ══════════════════════════════════════════════════════════════════════
#  4. Con un solo local, el cliente no elige nada
# ══════════════════════════════════════════════════════════════════════

def test_con_un_solo_local_la_reserva_funciona_como_siempre(
    client, db, armar_empresa
):
    a = armar_empresa()
    a.empresa.activa = True
    db.commit()

    horarios = client.get(
        f"/publico/{a.empresa.slug}/horarios", params={"servicio_id": a.servicio.id}
    )
    assert horarios.status_code == 200, horarios.text

    r = _reservar(client, a)
    assert r.status_code in (200, 201), r.text


def test_con_un_solo_local_la_vidriera_igual_lo_informa(client, db, armar_empresa):
    """La lista viene siempre; el wizard decide no mostrar el paso."""
    a = armar_empresa()
    a.empresa.activa = True
    db.commit()
    r = client.get(f"/publico/{a.empresa.slug}")
    assert len(r.json()["sucursales"]) == 1
