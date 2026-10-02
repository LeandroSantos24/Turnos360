"""Auditoría pre-deploy 2026-10-02: integridad económica.

Regla de oro: ningún peso aparece o desaparece sin una razón trazable.
Cada test recorre una operación de punta a punta y compara las tres fuentes
que tienen que coincidir: el PAGO (de donde lee Estadísticas), el MOVIMIENTO
(de donde lee la Caja) y el TURNO (saldo, cobrado).

Los marcados [BUG] fallaban contra el código anterior a esta auditoría.
"""

import datetime as dt

import pytest
from sqlalchemy import func, select

from app.models.enums import EstadoTurno
from app.models.finanzas import MetodoPago, MovimientoFinanciero, Pago
from app.models.modulos.fidelizacion import Membresia, PlanAbono
from app.models.modulos.giftcards import GiftCard
from app.models.organizacion import Sucursal
from app.models.turno import Turno

from .conftest import token_de

INICIO = dt.datetime(2026, 7, 10, 15, 0, tzinfo=dt.timezone.utc)


# ─────────────────────────── helpers ───────────────────────────────────────

def _turno(db, ctx, *, importe=10000.0, estado=EstadoTurno.CONFIRMADO,
           recurso=None, inicio=INICIO) -> Turno:
    recurso = recurso or ctx.lucas
    t = Turno(
        empresa_id=ctx.empresa.id,
        sucursal_id=recurso.sucursal_id,
        cliente_id=ctx.cliente.id,
        recurso_id=recurso.id,
        servicio_id=ctx.servicio.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=estado,
        importe_previsto=importe,
    )
    db.add(t)
    db.flush()
    return t


def _metodo(db, ctx, nombre, comision=0.0, clave=None) -> MetodoPago:
    m = MetodoPago(empresa_id=ctx.empresa.id, nombre=nombre,
                   comision_pct=comision, clave=clave)
    db.add(m)
    db.flush()
    return m


def _cobrar(client, ctx, turno_id, lineas, quien=None):
    return client.post(
        f"/turnos/{turno_id}/cobro",
        headers=token_de(quien or ctx.dueno),
        json={"pagos": lineas},
    )


def _abrir_caja(client, ctx, saldo=0):
    r = client.post("/caja/abrir", headers=token_de(ctx.dueno),
                    json={"saldo_inicial": saldo})
    assert r.status_code == 201, r.text
    return r.json()


def _caja(client, ctx):
    return client.get("/caja/actual", headers=token_de(ctx.dueno)).json()


def _stats(client, ctx, desde=None, hasta=None):
    desde = desde or dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
    hasta = hasta or dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc)
    r = client.get(
        "/estadisticas/facturacion",
        headers=token_de(ctx.dueno),
        params={"desde": desde.isoformat(), "hasta": hasta.isoformat()},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _pagos_vigentes(db, turno_id):
    return list(db.scalars(
        select(Pago).where(Pago.turno_id == turno_id, Pago.anulado.is_(False))
    ))


# ══════════════════════════════════════════════════════════════════════
# TEST 1-3 · Cobro por método: Pago == Movimiento == Caja == Estadísticas
# ══════════════════════════════════════════════════════════════════════

def test_01_efectivo_entra_a_caja_al_cajon_y_a_estadisticas(client, db, armar_empresa):
    ctx = armar_empresa()
    efectivo = _metodo(db, ctx, "Efectivo", clave="efectivo")
    t = _turno(db, ctx)
    db.commit()
    _abrir_caja(client, ctx, saldo=1000)

    r = _cobrar(client, ctx, t.id, [{"metodo_pago_id": efectivo.id, "monto": 10000}])
    assert r.status_code == 201, r.text

    caja = _caja(client, ctx)
    assert caja["total_ingresos"] == 10000
    assert caja["saldo_esperado"] == 11000
    assert caja["efectivo_esperado"] == 11000
    st = _stats(client, ctx)
    assert st["facturado_real"] == 10000
    pago = _pagos_vigentes(db, t.id)[0]
    mov = db.get(MovimientoFinanciero, pago.movimiento_id)
    assert (pago.monto, mov.monto, mov.caja_id) == (10000, 10000, caja["caja"]["id"])
    assert pago.cliente_id == ctx.cliente.id and pago.metodo_pago_id == efectivo.id


def test_02_transferencia_no_suma_al_cajon_pero_si_a_caja(client, db, armar_empresa):
    ctx = armar_empresa()
    transf = _metodo(db, ctx, "Transferencia", clave="transferencia")
    t = _turno(db, ctx)
    db.commit()
    _abrir_caja(client, ctx)
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": transf.id, "monto": 10000}]).status_code == 201
    caja = _caja(client, ctx)
    assert caja["total_ingresos"] == 10000
    assert caja["efectivo_esperado"] == 0
    assert caja["por_metodo"][0]["metodo"] == "Transferencia"


def test_03_tarjeta_bruto_menos_comision_es_neto_en_los_tres_lugares(client, db, armar_empresa):
    ctx = armar_empresa()
    credito = _metodo(db, ctx, "Crédito", comision=6.5, clave="credito")
    t = _turno(db, ctx)
    db.commit()
    _abrir_caja(client, ctx)
    r = _cobrar(client, ctx, t.id, [{"metodo_pago_id": credito.id, "monto": 10000}])
    assert r.status_code == 201
    assert (r.json()["total_cobrado"], r.json()["total_comision"], r.json()["neto"]) == (10000, 650, 9350)
    caja = _caja(client, ctx)
    assert (caja["total_ingresos"], caja["total_comisiones"], caja["total_neto"]) == (10000, 650, 9350)
    st = _stats(client, ctx)
    assert (st["facturado_real"], st["comision_total"], st["neto"]) == (10000, 650, 9350)


# ══════════════════════════════════════════════════════════════════════
# TEST 4 · Descuentos
# ══════════════════════════════════════════════════════════════════════

def test_04_descuento_porcentual_el_ingreso_es_el_subtotal(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=20000)
    db.commit()
    r = client.patch(f"/turnos/{t.id}/descuento", headers=token_de(ctx.dueno),
                     json={"descuento_pct": 25})
    assert r.json()["total"] == 15000 and r.json()["saldo"] == 15000
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 15000}]).status_code == 201
    assert _stats(client, ctx)["facturado_real"] == 15000


