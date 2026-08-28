"""Regresión del fix-027: anular una gift card tiene que sacarla de la facturación.

EL CASO QUE LO ORIGINÓ, tal cual lo reportó Leandro:
    "Puse una gift card, le puse cincuenta mil pesos, la creé, perfecto, me
    aparece en el apartado de estadística cincuenta mil, pero ahora que la
    eliminé, sigue apareciéndome cincuenta mil."

La causa era estructural: vender una gift card escribe en TRES tablas
(gift_card, movimiento_financiero, pago) y el borrado tocaba UNA. Estadísticas
lee de `pago`, así que la plata quedaba facturada para siempre.

Estos tests fijan las dos puntas: que el número baje, y que no baje de más
(una tarjeta ya canjeada no se puede anular, porque el servicio se prestó).
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.models import GiftCard
from app.models.enums import EstadoCaja, EstadoGiftCard
from app.models.finanzas import Caja, MovimientoFinanciero, Pago
from app.services import estadisticas as svc_estadisticas

from .conftest import token_de


def _facturado(db, empresa_id) -> float:
    """Lo mismo que muestra la pantalla de Estadísticas."""
    hoy = dt.datetime.now(dt.timezone.utc)
    datos = svc_estadisticas.facturacion(
        db,
        empresa_id,
        desde=hoy - dt.timedelta(days=1),
        hasta=hoy + dt.timedelta(days=1),
    )
    return float(datos["facturado_real"])


def _crear(client, ctx, monto=50000, con_metodo=True):
    cuerpo = {"monto": monto, "beneficiario": "Ana"}
    if con_metodo:
        cuerpo["metodo_pago_id"] = ctx.metodo.id
    r = client.post("/gift-cards", headers=token_de(ctx.dueno), json=cuerpo)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════
#  El caso reportado
# ══════════════════════════════════════════════════════════════════════

def test_anular_la_gift_card_baja_la_facturacion(client, db, armar_empresa):
    ctx = armar_empresa()
    antes = _facturado(db, ctx.empresa.id)

    gc = _crear(client, ctx, monto=50000)
    db.expire_all()
    assert _facturado(db, ctx.empresa.id) == pytest.approx(antes + 50000), (
        "La venta de la gift card tiene que entrar a la facturación."
    )

    r = client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    assert r.status_code == 204, r.text
    db.expire_all()

    assert _facturado(db, ctx.empresa.id) == pytest.approx(antes), (
        "Se anuló la gift card y la facturación siguió mostrando la venta. "
        "Este es exactamente el bug del fix-027."
    )


def test_la_tarjeta_queda_anulada_y_no_se_borra(client, db, armar_empresa):
    """La plata se movió: tiene que quedar rastro, no desaparecer la fila."""
    ctx = armar_empresa()
    gc = _crear(client, ctx)

    client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    db.expire_all()

    fila = db.get(GiftCard, gc["id"])
    assert fila is not None, "La gift card no se borra: se anula."
    assert fila.estado == EstadoGiftCard.ANULADA


def test_anular_marca_el_pago_y_el_movimiento(client, db, armar_empresa):
    ctx = armar_empresa()
    gc = _crear(client, ctx)
    db.expire_all()

    fila = db.get(GiftCard, gc["id"])
    mov_id = fila.movimiento_id
    assert mov_id is not None

    client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    db.expire_all()

    mov = db.get(MovimientoFinanciero, mov_id)
    pago = db.scalar(select(Pago).where(Pago.movimiento_id == mov_id))
    assert mov.anulado is True, "La caja tiene que dejar de contar esa venta."
    assert pago.anulado is True, "Estadísticas lee de pago: sin esto el número no baja."
    assert pago.anulado_por_id == ctx.dueno.id, "Hay que poder auditar quién anuló."


def test_una_gift_card_ya_canjeada_no_se_puede_anular(client, db, armar_empresa):
    """El servicio se prestó: borrar el ingreso ahí sería falsear la caja."""
    ctx = armar_empresa()
    gc = _crear(client, ctx)

    r = client.post(
        "/gift-cards/canjear",
        headers=token_de(ctx.dueno),
        json={"codigo": gc["codigo"]},
    )
    assert r.json()["valida"] is True

    r = client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    assert r.status_code == 409


def test_una_gift_card_anulada_no_se_puede_canjear(client, db, armar_empresa):
    """Si no, el cliente presenta la tarjeta y el mostrador se la toma igual."""
    ctx = armar_empresa()
    gc = _crear(client, ctx)
    client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))

    r = client.post(
        "/gift-cards/canjear",
        headers=token_de(ctx.dueno),
        json={"codigo": gc["codigo"]},
    )
    assert r.json()["valida"] is False
    assert r.json()["motivo"] == "anulada"


def test_anular_dos_veces_da_409(client, db, armar_empresa):
    ctx = armar_empresa()
    gc = _crear(client, ctx)
    assert client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno)).status_code == 204
    assert client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno)).status_code == 409


def test_una_gift_card_de_regalo_se_anula_sin_romper(client, db, armar_empresa):
    """Sin método de pago no hay venta que revertir, pero igual se da de baja."""
    ctx = armar_empresa()
    gc = _crear(client, ctx, con_metodo=False)

    r = client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    assert r.status_code == 204
    db.expire_all()
    assert db.get(GiftCard, gc["id"]).estado == EstadoGiftCard.ANULADA


def test_no_se_puede_anular_contra_una_caja_ya_cerrada(client, db, armar_empresa):
    """Un arqueo firmado no se toca: se ajusta con un movimiento nuevo."""
    ctx = armar_empresa()
    # La venta tiene que quedar asociada a una caja: es el caso que se prueba.
    r = client.post(
        "/caja/abrir", headers=token_de(ctx.dueno), json={"saldo_inicial": 0}
    )
    assert r.status_code in (200, 201), r.text

    gc = _crear(client, ctx)
    db.expire_all()

    fila = db.get(GiftCard, gc["id"])
    mov = db.get(MovimientoFinanciero, fila.movimiento_id)
    assert mov.caja_id is not None
    caja = db.get(Caja, mov.caja_id)
    caja.estado = EstadoCaja.CERRADA
    db.commit()

    r = client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    assert r.status_code == 409
    assert "cerrada" in r.json()["detail"].lower()


def test_el_aislamiento_por_empresa_se_mantiene(client, db, armar_empresa):
    """Una empresa no puede anular la gift card de otra."""
    a = armar_empresa()
    b = armar_empresa()
    gc = _crear(client, a)

    r = client.delete(f"/gift-cards/{gc['id']}", headers=token_de(b.dueno))
    assert r.status_code == 404
