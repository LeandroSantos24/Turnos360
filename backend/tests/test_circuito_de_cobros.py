"""Toda la plata que entra tiene que aparecer en los tres lugares que la miran.

QUÉ VERIFICA ESTE ARCHIVO
─────────────────────────
Turnos360 cobra por cinco caminos distintos —el turno, la seña online, la gift
card, el abono y el gasto— y cada uno está implementado en un módulo diferente.
Los tres lugares donde el dueño mira la plata (la CAJA del día, las
ESTADÍSTICAS y el arqueo POR MÉTODO) leen de tablas distintas: la caja de
`movimiento_financiero`, las estadísticas de `pago`.

Ese cruce es exactamente donde se pierde plata sin que nadie se entere: un
camino que crea el movimiento pero no el pago aparece en la caja y falta en las
estadísticas; uno que olvida `sucursal_id` entra igual pero queda fuera del
arqueo del local; uno que no guarda `metodo_pago_id` no se puede explicar en el
cierre. Ninguno de los tres da un error — dan un número más chico, que es peor,
porque se descubre a fin de mes y ya no se sabe cuál faltó.

Los tests de acá abajo recorren cada camino de punta a punta y verifican que la
misma plata aparece en los tres lados, con su local y con su método.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.models.enums import EstadoTurno, TipoMovimiento
from app.models.finanzas import Caja, MovimientoFinanciero, Pago
from app.schemas.finanzas import CobroCrear, PagoLinea
from app.schemas.giftcard import GiftCardCrear
from app.schemas.membresia import MembresiaCrear
from app.services import estadisticas as svc_estad
from app.services import finanzas as svc_fin
from app.services import giftcard as svc_gift
from app.services import membresia as svc_memb
from app.models.turno import Turno


# ── Andamios ─────────────────────────────────────────────────────────────

@pytest.fixture
def negocio(db, armar_empresa):
    """Una empresa con caja abierta y un turno listo para cobrar."""
    ctx = armar_empresa("Circuito de cobros")
    svc_fin.abrir_caja(
        db, ctx.empresa.id, type("D", (), {"saldo_inicial": 0})(), ctx.dueno.id
    )
    db.flush()
    return ctx


def _turno(db, ctx) -> Turno:
    cuando = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
    t = Turno(
        empresa_id=ctx.empresa.id,
        sucursal_id=ctx.sede.id,
        recurso_id=ctx.lucas.id,
        cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id,
        estado=EstadoTurno.CONFIRMADO,
        fecha_inicio=cuando,
        fecha_fin=cuando + dt.timedelta(minutes=30),
    )
    db.add(t)
    db.flush()
    return t


def _movimientos(db, empresa_id) -> list[MovimientoFinanciero]:
    return list(
        db.scalars(
            select(MovimientoFinanciero).where(
                MovimientoFinanciero.empresa_id == empresa_id,
                MovimientoFinanciero.tipo == TipoMovimiento.INGRESO,
            )
        )
    )


def _pagos(db, empresa_id) -> list[Pago]:
    return list(db.scalars(select(Pago).where(Pago.empresa_id == empresa_id)))


def _facturado(db, ctx) -> float:
    """Lo que muestran las Estadísticas para hoy."""
    hoy = dt.datetime.now(dt.timezone.utc)
    r = svc_estad.facturacion(
        db,
        ctx.empresa.id,
        desde=hoy - dt.timedelta(days=1),
        hasta=hoy + dt.timedelta(days=1),
    )
    return float(r["facturado_real"])


# ── El cobro de un turno ─────────────────────────────────────────────────

def test_cobrar_un_turno_lo_deja_en_caja_y_en_estadisticas(db, negocio):
    """El camino más común. Si este se rompe, no factura nadie."""
    turno = _turno(db, negocio)

    svc_fin.registrar_cobro(
        db,
        negocio.empresa.id,
        turno.id,
        CobroCrear(pagos=[PagoLinea(metodo_pago_id=negocio.metodo.id, monto=10000)]),
        negocio.dueno.id,
    )
    db.flush()

    movs = _movimientos(db, negocio.empresa.id)
    pagos = _pagos(db, negocio.empresa.id)

    assert len(movs) == 1, "el cobro no dejó movimiento: falta en la caja"
    assert len(pagos) == 1, "el cobro no dejó pago: falta en las estadísticas"
    assert float(movs[0].monto) == 10000
    assert _facturado(db, negocio) == 10000


def test_el_pago_dividido_no_pierde_ninguna_parte(db, negocio):
    """Mitad en efectivo, mitad con tarjeta: el caso donde es fácil que una
    línea se registre y la otra no."""
    turno = _turno(db, negocio)
    otro = svc_fin.crear_metodo(
        db,
        negocio.empresa.id,
        type("D", (), {"model_dump": lambda s: {"nombre": "Otro", "comision_pct": 0}})(),
    )
    db.flush()

    svc_fin.registrar_cobro(
        db,
        negocio.empresa.id,
        turno.id,
        CobroCrear(
            pagos=[
                PagoLinea(metodo_pago_id=negocio.metodo.id, monto=6000),
                PagoLinea(metodo_pago_id=otro.id, monto=4000),
            ]
        ),
        negocio.dueno.id,
    )
    db.flush()

    assert len(_pagos(db, negocio.empresa.id)) == 2
    assert _facturado(db, negocio) == 10000


def test_un_turno_no_se_puede_cobrar_dos_veces(db, negocio):
    """La caja cerraría con el doble y el duplicado no se puede anular desde
    la app: anular_movimiento rechaza los movimientos con pago asociado."""
    from fastapi import HTTPException

    turno = _turno(db, negocio)
    cobro = CobroCrear(pagos=[PagoLinea(metodo_pago_id=negocio.metodo.id, monto=10000)])
    svc_fin.registrar_cobro(db, negocio.empresa.id, turno.id, cobro, negocio.dueno.id)
    db.flush()

    with pytest.raises(HTTPException) as e:
        svc_fin.registrar_cobro(db, negocio.empresa.id, turno.id, cobro, negocio.dueno.id)
    assert e.value.status_code == 409


# ── La venta de una gift card ────────────────────────────────────────────

def test_vender_una_gift_card_entra_a_la_caja(db, negocio):
    """Vender una gift card es una venta como cualquier otra: entra plata hoy.

    Si no generara movimiento, el arqueo del día cerraría con una diferencia
    sin explicación — y como al canjearla el turno queda cubierto, esa venta
    no aparecería nunca en ningún lado.
    """
    svc_gift.crear(
        db,
        negocio.empresa.id,
        GiftCardCrear(monto=25000, metodo_pago_id=negocio.metodo.id),
        negocio.dueno.id,
    )
    db.flush()

    movs = _movimientos(db, negocio.empresa.id)
    assert len(movs) == 1
    assert float(movs[0].monto) == 25000
    assert _facturado(db, negocio) == 25000


def test_una_gift_card_de_regalo_no_ensucia_la_caja(db, negocio):
    """Sin método de pago es un regalo del negocio: no entró plata, así que
    sumarla inflaría la facturación con algo que nadie pagó."""
    svc_gift.crear(
        db, negocio.empresa.id, GiftCardCrear(monto=25000), negocio.dueno.id
    )
    db.flush()

    assert _movimientos(db, negocio.empresa.id) == []
    assert _facturado(db, negocio) == 0


# ── El cobro de un abono ─────────────────────────────────────────────────

def test_cobrar_una_membresia_entra_a_la_caja_y_a_estadisticas(db, negocio):
    plan = svc_memb.crear_plan(
        db,
        negocio.empresa.id,
        type("D", (), {"model_dump": lambda s, **k: {
            "nombre": "Mensual", "precio": 50000, "ilimitado": True,
        }})(),
    )
    db.flush()

    hoy = dt.date.today()
    svc_memb.crear_membresia(
        db,
        negocio.empresa.id,
        MembresiaCrear(
            cliente_id=negocio.cliente.id,
            plan_id=plan.id,
            fecha_desde=hoy,
            fecha_hasta=hoy + dt.timedelta(days=30),
            metodo_pago_id=negocio.metodo.id,
        ),
        negocio.dueno.id,
    )
    db.flush()

    movs = _movimientos(db, negocio.empresa.id)
    assert len(movs) == 1, "el abono no dejó movimiento: falta en la caja"
    assert float(movs[0].monto) == 50000
    assert _facturado(db, negocio) == 50000


# ── El local de cada plata (multisucursal) ───────────────────────────────

def test_toda_plata_que_entra_sabe_en_que_local_entro(db, negocio):
    """El invariante de multisucursal aplicado a la plata.

    `sucursal_id` es NOT NULL con default, así que un camino que se olvide de
    ponerlo NO falla: la plata entra igual, pero al local que decidió el
    default. En una empresa de un local no se nota; en una de tres, el arqueo
    de dos de ellos queda mal y nadie sabe por qué.
    """
    turno = _turno(db, negocio)
    svc_fin.registrar_cobro(
        db, negocio.empresa.id, turno.id,
        CobroCrear(pagos=[PagoLinea(metodo_pago_id=negocio.metodo.id, monto=10000)]),
        negocio.dueno.id,
    )
    svc_gift.crear(
        db, negocio.empresa.id,
        GiftCardCrear(monto=5000, metodo_pago_id=negocio.metodo.id),
        negocio.dueno.id,
    )
    db.flush()

    for m in _movimientos(db, negocio.empresa.id):
        assert m.sucursal_id == negocio.sede.id, (
            f"«{m.concepto}» entró al local {m.sucursal_id} y no al {negocio.sede.id}"
        )
    for p in _pagos(db, negocio.empresa.id):
        assert p.sucursal_id == negocio.sede.id, (
            "un pago quedó fuera del arqueo de su local"
        )


def test_todo_ingreso_dice_con_que_se_cobro(db, negocio):
    """Sin `metodo_pago_id` el cierre de caja no puede explicar la plata:
    aparece en el total y no en ninguna de las filas por método."""
    turno = _turno(db, negocio)
    svc_fin.registrar_cobro(
        db, negocio.empresa.id, turno.id,
        CobroCrear(pagos=[PagoLinea(metodo_pago_id=negocio.metodo.id, monto=10000)]),
        negocio.dueno.id,
    )
    svc_gift.crear(
        db, negocio.empresa.id,
        GiftCardCrear(monto=5000, metodo_pago_id=negocio.metodo.id),
        negocio.dueno.id,
    )
    db.flush()

    for m in _movimientos(db, negocio.empresa.id):
        assert m.metodo_pago_id is not None, f"«{m.concepto}» no dice con qué se cobró"


# ── Los tres lugares tienen que dar el MISMO número ──────────────────────

def test_caja_y_estadisticas_no_se_pueden_contradecir(db, negocio):
    """EL test de este archivo.

    La caja lee de `movimiento_financiero` y las estadísticas de `pago`. Son
    dos tablas distintas alimentadas por cinco caminos distintos. Que den
    números diferentes no rompe nada, no da ningún error, y se descubre a fin
    de mes cuando ya no se sabe cuál de los cinco faltó.
    """
    turno = _turno(db, negocio)
    svc_fin.registrar_cobro(
        db, negocio.empresa.id, turno.id,
        CobroCrear(pagos=[PagoLinea(metodo_pago_id=negocio.metodo.id, monto=10000)]),
        negocio.dueno.id,
    )
    svc_gift.crear(
        db, negocio.empresa.id,
        GiftCardCrear(monto=25000, metodo_pago_id=negocio.metodo.id),
        negocio.dueno.id,
    )
    plan = svc_memb.crear_plan(
        db, negocio.empresa.id,
        type("D", (), {"model_dump": lambda s, **k: {
            "nombre": "Mensual", "precio": 50000, "ilimitado": True,
        }})(),
    )
    db.flush()
    hoy = dt.date.today()
    svc_memb.crear_membresia(
        db, negocio.empresa.id,
        MembresiaCrear(
            cliente_id=negocio.cliente.id, plan_id=plan.id,
            fecha_desde=hoy, fecha_hasta=hoy + dt.timedelta(days=30),
            metodo_pago_id=negocio.metodo.id,
        ),
        negocio.dueno.id,
    )
    db.flush()

    esperado = 10000 + 25000 + 50000

    en_caja = sum(float(m.monto) for m in _movimientos(db, negocio.empresa.id))
    en_estadisticas = _facturado(db, negocio)

    assert en_caja == esperado, f"la caja dice {en_caja} y entraron {esperado}"
    assert en_estadisticas == esperado, (
        f"las estadísticas dicen {en_estadisticas} y la caja {en_caja}: "
        "algún camino de cobro escribe en una tabla y no en la otra"
    )


def test_el_arqueo_por_metodo_suma_lo_mismo_que_el_total(db, negocio):
    """Si un ingreso no tiene método, el total y la suma de las filas por
    método se separan — y el cierre no cuadra sin explicación."""
    turno = _turno(db, negocio)
    svc_fin.registrar_cobro(
        db, negocio.empresa.id, turno.id,
        CobroCrear(pagos=[PagoLinea(metodo_pago_id=negocio.metodo.id, monto=10000)]),
        negocio.dueno.id,
    )
    svc_gift.crear(
        db, negocio.empresa.id,
        GiftCardCrear(monto=25000, metodo_pago_id=negocio.metodo.id),
        negocio.dueno.id,
    )
    db.flush()

    caja = db.scalar(
        select(Caja).where(Caja.empresa_id == negocio.empresa.id).order_by(Caja.id.desc())
    )
    resumen = svc_fin.resumen_caja(db, negocio.empresa.id, caja)

    por_metodo = sum(float(f["total"]) for f in resumen["por_metodo"])
    assert por_metodo == float(resumen["total_ingresos"]), (
        f"por método suma {por_metodo} y los ingresos son "
        f"{resumen['total_ingresos']}: hay plata en la caja que el arqueo no "
        "puede explicar"
    )


# ── La seña online (Mercado Pago) ────────────────────────────────────────

def test_una_sena_cobrada_entra_a_la_caja_y_a_estadisticas(db, negocio):
    """Antes el webhook solo marcaba `sena_estado = "pagada"` y confirmaba el
    turno. La plata estaba de verdad en la cuenta de MP del negocio, pero para
    el sistema no existía: ni caja, ni arqueo, ni facturación."""
    turno = _turno(db, negocio)

    pago = svc_fin.registrar_sena_cobrada(db, turno, 5000, mp_payment_id="mp-1")
    db.flush()

    assert pago is not None
    assert _facturado(db, negocio) == 5000
    assert sum(float(m.monto) for m in _movimientos(db, negocio.empresa.id)) == 5000


def test_la_sena_no_se_registra_dos_veces(db, negocio):
    """Mercado Pago reintenta la misma notificación varias veces. Sin
    idempotencia, cada reintento suma plata que no entró."""
    turno = _turno(db, negocio)

    assert svc_fin.registrar_sena_cobrada(db, turno, 5000, mp_payment_id="mp-1")
    db.flush()
    assert svc_fin.registrar_sena_cobrada(db, turno, 5000, mp_payment_id="mp-1") is None
    db.flush()

    assert _facturado(db, negocio) == 5000


def test_la_sena_entra_por_el_metodo_de_mercado_pago_del_negocio(db, negocio):
    """El arreglo del match por clave, verificado desde el otro extremo.

    Se le renombra el método a «MP» —cosa que la pantalla deja hacer— y la
    seña siguiente tiene que caer en ESE método, no en uno nuevo. Con la
    búsqueda por nombre, acá aparecían dos «Mercado Pago» y la plata quedaba
    repartida entre los dos.
    """
    from app.models.finanzas import MetodoPago
    from app.services import metodos_pago as svc_metodos

    svc_metodos.sembrar(db, negocio.empresa.id)
    db.flush()
    mp = svc_metodos.por_clave(db, negocio.empresa.id, "mp_qr")
    mp.nombre = "MP"
    db.flush()

    turno = _turno(db, negocio)
    pago = svc_fin.registrar_sena_cobrada(db, turno, 5000, mp_payment_id="mp-2")
    db.flush()

    assert pago.metodo_pago_id == mp.id
    con_clave_mp = db.scalars(
        select(MetodoPago).where(
            MetodoPago.empresa_id == negocio.empresa.id,
            MetodoPago.clave == "mp_qr",
        )
    ).all()
    assert len(con_clave_mp) == 1, "se creó un método de Mercado Pago duplicado"