def test_04b_descuento_fijo_en_pesos(client, db, armar_empresa):
    """[BUG] No existía el descuento fijo: solo %. Servicio $20.000 − $5.000."""
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=20000)
    db.commit()
    r = client.patch(f"/turnos/{t.id}/descuento", headers=token_de(ctx.dueno),
                     json={"descuento_pct": 0, "descuento_monto": 5000})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 15000


def test_04c_no_se_puede_cobrar_mas_que_el_saldo(client, db, armar_empresa):
    """[BUG] El backend aceptaba cobrar $20.000 un turno de $15.000: $5.000
    de ingreso sin origen, atribuido al servicio y al profesional."""
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=15000)
    db.commit()
    r = _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 20000}])
    assert r.status_code == 422, r.text
    assert _pagos_vigentes(db, t.id) == []


def test_04d_descuento_despues_de_cobrar_se_rechaza(client, db, armar_empresa):
    """[BUG] Se podía cobrar $10.000 y después poner 50 %: el turno decía
    $5.000 y la caja $10.000. Dos números para el mismo hecho."""
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    r = client.patch(f"/turnos/{t.id}/descuento", headers=token_de(ctx.dueno),
                     json={"descuento_pct": 50})
    assert r.status_code == 409


def test_04e_adicional_despues_de_cobrar_se_rechaza(client, db, armar_empresa):
    """[BUG] Mismo agujero por los adicionales."""
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    r = client.post(f"/turnos/{t.id}/items", headers=token_de(ctx.dueno),
                    json={"descripcion": "Cera", "precio": 3000})
    assert r.status_code == 409


def test_04f_cupon_fijo_web_no_redondea_centavos(client, db, armar_empresa):
    """[BUG] Un cupón de $5.000 sobre $15.000 se guardaba como 33,33 % y el
    turno quedaba en $10.000,50: se le cobraban 50 centavos de más."""
    from app.models.cupon import CuponDescuento

    ctx = armar_empresa()
    ctx.servicio.precio = 15000
    db.add(CuponDescuento(empresa_id=ctx.empresa.id, codigo="MENOS5", tipo="monto",
                          valor=5000, servicios_ids=[]))
    db.commit()
    inicio = dt.datetime.combine(dt.date.today() + dt.timedelta(days=2), dt.time(11, 0))
    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json={
        "servicio_id": ctx.servicio.id, "recurso_id": ctx.lucas.id,
        "inicio": inicio.isoformat(), "cupon_codigo": "MENOS5",
        "cliente": {"nombre": "Ana", "telefono": "2615550001", "email": "ana@example.com"},
    })
    assert r.status_code in (200, 201), r.text
    t = db.scalar(select(Turno).where(Turno.empresa_id == ctx.empresa.id).order_by(Turno.id.desc()))
    r = client.get(f"/turnos/{t.id}", headers=token_de(ctx.dueno))
    assert r.json()["total"] == 10000.0


# ══════════════════════════════════════════════════════════════════════
# TEST 5 · Reasignación
# ══════════════════════════════════════════════════════════════════════

def test_05_reasignar_y_cobrar_un_solo_ingreso_para_el_correcto(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, recurso=ctx.lucas)
    db.commit()
    _abrir_caja(client, ctx)
    r = client.patch(f"/turnos/{t.id}/mover", headers=token_de(ctx.dueno),
                     json={"fecha_inicio": "2026-07-10T16:00:00Z", "recurso_id": ctx.pablo.id})
    assert r.status_code == 200, r.text
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    st = _stats(client, ctx)
    assert [(p["recurso"], p["total"]) for p in st["por_profesional"]] == [("Pablo Vega", 10000)]
    assert _caja(client, ctx)["cantidad_movimientos"] == 1


def test_05b_reasignar_a_otro_local_mueve_el_turno_de_local(client, db, armar_empresa):
    """[BUG] Al pasar el turno a un profesional de OTRO local, el turno seguía
    en el local viejo: el cobro entraba a la caja de un local donde no se
    atendió y las estadísticas por sucursal quedaban mal."""
    ctx = armar_empresa()
    otro = Sucursal(empresa_id=ctx.empresa.id, nombre="Centro", activa=True)
    db.add(otro)
    db.flush()
    ctx.pablo.sucursal_id = otro.id
    from app.models.agenda import ServicioSucursal

    db.add(ServicioSucursal(empresa_id=ctx.empresa.id, servicio_id=ctx.servicio.id,
                            sucursal_id=otro.id))
    t = _turno(db, ctx, recurso=ctx.lucas)
    db.commit()
    r = client.patch(f"/turnos/{t.id}/mover", headers=token_de(ctx.dueno),
                     json={"fecha_inicio": "2026-07-10T16:00:00Z", "recurso_id": ctx.pablo.id})
    assert r.status_code == 200, r.text
    db.refresh(t)
    assert t.sucursal_id == otro.id


