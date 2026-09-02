"""Multisucursal, paso 5: la caja es de cada local.

El paso más delicado de los ocho: toca dinero y arqueos ya firmados.

Hasta acá había UNA caja abierta por empresa. Con varios locales tiene que
haber una por local — la plata del centro y la del barrio no se cuentan juntas,
y cada encargado firma lo suyo.

TODA la plata tiene que caer en el local correcto: los turnos, las gift cards,
los abonos, las señas de Mercado Pago y los gastos. Si una sola de esas vías se
escapa, el arqueo de un local cierra con diferencia y no hay forma de saber por
qué.

De dónde sale el local en cada caso:
  · turno y seña → del TURNO (la plata entra donde se atendió, aunque la cobre
    el dueño parado en otro local)
  · gift card, abono y gasto → del USUARIO que los carga (no tienen turno del
    cual heredarlo)
"""

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import planes
from app.core.crypto import hash_clave
from app.models import (
    Caja,
    HorarioRecurso,
    MovimientoFinanciero,
    Pago,
    Recurso,
    ServicioSucursal,
    Sucursal,
    Usuario,
)
from app.models.enums import EstadoCaja, RolUsuario, TipoRecurso
from app.services import finanzas as fin

from .conftest import token_de


@pytest.fixture()
def dos_locales(db, armar_empresa):
    """Empresa Multi con un segundo local, su profesional y su recepcionista."""
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

    # Quien atiende el mostrador del Centro.
    recep = Usuario(
        empresa_id=a.empresa.id,
        sucursal_id=centro.id,
        nombre="Recepción Centro",
        email=f"rc-{centro.id}@example.com",
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


def _abrir_caja(client, usuario, saldo=0):
    return client.post(
        "/caja/abrir", headers=token_de(usuario), json={"saldo_inicial": saldo}
    )


def _reservar_y_cobrar(client, ctx, recurso, quien, dias, monto):
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
    cobro = client.post(
        f"/turnos/{turno.json()['id']}/cobro",
        headers=token_de(quien),
        json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": monto}]},
    )
    return turno.json(), cobro


# ══════════════════════════════════════════════════════════════════════
#  1. Una caja abierta POR LOCAL
# ══════════════════════════════════════════════════════════════════════

def test_cada_local_abre_su_propia_caja(client, db, dos_locales):
    a = dos_locales
    assert _abrir_caja(client, a.dueno, 1000).status_code == 201
    # El dueño es de la sede; la recepcionista del Centro abre la suya.
    segunda = _abrir_caja(client, a.recep_centro, 500)
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["sucursal_id"] == a.centro.id


def test_no_se_puede_abrir_dos_veces_la_caja_del_mismo_local(client, dos_locales):
    a = dos_locales
    assert _abrir_caja(client, a.dueno).status_code == 201
    assert _abrir_caja(client, a.dueno).status_code == 409


def test_la_base_impide_dos_cajas_abiertas_en_un_local(db, dos_locales):
    """El chequeo en Python es un SELECT seguido de un INSERT: dos pestañas al
    mismo tiempo pasaban las dos y el día quedaba repartido entre dos cajas."""
    a = dos_locales
    db.add(Caja(empresa_id=a.empresa.id, sucursal_id=a.sede.id, saldo_inicial=0))
    db.flush()
    db.add(Caja(empresa_id=a.empresa.id, sucursal_id=a.sede.id, saldo_inicial=0))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_cada_uno_cierra_la_suya(client, db, dos_locales):
    """Sin esto, el del centro cerraría la del barrio con la plata que él
    contó, y el arqueo del otro local quedaría firmado por quien no estuvo."""
    a = dos_locales
    _abrir_caja(client, a.dueno, 100)
    _abrir_caja(client, a.recep_centro, 200)

    r = client.post(
        "/caja/cerrar",
        headers=token_de(a.recep_centro),
        json={"saldo_real": 200},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    abiertas = {
        c.sucursal_id
        for c in db.query(Caja).filter(
            Caja.empresa_id == a.empresa.id, Caja.estado == EstadoCaja.ABIERTA
        )
    }
    assert abiertas == {a.sede.id}, "Se cerró la caja equivocada."


# ══════════════════════════════════════════════════════════════════════
#  2. TODA la plata cae en el local correcto
# ══════════════════════════════════════════════════════════════════════

def test_el_cobro_de_un_turno_entra_en_el_local_donde_se_atendio(
    client, db, dos_locales
):
    """Lo cobra el DUEÑO, que es de la sede, pero atendió Sofía en el Centro."""
    a = dos_locales
    _abrir_caja(client, a.dueno)
    _abrir_caja(client, a.recep_centro)

    _turno, cobro = _reservar_y_cobrar(client, a, a.sofia, a.dueno, 3, 5000)
    assert cobro.status_code == 201, cobro.text

    caja_centro = fin.caja_abierta(db, a.empresa.id, a.centro.id)
    mov = db.query(MovimientoFinanciero).filter(
        MovimientoFinanciero.caja_id == caja_centro.id
    ).one()
    assert float(mov.monto) == 5000
    assert mov.sucursal_id == a.centro.id

    caja_sede = fin.caja_abierta(db, a.empresa.id, a.sede.id)
    assert (
        db.query(MovimientoFinanciero)
        .filter(MovimientoFinanciero.caja_id == caja_sede.id)
        .count()
        == 0
    ), "La plata del Centro entró en la caja de la sede."


def test_la_gift_card_entra_en_la_caja_de_quien_la_vende(client, db, dos_locales):
    a = dos_locales
    _abrir_caja(client, a.dueno)
    _abrir_caja(client, a.recep_centro)

    r = client.post(
        "/gift-cards",
        headers=token_de(a.recep_centro),
        json={"monto": 20000, "beneficiario": "Ana", "metodo_pago_id": a.metodo.id},
    )
    assert r.status_code == 201, r.text

    caja_centro = fin.caja_abierta(db, a.empresa.id, a.centro.id)
    mov = db.query(MovimientoFinanciero).filter(
        MovimientoFinanciero.caja_id == caja_centro.id
    ).one()
    assert float(mov.monto) == 20000
    pago = db.query(Pago).filter(Pago.movimiento_id == mov.id).one()
    assert pago.sucursal_id == a.centro.id, (
        "Estadísticas lee de pago: sin el local ahí, esa venta no aparece en "
        "la facturación de ningún local."
    )


def test_el_gasto_sale_de_la_caja_de_quien_lo_carga(client, db, dos_locales):
    a = dos_locales
    _abrir_caja(client, a.dueno)
    _abrir_caja(client, a.recep_centro)

    r = client.post(
        "/gastos",
        headers=token_de(a.recep_centro),
        json={"concepto": "Café", "monto": 3000},
    )
    assert r.status_code == 201, r.text
    assert r.json()["sucursal_id"] == a.centro.id

    caja_centro = fin.caja_abierta(db, a.empresa.id, a.centro.id)
    mov = db.query(MovimientoFinanciero).filter(
        MovimientoFinanciero.caja_id == caja_centro.id
    ).one()
    assert float(mov.monto) == 3000


def test_el_abono_entra_en_la_caja_de_quien_lo_vende(client, db, dos_locales):
    from app.models import PlanAbono

    a = dos_locales
    plan = PlanAbono(empresa_id=a.empresa.id, nombre="Mensual", precio=15000)
    db.add(plan)
    db.flush()
    db.commit()

    _abrir_caja(client, a.dueno)
    _abrir_caja(client, a.recep_centro)

    r = client.post(
        "/membresias",
        headers=token_de(a.recep_centro),
        json={
            "cliente_id": a.cliente.id,
            "plan_id": plan.id,
            "metodo_pago_id": a.metodo.id,
            "fecha_desde": str(dt.date.today()),
            "fecha_hasta": str(dt.date.today() + dt.timedelta(days=30)),
        },
    )
    assert r.status_code in (200, 201), r.text

    caja_centro = fin.caja_abierta(db, a.empresa.id, a.centro.id)
    movs = (
        db.query(MovimientoFinanciero)
        .filter(MovimientoFinanciero.caja_id == caja_centro.id)
        .all()
    )
    assert len(movs) == 1 and float(movs[0].monto) == 15000


# ══════════════════════════════════════════════════════════════════════
#  3. El arqueo de cada local cuenta solo lo suyo
# ══════════════════════════════════════════════════════════════════════

def test_el_arqueo_de_un_local_no_cuenta_la_plata_del_otro(client, db, dos_locales):
    """Es la prueba que importa: si esto falla, un encargado firma un arqueo
    con la plata de un local en el que no estuvo."""
    a = dos_locales
    _abrir_caja(client, a.dueno, 0)
    _abrir_caja(client, a.recep_centro, 0)

    _reservar_y_cobrar(client, a, a.lucas, a.dueno, 3, 7000)   # sede
    _reservar_y_cobrar(client, a, a.sofia, a.dueno, 4, 5000)   # centro
    client.post(
        "/gastos",
        headers=token_de(a.recep_centro),
        json={"concepto": "Café", "monto": 1000},
    )

    sede = client.get(
        f"/caja/actual?sucursal_id={a.sede.id}", headers=token_de(a.dueno)
    ).json()
    centro = client.get(
        f"/caja/actual?sucursal_id={a.centro.id}", headers=token_de(a.dueno)
    ).json()

    assert float(sede["total_ingresos"]) == 7000
    assert float(sede["total_egresos"]) == 0
    assert float(centro["total_ingresos"]) == 5000
    assert float(centro["total_egresos"]) == 1000


def test_la_caja_actual_sin_pedir_local_es_la_de_quien_pregunta(client, dos_locales):
    """La recepcionista del centro abre Caja y ve la suya, sin elegir nada."""
    a = dos_locales
    _abrir_caja(client, a.dueno, 111)
    _abrir_caja(client, a.recep_centro, 222)

    mia = client.get("/caja/actual", headers=token_de(a.recep_centro)).json()
    assert float(mia["caja"]["saldo_inicial"]) == 222


def test_los_movimientos_se_pueden_filtrar_por_local(client, db, dos_locales):
    a = dos_locales
    _abrir_caja(client, a.dueno)
    _abrir_caja(client, a.recep_centro)
    _reservar_y_cobrar(client, a, a.lucas, a.dueno, 3, 7000)
    _reservar_y_cobrar(client, a, a.sofia, a.dueno, 4, 5000)

    r = client.get(
        f"/movimientos?sucursal_id={a.centro.id}", headers=token_de(a.dueno)
    ).json()
    assert r["total"] == 1
    assert float(r["items"][0]["monto"]) == 5000


# ══════════════════════════════════════════════════════════════════════
#  4. Con un solo local, nada cambió
# ══════════════════════════════════════════════════════════════════════

def test_con_un_solo_local_la_caja_funciona_igual_que_siempre(
    client, db, armar_empresa
):
    a = armar_empresa()
    db.commit()

    assert _abrir_caja(client, a.dueno, 500).status_code == 201
    assert _abrir_caja(client, a.dueno).status_code == 409

    _reservar_y_cobrar(client, a, a.lucas, a.dueno, 3, 9000)
    actual = client.get("/caja/actual", headers=token_de(a.dueno)).json()
    assert float(actual["total_ingresos"]) == 9000
    assert float(actual["caja"]["saldo_inicial"]) == 500

    cierre = client.post(
        "/caja/cerrar", headers=token_de(a.dueno), json={"saldo_real": 9500}
    )
    assert cierre.status_code == 200, cierre.text
    assert float(cierre.json()["diferencia"]) == 0
