"""Lo que necesitan las pestañas de «Mi suscripción» (pagos y actividad).

- Cada pago trae su id y la referencia REAL del cobro (id de Mercado Pago) o
  nada: el detalle no puede inventar un comprobante.
- Los pagos anulados no aparecen.
- La pestaña Actividad muestra más que los 12 eventos del resumen de antes.
"""

import datetime as dt

from app.models import AjusteSuscripcion, PagoSuscripcion, Usuario
from app.models.enums import RolUsuario

from .conftest import token_de


def _dueno(db, ctx):
    return db.query(Usuario).filter_by(empresa_id=ctx.empresa.id, rol=RolUsuario.DUENO).one()


def test_los_pagos_traen_id_y_referencia_real(client, db, armar_empresa):
    ctx = armar_empresa()
    hoy = dt.date.today()
    mp = PagoSuscripcion(
        empresa_id=ctx.empresa.id, fecha=hoy, monto=19990, metodo="mercadopago",
        tipo="renovacion", plan="pro", mp_payment_id="123456789",
    )
    transf = PagoSuscripcion(
        empresa_id=ctx.empresa.id, fecha=hoy - dt.timedelta(days=30), monto=19990,
        metodo="transferencia", tipo="alta", plan="pro", notas="nota interna",
    )
    anulado = PagoSuscripcion(
        empresa_id=ctx.empresa.id, fecha=hoy, monto=1, metodo="transferencia", anulado=True,
    )
    db.add_all([mp, transf, anulado])
    db.commit()

    r = client.get("/empresa/mi-suscripcion", headers=token_de(_dueno(db, ctx)))
    assert r.status_code == 200
    pagos = {p["id"]: p for p in r.json()["pagos"]}

    assert set(pagos) == {mp.id, transf.id}, "Los anulados no se listan."
    assert pagos[mp.id]["referencia"] == "Mercado Pago #123456789"
    assert pagos[transf.id]["referencia"] is None
    assert all(p["estado"] == "aprobado" for p in pagos.values())
    assert "notas" not in pagos[transf.id]


def test_la_actividad_trae_mas_que_doce_eventos(client, db, armar_empresa):
    ctx = armar_empresa()
    for i in range(20):
        db.add(AjusteSuscripcion(
            empresa_id=ctx.empresa.id, tipo="plan", detalle=f"cambio {i}", actor_tipo="admin",
        ))
    db.commit()

    r = client.get("/empresa/mi-suscripcion", headers=token_de(_dueno(db, ctx)))
    assert r.status_code == 200
    assert len(r.json()["actividad"]) == 20