# ══════════════════════════════════════════════════════════════════════
# TEST 6-7 · Reprogramación, cancelación y reversión del cobro
# ══════════════════════════════════════════════════════════════════════

def test_06_reprogramar_no_duplica(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.commit()
    client.patch(f"/turnos/{t.id}/mover", headers=token_de(ctx.dueno),
                 json={"fecha_inicio": "2026-07-11T15:00:00Z"})
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]).status_code == 201
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]).status_code == 409
    assert len(_pagos_vigentes(db, t.id)) == 1


def test_06b_no_se_reprograma_un_turno_cobrado(client, db, armar_empresa):
    """[BUG] Se podía mover un turno finalizado y cobrado a otro día."""
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    r = client.patch(f"/turnos/{t.id}/mover", headers=token_de(ctx.dueno),
                     json={"fecha_inicio": "2026-07-12T15:00:00Z"})
    assert r.status_code == 409


def test_07_cancelado_cuenta_en_estadisticas_y_no_factura(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.PENDIENTE)
    db.commit()
    client.patch(f"/turnos/{t.id}/estado", headers=token_de(ctx.dueno), json={"estado": "confirmado"})
    client.patch(f"/turnos/{t.id}/estado", headers=token_de(ctx.dueno), json={"estado": "cancelado"})
    st = _stats(client, ctx, INICIO - dt.timedelta(days=1), INICIO + dt.timedelta(days=1))
    assert st["estados"]["cancelados"] == 1 and st["facturado_real"] == 0


def test_07b_no_se_cobra_un_turno_cancelado(client, db, armar_empresa):
    """[BUG] Se podía registrar plata contra un turno cancelado."""
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.CANCELADO)
    db.commit()
    r = _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    assert r.status_code == 409


def test_07c_no_se_cancela_un_turno_cobrado_sin_anular_el_cobro(client, db, armar_empresa):
    """[BUG] Cobrado → reabierto → cancelado dejaba el ingreso vivo en un
    turno cancelado. Plata contabilizada de una operación anulada."""
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.EN_CURSO)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    r = client.patch(f"/turnos/{t.id}/estado", headers=token_de(ctx.dueno), json={"estado": "cancelado"})
    assert r.status_code == 409


def test_07d_anular_cobro_revierte_las_tres_puntas(client, db, armar_empresa):
    """[BUG] Un cobro mal cargado no tenía vuelta: Caja decía «reabrí el
    turno», reabrir el turno no tocaba la plata, y el aviso de la agenda
    mandaba a Caja. Círculo cerrado; la única salida era psql."""
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)
    db.commit()
    _abrir_caja(client, ctx)
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])

    r = client.post(f"/turnos/{t.id}/anular-cobro", headers=token_de(ctx.dueno),
                    json={"motivo": "lo cargué al cliente equivocado"})
    assert r.status_code == 200, r.text
    db.refresh(t)
    assert t.cobrado is False
    assert _pagos_vigentes(db, t.id) == []
    assert _caja(client, ctx)["total_ingresos"] == 0
    assert _stats(client, ctx)["facturado_real"] == 0
    # y se puede volver a cobrar bien
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]).status_code == 201


def test_07e_anular_cobro_es_solo_del_dueno(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    r = client.post(f"/turnos/{t.id}/anular-cobro", headers=token_de(ctx.profesional), json={})
    assert r.status_code == 403


def test_07f_anular_cobro_de_caja_cerrada_se_rechaza(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)
    db.commit()
    _abrir_caja(client, ctx)
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    client.post("/caja/cerrar", headers=token_de(ctx.dueno), json={"saldo_real": 10000})
    r = client.post(f"/turnos/{t.id}/anular-cobro", headers=token_de(ctx.dueno), json={})
    assert r.status_code == 409


def test_07g_saldo_y_pagado_ignoran_pagos_anulados(client, db, armar_empresa):
    """[BUG] El saldo del turno sumaba pagos anulados."""
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=t.sucursal_id, turno_id=t.id,
                cliente_id=ctx.cliente.id, monto=4000, origen="sena", anulado=True))
    db.commit()
    r = client.get(f"/turnos/{t.id}", headers=token_de(ctx.dueno)).json()
    assert (r["senado"], r["pagado_total"], r["saldo"]) == (0, 0, 10000)


def test_07h_lo_cobrado_al_cliente_ignora_anulados(client, db, armar_empresa):
    """[BUG] La ficha del cliente sumaba ventas anuladas."""
    ctx = armar_empresa()
    db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=ctx.sede.id, cliente_id=ctx.cliente.id,
                monto=50000, origen="abono", anulado=True))
    db.commit()
    r = client.get(f"/clientes/{ctx.cliente.id}/cobrado", headers=token_de(ctx.dueno)).json()
    assert r["total_cobrado"] == 0


# ══════════════════════════════════════════════════════════════════════
# TEST 8-9 · Gift cards: se cobra al venderla, NO al usarla
# ══════════════════════════════════════════════════════════════════════

def _vender_gc(client, ctx, monto=50000, metodo_id=None):
    r = client.post("/gift-cards", headers=token_de(ctx.dueno),
                    json={"monto": monto, "metodo_pago_id": metodo_id or ctx.metodo.id,
                          "beneficiario": "Ana"})
    assert r.status_code == 201, r.text
    return r.json()


def test_08_venta_de_gift_card_entra_a_caja_con_su_metodo(client, db, armar_empresa):
    ctx = armar_empresa()
    transf = _metodo(db, ctx, "Transferencia")
    db.commit()
    _abrir_caja(client, ctx)
    gc = _vender_gc(client, ctx, 50000, transf.id)
    caja = _caja(client, ctx)
    assert caja["total_ingresos"] == 50000
    assert caja["por_metodo"][0]["metodo"] == "Transferencia"
    st = _stats(client, ctx)
    assert st["facturado_real"] == 50000
    assert gc["saldo"] == 50000


