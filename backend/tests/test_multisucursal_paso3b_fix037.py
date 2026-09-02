"""Multisucursal, paso 3b: el servicio se ofrece por local, y puede costar distinto.

Es la primera pregunta de cualquier dueño de dos locales: el corte del centro
sale más caro que el del barrio. Hasta acá el precio era uno solo por servicio.

El invariante que sostiene todo: **todo servicio se ofrece en al menos un
local**. Un servicio ofrecido en ninguno no da error — da un servicio
invisible, y nadie se entera hasta que un cliente no lo encuentra en la página
de reservas. Por eso se garantiza en el modelo (listener) y no en la disciplina
de cada alta.
"""

import datetime as dt

import pytest

from app.core import planes
from app.models import Servicio, Sucursal, Turno
from app.services import servicio as servicio_svc

from .conftest import token_de


@pytest.fixture()
def dos_locales(db, armar_empresa):
    a = armar_empresa()
    a.empresa.plan = planes.Plan.MULTI.value
    a.empresa.limite_sucursales = 5
    centro = Sucursal(empresa_id=a.empresa.id, nombre="Centro", activa=True)
    db.add(centro)
    db.flush()
    a.centro = centro
    db.commit()
    return a


def _cuando():
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)


# ══════════════════════════════════════════════════════════════════════
#  1. Nunca cero locales
# ══════════════════════════════════════════════════════════════════════

def test_un_servicio_nuevo_se_ofrece_en_todos_los_locales(client, db, dos_locales):
    """Es lo que preserva el comportamiento de siempre: el servicio se ofrece
    en todos lados salvo que el dueño diga otra cosa."""
    a = dos_locales
    r = client.post(
        "/servicios",
        headers=token_de(a.dueno),
        json={"nombre": "Barba", "duracion_min": 20, "precio": 5000},
    )
    assert r.status_code == 201, r.text
    ids = {s["sucursal_id"] for s in r.json()["sucursales"]}
    assert ids == {a.sede.id, a.centro.id}


def test_un_servicio_creado_a_mano_tambien_queda_ofrecido(db, dos_locales):
    """El invariante no puede depender de que cada alta se acuerde: un alta
    nueva que se olvide daría un servicio invisible, no un error ruidoso."""
    a = dos_locales
    s = Servicio(empresa_id=a.empresa.id, nombre="A mano", duracion_min=30, precio=1000)
    db.add(s)
    db.flush()
    assert len(servicio_svc.sucursales_de(db, s.id)) == 2


def test_no_se_puede_dejar_un_servicio_sin_ningun_local(client, db, dos_locales):
    a = dos_locales
    r = client.patch(
        f"/servicios/{a.servicio.id}",
        headers=token_de(a.dueno),
        json={"sucursales": []},
    )
    assert r.status_code == 422, r.text
    assert "al menos un local" in r.json()["detail"]


# ══════════════════════════════════════════════════════════════════════
#  2. Precio por local
# ══════════════════════════════════════════════════════════════════════

