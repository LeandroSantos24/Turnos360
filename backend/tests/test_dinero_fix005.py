"""Regresión del fix-005: la plata.

La auditoría encontró que los 59 tests que había no tocaban NADA de dinero:
ni cobros, ni caja, ni arqueo, ni la idempotencia de la seña. Estos tests
cubren eso, que es lo único del sistema que no se puede deshacer.
"""

import datetime as dt

import pytest
from sqlalchemy import func, select

from app.models.enums import EstadoTurno, TipoMovimiento
from app.models.finanzas import MetodoPago, Pago
from app.models.turno import Turno

from .conftest import token_de


def _crear_turno(db, ctx, *, importe=10000.0, estado=EstadoTurno.FINALIZADO) -> Turno:
    inicio = dt.datetime(2026, 7, 10, 15, 0, tzinfo=dt.timezone.utc)
    turno = Turno(
        empresa_id=ctx.empresa.id,
        cliente_id=ctx.cliente.id,
        recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=estado,
        importe_previsto=importe,
    )
    db.add(turno)
    db.flush()
    return turno


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 4.1 — ALTO: cobrar dos veces creaba dos cobros
# ══════════════════════════════════════════════════════════════════════

def test_cobrar_dos_veces_el_mismo_turno_da_409(client, db, armar_empresa):
    """El segundo intento tiene que rebotar, no duplicar la plata."""
    ctx = armar_empresa()
    turno = _crear_turno(db, ctx)
    db.commit()

    cuerpo = {"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]}

    r1 = client.post(f"/turnos/{turno.id}/cobro", headers=token_de(ctx.dueno), json=cuerpo)
    assert r1.status_code == 201

    r2 = client.post(f"/turnos/{turno.id}/cobro", headers=token_de(ctx.dueno), json=cuerpo)
    assert r2.status_code == 409, (
        "Se pudo cobrar dos veces el mismo turno. La caja cierra con el doble "
        "y el duplicado no se puede anular desde la app."
    )


def test_el_cobro_duplicado_no_deja_dos_pagos(client, db, armar_empresa):
    ctx = armar_empresa()
    turno = _crear_turno(db, ctx)
    db.commit()

    cuerpo = {"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]}
    client.post(f"/turnos/{turno.id}/cobro", headers=token_de(ctx.dueno), json=cuerpo)
    client.post(f"/turnos/{turno.id}/cobro", headers=token_de(ctx.dueno), json=cuerpo)

    cantidad = db.scalar(
        select(func.count(Pago.id)).where(Pago.turno_id == turno.id)
    )
    assert cantidad == 1, f"Quedaron {cantidad} pagos para un solo turno."


def test_el_primer_cobro_sigue_funcionando_con_pago_dividido(client, db, armar_empresa):
    """La guarda no puede romper el camino normal, ni el pago dividido."""
    ctx = armar_empresa()
    transferencia = MetodoPago(
        empresa_id=ctx.empresa.id, nombre="Transferencia", comision_pct=0
    )
    db.add(transferencia)
    db.flush()
    turno = _crear_turno(db, ctx)
    db.commit()

    r = client.post(
        f"/turnos/{turno.id}/cobro",
        headers=token_de(ctx.dueno),
        json={
            "pagos": [
                {"metodo_pago_id": ctx.metodo.id, "monto": 6000},
                {"metodo_pago_id": transferencia.id, "monto": 4000},
            ]
        },
    )
    assert r.status_code == 201
    assert r.json()["total_cobrado"] == pytest.approx(10000)

    cantidad = db.scalar(select(func.count(Pago.id)).where(Pago.turno_id == turno.id))
    assert cantidad == 2, "El pago dividido tiene que dejar una fila por línea."


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 4.2 — ALTO: doble seña por carrera en el webhook
# ══════════════════════════════════════════════════════════════════════

def test_la_base_impide_dos_senas_para_el_mismo_turno(client, db, armar_empresa):
    """El índice único parcial es la única barrera real contra la carrera.

    El chequeo en Python es un SELECT seguido de un INSERT, y Mercado Pago
    reintenta las notificaciones EN PARALELO: dos avisos con 50 ms de
    diferencia pasaban los dos el SELECT. Acá se simula el caso extremo
    insertando directo, saltando la lógica de la aplicación.
    """
    from sqlalchemy.exc import IntegrityError

    ctx = armar_empresa()
    turno = _crear_turno(db, ctx, estado=EstadoTurno.CONFIRMADO)
    db.flush()

    db.add(
        Pago(
            empresa_id=ctx.empresa.id,
            turno_id=turno.id,
            cliente_id=ctx.cliente.id,
            monto=3000,
            origen="sena",
        )
    )
    db.flush()

    db.add(
        Pago(
            empresa_id=ctx.empresa.id,
            turno_id=turno.id,
            cliente_id=ctx.cliente.id,
            monto=3000,
            origen="sena",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_un_turno_puede_tener_sena_y_ademas_el_cobro_de_la_atencion(
    client, db, armar_empresa
):
    """El índice único es SOLO para origen='sena': no debe estorbar al resto."""
    ctx = armar_empresa()
    turno = _crear_turno(db, ctx, estado=EstadoTurno.CONFIRMADO)
    db.add(
        Pago(
            empresa_id=ctx.empresa.id,
            turno_id=turno.id,
            cliente_id=ctx.cliente.id,
            monto=3000,
            origen="sena",
        )
    )
    db.commit()

    r = client.post(
        f"/turnos/{turno.id}/cobro",
        headers=token_de(ctx.dueno),
        json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 7000}]},
    )
    assert r.status_code == 201, "La seña no puede impedir el cobro del turno."


# ══════════════════════════════════════════════════════════════════════
# El arqueo: el número que decide si alguien se lleva plata
# ══════════════════════════════════════════════════════════════════════

def test_el_arqueo_cuadra_con_efectivo_tarjeta_y_un_gasto(client, db, armar_empresa):
    """Un día completo, con los números calculados a mano.

    Apertura $10.000 en efectivo.
    Turno 1: $10.000 en efectivo.
    Turno 2: $20.000 con tarjeta al 3% -> comisión $600.
    Gasto:   $2.000 en efectivo.

    Efectivo esperado en el cajón = 10.000 + 10.000 - 2.000 = 18.000
    (la tarjeta NO está en el cajón: es la trampa clásica del arqueo)
    Saldo esperado total = 10.000 + 30.000 - 2.000 = 38.000
    Comisiones = 600
    """
    ctx = armar_empresa()
    tarjeta = MetodoPago(empresa_id=ctx.empresa.id, nombre="Tarjeta", comision_pct=3)
    db.add(tarjeta)
    db.flush()
    t1 = _crear_turno(db, ctx, importe=10000)
    t2 = _crear_turno(db, ctx, importe=20000)
    db.commit()

    cab = token_de(ctx.dueno)

    r = client.post("/caja/abrir", headers=cab, json={"saldo_inicial": 10000})
    assert r.status_code == 201

    assert client.post(
        f"/turnos/{t1.id}/cobro", headers=cab,
        json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]},
    ).status_code == 201

    assert client.post(
        f"/turnos/{t2.id}/cobro", headers=cab,
        json={"pagos": [{"metodo_pago_id": tarjeta.id, "monto": 20000}]},
    ).status_code == 201

    assert client.post(
        "/gastos", headers=cab,
        json={"concepto": "Insumos", "monto": 2000, "metodo_pago_id": ctx.metodo.id},
    ).status_code == 201

    # Cerramos contando exactamente el efectivo esperado: tiene que cuadrar.
    r = client.post("/caja/cerrar", headers=cab, json={"saldo_real": 18000})
    assert r.status_code == 200
    d = r.json()

    assert d["total_ingresos"] == pytest.approx(30000)
    assert d["total_egresos"] == pytest.approx(2000)
    assert d["saldo_esperado"] == pytest.approx(38000)
    assert d["total_comisiones"] == pytest.approx(600)
    assert d["total_neto"] == pytest.approx(29400)
    assert d["efectivo_esperado"] == pytest.approx(18000), (
        "El efectivo esperado tiene que contar SOLO lo que entró en efectivo. "
        "Si mete la tarjeta, el arqueo no cuadra nunca."
    )