def test_09_usar_gift_card_no_vuelve_a_contar_el_ingreso(client, db, armar_empresa):
    """[BUG] El canje no estaba conectado al cobro: la recepción canjeaba y
    después cobraba el turno «en efectivo» → $50.000 de la venta + $20.000
    del cobro = plata fantasma. O no lo cobraba y el turno quedaba impago."""
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=20000, estado=EstadoTurno.FINALIZADO)
    db.commit()
    _abrir_caja(client, ctx)
    gc = _vender_gc(client, ctx, 50000)

    r = _cobrar(client, ctx, t.id, [{"gift_card_codigo": gc["codigo"], "monto": 20000}])
    assert r.status_code == 201, r.text

    caja = _caja(client, ctx)
    assert caja["total_ingresos"] == 50000, "el uso no puede volver a entrar a caja"
    assert caja["cantidad_movimientos"] == 1
    st = _stats(client, ctx)
    assert st["facturado_real"] == 50000, "el ingreso se cuenta una sola vez: al vender"
    # el profesional sí queda acreditado por el servicio prestado (comisiones)
    assert st["por_profesional"][0]["prepago"] == 20000
    db.refresh(t)
    assert t.cobrado is True
    assert db.get(GiftCard, gc["id"]).saldo == 30000


def test_09b_uso_parcial_total_y_sin_saldo(client, db, armar_empresa):
    ctx = armar_empresa()
    t1 = _turno(db, ctx, importe=30000, estado=EstadoTurno.FINALIZADO)
    t2 = _turno(db, ctx, importe=20000, estado=EstadoTurno.FINALIZADO,
                inicio=INICIO + dt.timedelta(hours=1))
    t3 = _turno(db, ctx, importe=10000, estado=EstadoTurno.FINALIZADO,
                inicio=INICIO + dt.timedelta(hours=2))
    db.commit()
    gc = _vender_gc(client, ctx, 50000)
    assert _cobrar(client, ctx, t1.id, [{"gift_card_codigo": gc["codigo"], "monto": 30000}]).status_code == 201
    assert _cobrar(client, ctx, t2.id, [{"gift_card_codigo": gc["codigo"], "monto": 20000}]).status_code == 201
    g = db.get(GiftCard, gc["id"])
    db.refresh(g)
    assert g.saldo == 0 and g.estado.value == "canjeada"
    r = _cobrar(client, ctx, t3.id, [{"gift_card_codigo": gc["codigo"], "monto": 10000}])
    assert r.status_code == 409
    # gift card + efectivo en el mismo cobro (pago dividido)
    gc2 = _vender_gc(client, ctx, 4000)
    r = _cobrar(client, ctx, t3.id, [{"gift_card_codigo": gc2["codigo"], "monto": 4000},
                                     {"metodo_pago_id": ctx.metodo.id, "monto": 6000}])
    assert r.status_code == 201, r.text


def test_09c_no_se_usa_mas_saldo_del_que_tiene(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=20000, estado=EstadoTurno.FINALIZADO)
    db.commit()
    gc = _vender_gc(client, ctx, 5000)
    r = _cobrar(client, ctx, t.id, [{"gift_card_codigo": gc["codigo"], "monto": 20000}])
    assert r.status_code == 409
    assert db.get(GiftCard, gc["id"]).saldo == 5000


def test_09d_anular_cobro_con_gift_card_devuelve_el_saldo(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=20000, estado=EstadoTurno.FINALIZADO)
    db.commit()
    gc = _vender_gc(client, ctx, 50000)
    _cobrar(client, ctx, t.id, [{"gift_card_codigo": gc["codigo"], "monto": 20000}])
    client.post(f"/turnos/{t.id}/anular-cobro", headers=token_de(ctx.dueno), json={})
    g = db.get(GiftCard, gc["id"])
    db.refresh(g)
    assert g.saldo == 50000 and g.estado.value == "activa"


def test_09e_gift_card_usada_en_parte_no_se_anula(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=20000, estado=EstadoTurno.FINALIZADO)
    db.commit()
    gc = _vender_gc(client, ctx, 50000)
    _cobrar(client, ctx, t.id, [{"gift_card_codigo": gc["codigo"], "monto": 20000}])
    r = client.delete(f"/gift-cards/{gc['id']}", headers=token_de(ctx.dueno))
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════════════════
# TEST 10-11 · Membresías
# ══════════════════════════════════════════════════════════════════════

def _plan(db, ctx, cupos=None, precio=30000):
    p = PlanAbono(empresa_id=ctx.empresa.id, nombre="Mensual", precio=precio,
                  ilimitado=cupos is None, cantidad_cupos=cupos,
                  servicios_cubiertos=[ctx.servicio.id])
    db.add(p)
    db.flush()
    return p