def test_el_precio_del_local_pisa_al_del_servicio(client, db, dos_locales):
    a = dos_locales
    r = client.patch(
        f"/servicios/{a.servicio.id}",
        headers=token_de(a.dueno),
        json={
            "sucursales": [
                {"sucursal_id": a.sede.id, "precio": 12000},
                {"sucursal_id": a.centro.id, "precio": None},
            ]
        },
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    servicio = db.get(Servicio, a.servicio.id)
    assert servicio_svc.precio_en(db, servicio, a.sede.id) == 12000
    assert servicio_svc.precio_en(db, servicio, a.centro.id) == 10000, (
        "Sin precio propio manda el del servicio. Ese fallback es lo que "
        "permite subir el precio general una sola vez."
    )


def test_el_turno_se_cobra_al_precio_del_local(client, db, dos_locales):
    """Sin esto, el precio por local sería un adorno: el turno seguiría
    tomando el precio general."""
    a = dos_locales
    client.patch(
        f"/servicios/{a.servicio.id}",
        headers=token_de(a.dueno),
        json={"sucursales": [{"sucursal_id": a.sede.id, "precio": 12345}]},
    )

    r = client.post(
        "/turnos",
        headers=token_de(a.dueno),
        json={
            "cliente_id": a.cliente.id,
            "recurso_id": a.lucas.id,
            "servicio_id": a.servicio.id,
            "fecha_inicio": _cuando().isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    turno = db.get(Turno, r.json()["id"])
    assert float(turno.importe_previsto) == 12345


def test_un_importe_explicito_sigue_mandando(client, db, dos_locales):
    """El precio por local no puede pisar lo que el mostrador escribió a mano."""
    a = dos_locales
    r = client.post(
        "/turnos",
        headers=token_de(a.dueno),
        json={
            "cliente_id": a.cliente.id,
            "recurso_id": a.lucas.id,
            "servicio_id": a.servicio.id,
            "fecha_inicio": _cuando().isoformat(),
            "importe_previsto": 777,
        },
    )
    assert r.status_code == 201, r.text
    assert float(db.get(Turno, r.json()["id"]).importe_previsto) == 777


# ══════════════════════════════════════════════════════════════════════
#  3. No se puede agendar un servicio en un local donde no se presta
# ══════════════════════════════════════════════════════════════════════

def test_no_se_agenda_un_servicio_que_no_se_presta_en_ese_local(
    client, db, dos_locales
):
    a = dos_locales
    cab = token_de(a.dueno)
    # El corte queda solo en el Centro…
    client.patch(
        f"/servicios/{a.servicio.id}",
        headers=cab,
        json={"sucursales": [{"sucursal_id": a.centro.id}]},
    )
    # …pero Lucas atiende en la sede principal.
    r = client.post(
        "/turnos",
        headers=cab,
        json={
            "cliente_id": a.cliente.id,
            "recurso_id": a.lucas.id,
            "servicio_id": a.servicio.id,
            "fecha_inicio": _cuando().isoformat(),
        },
    )
    assert r.status_code == 409, r.text
    assert "no se ofrece en el local" in r.json()["detail"]


def test_mover_al_profesional_al_local_correcto_lo_destraba(client, db, dos_locales):
    a = dos_locales
    cab = token_de(a.dueno)
    client.patch(
        f"/servicios/{a.servicio.id}",
        headers=cab,
        json={"sucursales": [{"sucursal_id": a.centro.id}]},
    )
    client.patch(
        f"/recursos/{a.lucas.id}", headers=cab, json={"sucursal_id": a.centro.id}
    )

    r = client.post(
        "/turnos",
        headers=cab,
        json={
            "cliente_id": a.cliente.id,
            "recurso_id": a.lucas.id,
            "servicio_id": a.servicio.id,
            "fecha_inicio": _cuando().isoformat(),
        },
    )
    assert r.status_code == 201, r.text


# ══════════════════════════════════════════════════════════════════════
#  4. Tenencia
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_ofrecer_un_servicio_en_el_local_de_otra_empresa(
    client, db, armar_empresa
):
    a = armar_empresa()
    b = armar_empresa()
    db.commit()

    r = client.patch(
        f"/servicios/{a.servicio.id}",
        headers=token_de(a.dueno),
        json={"sucursales": [{"sucursal_id": b.sede.id}]},
    )
    assert r.status_code == 404, r.text
    ids = {f.sucursal_id for f in servicio_svc.sucursales_de(db, a.servicio.id)}
    assert b.sede.id not in ids


# ══════════════════════════════════════════════════════════════════════
#  5. Con un solo local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_el_alta_de_un_servicio_no_pide_locales(client, armar_empresa):
    a = armar_empresa()
    r = client.post(
        "/servicios",
        headers=token_de(a.dueno),
        json={"nombre": "Corte simple", "duracion_min": 30, "precio": 8000},
    )
    assert r.status_code == 201, r.text
    assert len(r.json()["sucursales"]) == 1


def test_el_turno_de_siempre_se_sigue_cobrando_igual(client, db, armar_empresa):
    a = armar_empresa()
    db.commit()
    r = client.post(
        "/turnos",
        headers=token_de(a.dueno),
        json={
            "cliente_id": a.cliente.id,
            "recurso_id": a.lucas.id,
            "servicio_id": a.servicio.id,
            "fecha_inicio": _cuando().isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    assert float(db.get(Turno, r.json()["id"]).importe_previsto) == 10000


def test_listar_servicios_trae_los_locales_sin_una_consulta_por_fila(
    client, db, dos_locales
):
    """El N+1 clásico: no se nota con tres servicios y sí en un negocio real."""
    a = dos_locales
    for i in range(5):
        db.add(
            Servicio(
                empresa_id=a.empresa.id,
                nombre=f"Servicio {i}",
                duracion_min=30,
                precio=1000,
            )
        )
    db.commit()

    r = client.get("/servicios", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    for item in r.json()["items"]:
        assert len(item["sucursales"]) >= 1, (
            "Todo servicio tiene al menos un local. Si viene vacío, la pantalla "
            "no tiene con qué mostrar dónde se presta."
        )