def test_el_arqueo_reporta_la_diferencia_cuando_falta_plata(client, db, armar_empresa):
    """Si faltan $500 en el cajón, el cierre lo tiene que decir."""
    ctx = armar_empresa()
    turno = _crear_turno(db, ctx, importe=10000)
    db.commit()
    cab = token_de(ctx.dueno)

    client.post("/caja/abrir", headers=cab, json={"saldo_inicial": 0})
    client.post(
        f"/turnos/{turno.id}/cobro", headers=cab,
        json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 10000}]},
    )

    r = client.post("/caja/cerrar", headers=cab, json={"saldo_real": 9500})
    assert r.status_code == 200
    assert r.json()["diferencia"] == pytest.approx(-500)


def test_no_se_pueden_abrir_dos_cajas_a_la_vez(client, db, armar_empresa):
    ctx = armar_empresa()
    db.commit()
    cab = token_de(ctx.dueno)

    assert client.post("/caja/abrir", headers=cab, json={"saldo_inicial": 0}).status_code == 201
    assert client.post("/caja/abrir", headers=cab, json={"saldo_inicial": 0}).status_code == 409


# ══════════════════════════════════════════════════════════════════════
# El webhook sigue siendo idempotente después de sacarlo del event loop
# ══════════════════════════════════════════════════════════════════════

def test_el_movimiento_del_cobro_queda_asociado_a_la_caja_abierta(
    client, db, armar_empresa
):
    """Si el cobro no entra a la caja, el arqueo del día no cierra."""
    from app.models.finanzas import MovimientoFinanciero

    ctx = armar_empresa()
    turno = _crear_turno(db, ctx, importe=5000)
    db.commit()
    cab = token_de(ctx.dueno)

    r = client.post("/caja/abrir", headers=cab, json={"saldo_inicial": 0})
    caja_id = r.json()["id"]

    client.post(
        f"/turnos/{turno.id}/cobro", headers=cab,
        json={"pagos": [{"metodo_pago_id": ctx.metodo.id, "monto": 5000}]},
    )

    mov = db.scalar(
        select(MovimientoFinanciero).where(
            MovimientoFinanciero.empresa_id == ctx.empresa.id,
            MovimientoFinanciero.tipo == TipoMovimiento.INGRESO,
        )
    )
    assert mov is not None
    assert mov.caja_id == caja_id