def _asignar(client, ctx, plan, desde=None, hasta=None, metodo=True):
    desde = desde or dt.date.today() - dt.timedelta(days=1)
    hasta = hasta or dt.date.today() + dt.timedelta(days=29)
    r = client.post("/membresias", headers=token_de(ctx.dueno), json={
        "cliente_id": ctx.cliente.id, "plan_id": plan.id,
        "fecha_desde": desde.isoformat(), "fecha_hasta": hasta.isoformat(),
        **({"metodo_pago_id": ctx.metodo.id} if metodo else {}),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _crear_por_api(client, ctx, inicio):
    r = client.post("/turnos", headers=token_de(ctx.dueno), json={
        "cliente_id": ctx.cliente.id, "recurso_id": ctx.lucas.id,
        "servicio_id": ctx.servicio.id, "fecha_inicio": inicio.isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _maniana(h):
    return dt.datetime.combine(dt.date.today() + dt.timedelta(days=1), dt.time(h, 0),
                               tzinfo=dt.timezone.utc)


def test_10_venta_de_membresia_entra_a_caja(client, db, armar_empresa):
    ctx = armar_empresa()
    plan = _plan(db, ctx)
    db.commit()
    _abrir_caja(client, ctx)
    m = _asignar(client, ctx, plan)
    assert _caja(client, ctx)["total_ingresos"] == 30000
    assert m["monto_cobrado"] == 30000 and m["metodo_pago_id"] == ctx.metodo.id
    o = {x["origen"]: x["total"] for x in _stats(client, ctx)["por_origen"]}
    assert o["abono"] == 30000


def test_11_los_cupos_del_plan_se_respetan(client, db, armar_empresa):
    """[BUG] cantidad_cupos no se controlaba ni cupos_usados se contaba nunca:
    un plan de 2 cortes cubría cortes ilimitados en $0."""
    ctx = armar_empresa()
    plan = _plan(db, ctx, cupos=2)
    db.commit()
    _asignar(client, ctx, plan)
    t1 = _crear_por_api(client, ctx, _maniana(10))
    t2 = _crear_por_api(client, ctx, _maniana(11))
    t3 = _crear_por_api(client, ctx, _maniana(12))
    assert [t["cubierto_por_abono"] for t in (t1, t2, t3)] == [True, True, False]
    assert t3["importe_previsto"] == 10000
    m = client.get(f"/clientes/{ctx.cliente.id}/membresia", headers=token_de(ctx.dueno)).json()
    assert m["cupos_usados"] == 2 and m["cupos_disponibles"] == 0


def test_11b_cancelar_un_turno_cubierto_devuelve_el_cupo(client, db, armar_empresa):
    ctx = armar_empresa()
    plan = _plan(db, ctx, cupos=1)
    db.commit()
    _asignar(client, ctx, plan)
    t1 = _crear_por_api(client, ctx, _maniana(10))
    client.patch(f"/turnos/{t1['id']}/estado", headers=token_de(ctx.dueno), json={"estado": "cancelado"})
    t2 = _crear_por_api(client, ctx, _maniana(11))
    assert t2["cubierto_por_abono"] is True


def test_11c_el_abono_no_cubre_un_turno_posterior_al_vencimiento(client, db, armar_empresa):
    """[BUG] Se miraba la vigencia HOY, no el día del turno: con el abono
    venciendo mañana, un turno de dentro de 2 meses salía gratis."""
    ctx = armar_empresa()
    plan = _plan(db, ctx)
    db.commit()
    _asignar(client, ctx, plan, hasta=dt.date.today() + dt.timedelta(days=2))
    lejos = dt.datetime.combine(dt.date.today() + dt.timedelta(days=60), dt.time(10, 0),
                                tzinfo=dt.timezone.utc)
    t = _crear_por_api(client, ctx, lejos)
    assert t["cubierto_por_abono"] is False and t["importe_previsto"] == 10000


def test_11d_anular_la_venta_del_abono_la_saca_de_la_rentabilidad(client, db, armar_empresa):
    """[BUG] Se anulaba el movimiento y el pago, pero la membresía seguía con
    monto_cobrado: la pantalla de rentabilidad contaba plata que no estaba."""
    ctx = armar_empresa()
    plan = _plan(db, ctx)
    db.commit()
    _abrir_caja(client, ctx)
    m = _asignar(client, ctx, plan)
    mem = db.get(Membresia, m["id"])
    r = client.post(f"/movimientos/{mem.movimiento_id}/anular", headers=token_de(ctx.dueno),
                    json={"motivo": "error"})
    assert r.status_code == 200
    db.refresh(mem)
    assert mem.monto_cobrado is None
    est = client.get("/membresias/estadisticas", headers=token_de(ctx.dueno)).json()
    assert est["resumen"]["total_ingreso"] == 0


def test_11e_reserva_web_con_abono_no_cobra_por_mercado_pago(client, db, armar_empresa, monkeypatch):
    """[BUG] Con el cobro «total» activo, un abonado que reservaba por la web
    pagaba el servicio completo por MP aunque su turno quedara en $0."""
    from app.services import mercadopago as mp

    ctx = armar_empresa()
    plan = _plan(db, ctx)
    ctx.empresa.cobro_modo = "total"
    db.commit()
    _asignar(client, ctx, plan)
    llamadas = []
    monkeypatch.setattr(mp, "crear_preferencia", lambda *a, **k: llamadas.append(a) or "https://mp.test/x")
    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json={
        "servicio_id": ctx.servicio.id, "recurso_id": ctx.lucas.id,
        "inicio": _maniana(10).replace(tzinfo=None).isoformat(),
        "cliente": {"nombre": ctx.cliente.nombre, "telefono": ctx.cliente.telefono, "email": "jp@example.com"},
    })
    assert r.status_code in (200, 201), r.text
    assert llamadas == []


# ══════════════════════════════════════════════════════════════════════
# TEST 12-14 · Mercado Pago
# ══════════════════════════════════════════════════════════════════════

def _sena(db, ctx):
    t = _turno(db, ctx, estado=EstadoTurno.PENDIENTE, inicio=_maniana(16))
    t.sena_estado = "pendiente"
    t.sena_monto = 3000
    db.commit()
    return t


def _mp(monkeypatch, respuesta):
    monkeypatch.setattr("app.services.mercadopago.token_de", lambda emp: "TOKEN")
    monkeypatch.setattr("app.services.mercadopago.consultar_pago", lambda tok, pid: respuesta(pid))


def test_12_pago_aprobado_confirma_y_entra_a_caja_y_estadisticas(client, db, armar_empresa, monkeypatch):
    ctx = armar_empresa()
    t = _sena(db, ctx)
    _abrir_caja(client, ctx)
    _mp(monkeypatch, lambda pid: {"id": pid, "status": "approved", "external_reference": str(t.id),
                                  "transaction_amount": 3000, "currency_id": "ARS"})
    client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=901")
    db.refresh(t)
    assert t.estado == EstadoTurno.CONFIRMADO
    assert _caja(client, ctx)["total_ingresos"] == 3000
    assert _stats(client, ctx)["facturado_real"] == 3000
    r = client.get(f"/turnos/{t.id}", headers=token_de(ctx.dueno)).json()
    assert r["saldo"] == 7000


def test_13_pago_rechazado_o_pendiente_no_genera_ingreso(client, db, armar_empresa, monkeypatch):
    ctx = armar_empresa()
    t = _sena(db, ctx)
    for estado, pid in (("rejected", 902), ("pending", 903), ("in_process", 904)):
        _mp(monkeypatch, lambda p, e=estado: {"id": p, "status": e, "external_reference": str(t.id),
                                             "transaction_amount": 3000, "currency_id": "ARS"})
        client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id={pid}")
    assert db.scalar(select(func.count(Pago.id)).where(Pago.turno_id == t.id)) == 0
    db.refresh(t)
    assert t.estado == EstadoTurno.PENDIENTE


def test_13b_moneda_distinta_no_se_acredita(client, db, armar_empresa, monkeypatch):
    """[BUG] No se validaba currency_id."""
    ctx = armar_empresa()
    t = _sena(db, ctx)
    _mp(monkeypatch, lambda pid: {"id": pid, "status": "approved", "external_reference": str(t.id),
                                  "transaction_amount": 3000, "currency_id": "USD"})
    client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=905")
    assert db.scalar(select(func.count(Pago.id)).where(Pago.turno_id == t.id)) == 0


def test_14_webhook_duplicado_un_solo_pago(client, db, armar_empresa, monkeypatch):
    ctx = armar_empresa()
    t = _sena(db, ctx)
    _mp(monkeypatch, lambda pid: {"id": pid, "status": "approved", "external_reference": str(t.id),
                                  "transaction_amount": 3000, "currency_id": "ARS"})
    for _ in range(3):
        client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=906")
    assert db.scalar(select(func.count(Pago.id)).where(Pago.turno_id == t.id)) == 1
    assert db.scalar(select(func.count(MovimientoFinanciero.id)).where(
        MovimientoFinanciero.empresa_id == ctx.empresa.id)) == 1


def test_14b_devolucion_de_la_sena_revierte_el_ingreso(client, db, armar_empresa, monkeypatch):
    """[BUG] Una seña devuelta (refunded/charged_back) seguía en caja y en
    estadísticas: el aviso de MP se cortaba por «ya procesado»."""
    ctx = armar_empresa()
    t = _sena(db, ctx)
    _abrir_caja(client, ctx)
    estado = {"s": "approved"}
    _mp(monkeypatch, lambda pid: {"id": pid, "status": estado["s"], "external_reference": str(t.id),
                                  "transaction_amount": 3000, "currency_id": "ARS"})
    url = f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=907"
    client.post(url, json={"action": "payment.created"})
    assert _caja(client, ctx)["total_ingresos"] == 3000
    estado["s"] = "refunded"
    client.post(url, json={"action": "payment.updated"})
    assert _caja(client, ctx)["total_ingresos"] == 0
    assert _stats(client, ctx)["facturado_real"] == 0
    db.refresh(t)
    assert t.sena_estado == "devuelta"


# ══════════════════════════════════════════════════════════════════════
# TEST 15-16 · Cierre de caja
# ══════════════════════════════════════════════════════════════════════

def test_15_16_cierre_cuadra_con_ingresos_gastos_y_ajustes(client, db, armar_empresa):
    ctx = armar_empresa()
    efectivo = _metodo(db, ctx, "Efectivo", clave="efectivo")
    transf = _metodo(db, ctx, "Transferencia")
    t1 = _turno(db, ctx)
    t2 = _turno(db, ctx, inicio=INICIO + dt.timedelta(hours=1))
    db.commit()
    _abrir_caja(client, ctx, saldo=5000)
    _cobrar(client, ctx, t1.id, [{"metodo_pago_id": efectivo.id, "monto": 10000}])
    _cobrar(client, ctx, t2.id, [{"metodo_pago_id": efectivo.id, "monto": 4000},
                                 {"metodo_pago_id": transf.id, "monto": 6000}])
    client.post("/gastos", headers=token_de(ctx.dueno),
                json={"concepto": "Insumos", "monto": 3000, "metodo_pago_id": efectivo.id})
    g = client.post("/gastos", headers=token_de(ctx.dueno),
                    json={"concepto": "Duplicado", "monto": 999}).json()
    client.post(f"/movimientos/{g['id']}/anular", headers=token_de(ctx.dueno), json={})

    r = client.post("/caja/cerrar", headers=token_de(ctx.dueno), json={"saldo_real": 16000})
    c = r.json()
    assert c["total_ingresos"] == 20000 and c["total_egresos"] == 3000
    assert c["saldo_esperado"] == 5000 + 20000 - 3000
    assert c["efectivo_esperado"] == 5000 + 14000 - 3000
    assert c["diferencia"] == 0


def test_15b_efectivo_renombrado_sigue_siendo_efectivo(client, db, armar_empresa):
    """[BUG] El cajón se detectaba por nombre: si el dueño renombraba
    «Efectivo» a «Efectivo $», el arqueo esperaba $0 en el cajón."""
    ctx = armar_empresa()
    efectivo = _metodo(db, ctx, "Efectivo $", clave="efectivo")
    t = _turno(db, ctx)
    db.commit()
    _abrir_caja(client, ctx)
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": efectivo.id, "monto": 10000}])
    assert _caja(client, ctx)["efectivo_esperado"] == 10000


def test_16b_lo_cobrado_con_la_caja_cerrada_entra_a_la_proxima(client, db, armar_empresa):
    """[BUG] Un cobro con la caja cerrada quedaba con caja_id NULL para
    siempre: no aparecía en ningún arqueo."""
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.commit()
    _abrir_caja(client, ctx)
    cerrada = client.post("/caja/cerrar", headers=token_de(ctx.dueno), json={"saldo_real": 0}).json()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    # la caja cerrada NO se toca
    det = client.get(f"/cajas/{cerrada['caja']['id']}/detalle", headers=token_de(ctx.dueno)).json()
    assert det["resumen"]["total_ingresos"] == 0
    # y la próxima caja la adopta
    _abrir_caja(client, ctx)
    assert _caja(client, ctx)["total_ingresos"] == 10000


# ══════════════════════════════════════════════════════════════════════
# Estadísticas: totales matemáticamente consistentes
# ══════════════════════════════════════════════════════════════════════

def test_est_servicios_suman_lo_mismo_que_la_facturacion(client, db, armar_empresa):
    """[BUG] «Servicios» miraba turnos FINALIZADOS por fecha de turno y la
    facturación pagos por fecha de pago: una seña cobrada el mes anterior o un
    turno cobrado sin finalizar hacían que no sumaran lo mismo."""
    ctx = armar_empresa()
    t1 = _turno(db, ctx, estado=EstadoTurno.CONFIRMADO)  # cobrado pero no finalizado
    t2 = _turno(db, ctx, estado=EstadoTurno.FINALIZADO, inicio=INICIO + dt.timedelta(hours=1))
    db.commit()
    _cobrar(client, ctx, t1.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    _cobrar(client, ctx, t2.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    st = _stats(client, ctx)
    suma_serv = sum(s["total"] for s in st["por_servicio"])
    suma_prof = sum(p["total"] for p in st["por_profesional"])
    suma_met = sum(m["total"] for m in st["por_metodo"])
    suma_dia = sum(d["total"] for d in st["por_dia"])
    assert suma_serv == suma_prof == st["facturado_turnos"] == 20000
    assert suma_met == suma_dia == st["facturado_real"] == 20000


def test_est_ticket_no_se_parte_con_el_pago_dividido(client, db, armar_empresa):
    """[BUG] El ticket dividía por cantidad de PAGOS: un turno de $10.000
    pagado mitad y mitad daba ticket $5.000."""
    ctx = armar_empresa()
    transf = _metodo(db, ctx, "Transferencia")
    t = _turno(db, ctx)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 5000},
                                {"metodo_pago_id": transf.id, "monto": 5000}])
    assert _stats(client, ctx)["ticket_promedio"] == 10000


def test_est_por_dia_usa_el_dia_del_negocio(client, db, armar_empresa):
    """[BUG] Un cobro a las 23:30 de Mendoza (02:30 UTC del día siguiente)
    aparecía en el gráfico del día siguiente."""
    ctx = armar_empresa()
    db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=ctx.sede.id, monto=1000, origen="turno",
                fecha=dt.datetime(2026, 7, 11, 2, 30, tzinfo=dt.timezone.utc)))
    db.commit()
    assert [d["fecha"] for d in _stats(client, ctx)["por_dia"]] == ["2026-07-10"]


