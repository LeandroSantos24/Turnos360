"""Multisucursal, paso 4: la agenda se mira por local.

Con dos sucursales y cinco barberos en cada una, abrir la agenda con diez
columnas mezcladas no le sirve a nadie: los turnos del centro y los del barrio
no comparten ni sala ni caja.

Lo que se prueba acá es el filtro del backend. Que el turno guarde su propio
`sucursal_id` (paso 1) es lo que lo hace barato: se filtra por columna, sin
joinear con recurso, y un turno viejo sigue contando en el local donde ocurrió
aunque el profesional se haya mudado después.
"""

import datetime as dt

import pytest

from app.core import planes
from app.models import HorarioRecurso, Recurso, ServicioSucursal, Sucursal
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
    # Horario 0-24 los siete días, como los del fixture base.
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
    # El servicio nació ofrecido solo en la sede (Centro no existía todavía).
    # Se lo suma acá: sin esto el turno de Sofía da 409, que es exactamente el
    # candado del paso 3b haciendo su trabajo.
    db.add(
        ServicioSucursal(
            empresa_id=a.empresa.id, servicio_id=a.servicio.id, sucursal_id=centro.id
        )
    )
    a.centro = centro
    a.sofia = sofia
    db.commit()
    return a


# ══════════════════════════════════════════════════════════════════════
#  1. Recursos por local
# ══════════════════════════════════════════════════════════════════════

def test_los_recursos_se_pueden_pedir_por_local(client, dos_locales):
    a = dos_locales
    cab = token_de(a.dueno)

    todos = client.get("/recursos", headers=cab).json()
    assert {r["nombre"] for r in todos["items"]} >= {
        "Lucas Estrella",
        "Pablo Vega",
        "Sofía",
    }

    delCentro = client.get(f"/recursos?sucursal_id={a.centro.id}", headers=cab).json()
    assert [r["nombre"] for r in delCentro["items"]] == ["Sofía"]
    assert delCentro["total"] == 1, "El total también tiene que respetar el filtro."


def test_un_local_ajeno_no_devuelve_nada(client, db, armar_empresa):
    """No es un 404 ni un error: simplemente no hay recursos de esta empresa
    en un local que no es suyo. Lo importante es que no se filtre nada."""
    a = armar_empresa()
    b = armar_empresa()
    db.commit()

    r = client.get(f"/recursos?sucursal_id={b.sede.id}", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


# ══════════════════════════════════════════════════════════════════════
#  2. Turnos por local
# ══════════════════════════════════════════════════════════════════════

def _reservar(client, ctx, recurso, dias):
    cuando = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=dias)
    return client.post(
        "/turnos",
        headers=token_de(ctx.dueno),
        json={
            "cliente_id": ctx.cliente.id,
            "recurso_id": recurso.id,
            "servicio_id": ctx.servicio.id,
            "fecha_inicio": cuando.isoformat(),
        },
    )


def test_la_agenda_se_filtra_por_local(client, db, dos_locales):
    a = dos_locales
    # Sofía tiene que poder prestar el servicio: se la suma al servicio.
    a.servicio.recursos.append(a.sofia)
    db.commit()

    assert _reservar(client, a, a.lucas, 3).status_code == 201
    assert _reservar(client, a, a.sofia, 4).status_code == 201

    cab = token_de(a.dueno)
    todos = client.get("/turnos", headers=cab).json()
    assert todos["total"] >= 2

    delCentro = client.get(f"/turnos?sucursal_id={a.centro.id}", headers=cab).json()
    assert delCentro["total"] == 1
    assert delCentro["items"][0]["recurso_id"] == a.sofia.id


def test_el_turno_se_queda_en_el_local_donde_ocurrio(client, db, dos_locales):
    """Si el profesional se muda de local el mes que viene, los turnos que ya
    pasaron tienen que seguir contando donde ocurrieron. Por eso el turno
    guarda su propio local en vez de joinear con el del profesional."""
    a = dos_locales
    creado = _reservar(client, a, a.lucas, 3)
    assert creado.status_code == 201

    cab = token_de(a.dueno)
    client.patch(f"/recursos/{a.lucas.id}", headers=cab, json={"sucursal_id": a.centro.id})

    delaSede = client.get(f"/turnos?sucursal_id={a.sede.id}", headers=cab).json()
    assert delaSede["total"] == 1, (
        "El turno se movió de local al mudarse el profesional: la facturación "
        "de la sede quedaría mal."
    )


# ══════════════════════════════════════════════════════════════════════
#  3. El usuario sabe a qué local pertenece
# ══════════════════════════════════════════════════════════════════════

def test_me_dice_a_que_local_pertenece(client, dos_locales):
    """El panel lo usa para abrir la agenda en el local de quien entra."""
    a = dos_locales
    r = client.get("/auth/me", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    assert r.json()["sucursal_id"] == a.sede.id


# ══════════════════════════════════════════════════════════════════════
#  4. Con un solo local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_sin_filtro_la_agenda_trae_todo_como_siempre(client, db, armar_empresa):
    a = armar_empresa()
    db.commit()
    assert _reservar(client, a, a.lucas, 3).status_code == 201

    r = client.get("/turnos", headers=token_de(a.dueno))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1


def test_el_filtro_por_recurso_sigue_funcionando(client, db, dos_locales):
    a = dos_locales
    assert _reservar(client, a, a.lucas, 3).status_code == 201
    assert _reservar(client, a, a.pablo, 4).status_code == 201

    r = client.get(
        f"/turnos?recurso_id={a.lucas.id}", headers=token_de(a.dueno)
    ).json()
    assert r["total"] == 1
    assert r["items"][0]["recurso_id"] == a.lucas.id