def test_est_los_filtros_de_periodo_cambian_los_datos(client, db, armar_empresa):
    ctx = armar_empresa()
    for dia, monto in ((5, 1000), (20, 2000)):
        db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=ctx.sede.id, monto=monto,
                    origen="turno", fecha=dt.datetime(2026, 7, dia, 15, tzinfo=dt.timezone.utc)))
    db.commit()
    a = _stats(client, ctx, dt.datetime(2026, 7, 1, 3, tzinfo=dt.timezone.utc),
               dt.datetime(2026, 7, 11, 3, tzinfo=dt.timezone.utc))
    b = _stats(client, ctx, dt.datetime(2026, 7, 11, 3, tzinfo=dt.timezone.utc),
               dt.datetime(2026, 8, 1, 3, tzinfo=dt.timezone.utc))
    assert (a["facturado_real"], b["facturado_real"]) == (1000, 2000)
    assert b["facturado_anterior"] == 1000 or b["facturado_anterior"] == 1000.0


def test_est_cupones_facturado_es_plata_real(client, db, armar_empresa):
    """[BUG] «Facturado» de cupones era importe × (1 − %), una estimación,
    aunque el turno no se hubiera cobrado nunca."""
    from app.models.cupon import CuponDescuento

    ctx = armar_empresa()
    c = CuponDescuento(empresa_id=ctx.empresa.id, codigo="X10", tipo="porcentaje", valor=10)
    db.add(c)
    db.flush()
    t = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)
    t.cupon_id = c.id
    t.descuento_pct = 10
    db.commit()
    st = _stats(client, ctx, INICIO - dt.timedelta(days=1), INICIO + dt.timedelta(days=1))
    assert st["por_cupon"][0]["facturado"] == 0  # nadie lo cobró todavía


# ══════════════════════════════════════════════════════════════════════
# Baja de profesional: la historia no se pierde
# ══════════════════════════════════════════════════════════════════════

def test_baja_de_profesional_conserva_ingresos_historicos(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)
    db.commit()
    _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}])
    r = client.patch(f"/equipo/usuarios/{ctx.profesional.id}", headers=token_de(ctx.dueno),
                     json={"activo": False})
    assert r.status_code == 200, r.text
    r = client.delete(f"/recursos/{ctx.lucas.id}", headers=token_de(ctx.dueno))
    assert r.status_code in (200, 204), r.text
    st = _stats(client, ctx)
    assert st["por_profesional"][0]["recurso"] == "Lucas Estrella"
    assert st["facturado_real"] == 10000


# ══════════════════════════════════════════════════════════════════════
# Casos borde del cobro
# ══════════════════════════════════════════════════════════════════════

def test_cobro_parcial_deja_saldo_y_se_completa_despues(client, db, armar_empresa):
    """Antes un cobro de menos marcaba el turno como cobrado y la diferencia
    se perdía sin rastro. Ahora queda el saldo a la vista."""
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.commit()
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 6000}]).status_code == 201
    r = client.get(f"/turnos/{t.id}", headers=token_de(ctx.dueno)).json()
    assert (r["cobrado"], r["saldo"], r["pagado_total"]) == (False, 4000, 6000)
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 4000}]).status_code == 201
    r = client.get(f"/turnos/{t.id}", headers=token_de(ctx.dueno)).json()
    assert (r["cobrado"], r["saldo"]) == (True, 0)


def test_servicio_sin_precio_el_cobro_define_el_precio(client, db, armar_empresa):
    """Consulta de precio variable: el cobro fija el importe del turno, así
    turno, caja y estadísticas dicen lo mismo."""
    ctx = armar_empresa()
    t = _turno(db, ctx, importe=None)
    db.commit()
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 12500}]).status_code == 201
    r = client.get(f"/turnos/{t.id}", headers=token_de(ctx.dueno)).json()
    assert (r["total"], r["saldo"], r["cobrado"]) == (12500, 0, True)


def test_turno_con_sena_cobra_solo_el_saldo(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=t.sucursal_id, turno_id=t.id,
                cliente_id=ctx.cliente.id, monto=3000, origen="sena"))
    db.commit()
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]).status_code == 422
    assert _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id, "monto": 7000}]).status_code == 201
    st = _stats(client, ctx)
    assert st["facturado_turnos"] == 10000


def test_turno_senado_se_puede_reprogramar_y_cancelar(client, db, armar_empresa):
    """La seña no traba la agenda: se puede mover y, por la política de seña
    no reembolsable, cancelar (la seña queda como ingreso)."""
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=t.sucursal_id, turno_id=t.id,
                cliente_id=ctx.cliente.id, monto=3000, origen="sena"))
    db.commit()
    r = client.patch(f"/turnos/{t.id}/mover", headers=token_de(ctx.dueno),
                     json={"fecha_inicio": "2026-07-12T15:00:00Z"})
    assert r.status_code == 200
    r = client.patch(f"/turnos/{t.id}/estado", headers=token_de(ctx.dueno), json={"estado": "cancelado"})
    assert r.status_code == 200


def test_anular_venta_de_gift_card_desde_caja_la_da_de_baja(client, db, armar_empresa):
    """Antes se anulaba el movimiento y la tarjeta seguía ACTIVA con saldo:
    el cliente la usaba gratis."""
    ctx = armar_empresa()
    db.commit()
    _abrir_caja(client, ctx)
    gc = _vender_gc(client, ctx, 20000)
    g = db.get(GiftCard, gc["id"])
    r = client.post(f"/movimientos/{g.movimiento_id}/anular", headers=token_de(ctx.dueno), json={})
    assert r.status_code == 200, r.text
    db.refresh(g)
    assert g.estado.value == "anulada" and float(g.saldo) == 0


def test_descuento_no_puede_quedar_debajo_de_la_sena(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.add(Pago(empresa_id=ctx.empresa.id, sucursal_id=t.sucursal_id, turno_id=t.id,
                cliente_id=ctx.cliente.id, monto=8000, origen="sena"))
    db.commit()
    r = client.patch(f"/turnos/{t.id}/descuento", headers=token_de(ctx.dueno),
                     json={"descuento_pct": 50})
    assert r.status_code == 409


def test_linea_con_metodo_y_gift_card_a_la_vez_se_rechaza(client, db, armar_empresa):
    ctx = armar_empresa()
    t = _turno(db, ctx)
    db.commit()
    r = _cobrar(client, ctx, t.id, [{"metodo_pago_id": ctx.metodo.id,
                                     "gift_card_codigo": "GIFT-AAAA-BBBB", "monto": 100}])
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════
# Producción: la URL de los avisos de Mercado Pago no puede ser localhost
# ══════════════════════════════════════════════════════════════════════

def test_produccion_no_levanta_con_urls_locales():
    """Con API_BASE_URL=localhost la notification_url de MP apunta a la
    máquina local: los avisos no llegan y las señas no entran a la caja."""
    from app.core.config import Settings

    base = dict(env="prod", secret_key="s" * 40, fernet_key="f" * 40,
                cors_origins="https://turnos360.com.ar",
                public_base_url="https://turnos360.com.ar")
    with pytest.raises(ValueError, match="API_BASE_URL"):
        Settings(_env_file=None, api_base_url="http://localhost:8000", **base)
    assert Settings(_env_file=None, api_base_url="https://api.turnos360.com.ar", **base)
