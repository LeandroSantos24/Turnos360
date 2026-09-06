"""Qué pasa —y qué NO pasa— cuando una suscripción vence de verdad.

POR QUÉ ESTE ARCHIVO EXISTE
───────────────────────────
Hasta ahora, no pasaba nada. El panel le prometía al dueño «después de esa
fecha, la agenda y tu página dejan de estar disponibles» y el vencimiento no
tocaba absolutamente nada: una empresa podía dejar de pagar y seguir usando
todo para siempre. La prórroga era un plazo de gracia sobre un corte que no
existía, y el aviso era una amenaza vacía.

Que el corte exista es la mitad del asunto. La otra mitad —y es la que este
archivo cuida más— es que corte EXACTAMENTE una cosa:

  · se cortan las reservas nuevas por la página pública;
  · NO se cierra el panel (el dueño tiene que poder entrar, entre otras cosas
    a pagar: un sistema que te deja afuera cuando le debés plata te impide
    pagarle);
  · NO se cancelan los turnos ya tomados (son compromisos con clientes reales
    que no tienen nada que ver con esta deuda);
  · NO se toca ni un dato.

Y sobre todo: DURANTE LA PRÓRROGA NO SE CORTA NADA. Ese es el punto entero de
que la prórroga exista.
"""

import datetime as dt

from app.services.suscripcion import DIAS_PRORROGA
from tests.conftest import token_de


def _vencida_hace(db, ctx, dias: int):
    """Deja la empresa con el vencimiento `dias` días atrás, y sin prueba."""
    ctx.empresa.prueba_hasta = None
    ctx.empresa.plan = "inicial"
    ctx.empresa.suscripcion_vence = dt.date.today() - dt.timedelta(days=dias)
    db.commit()


_HORA = [9]


def _reservar(client, ctx, db=None, hora: int | None = None):
    """Intenta sacar un turno por la página pública, como un cliente final.

    La hora avanza sola en cada llamada: dos reservas seguidas en el mismo
    horario chocarían entre sí y el 409 se confundiría con el corte, que es
    justo lo que estos tests tienen que poder distinguir.
    """
    if hora is None:
        _HORA[0] = 9 if _HORA[0] >= 19 else _HORA[0] + 1
        hora = _HORA[0]
    inicio = dt.datetime.combine(
        dt.date.today() + dt.timedelta(days=1), dt.time(hora, 0)
    )
    return client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json={
            "servicio_id": ctx.servicio.id,
            "recurso_id": ctx.lucas.id,
            "inicio": inicio.isoformat(),
            "cliente": {
                "nombre": "Cliente Web",
                "telefono": "2615550000",
                "email": "cliente.web@example.com",
            },
        },
    )


# ══════════════════════════════════════════════════════════════════════
#  La prórroga sirve para algo
# ══════════════════════════════════════════════════════════════════════

def test_durante_la_prorroga_se_sigue_reservando_normal(client, db, armar_empresa):
    """ES EL PUNTO DE LA PRÓRROGA. Si acá se cortara, los días de gracia
    serían un texto en una pantalla y nada más."""
    ctx = armar_empresa()
    _vencida_hace(db, ctx, dias=DIAS_PRORROGA - 1)

    r = _reservar(client, ctx, db)
    assert r.status_code in (200, 201), (
        f"Dentro de la prórroga NO se corta nada. Vino {r.status_code}: {r.text[:200]}"
    )


def test_el_ultimo_dia_de_gracia_todavia_se_reserva(client, db, armar_empresa):
    """El borde exacto. Un error de un día acá le corta el servicio a alguien
    que todavía está en plazo — y es el tipo de error que nadie mira."""
    ctx = armar_empresa()
    _vencida_hace(db, ctx, dias=DIAS_PRORROGA)

    r = _reservar(client, ctx, db)
    assert r.status_code in (200, 201)


def test_pasada_la_prorroga_no_entran_turnos_nuevos(client, db, armar_empresa):
    ctx = armar_empresa()
    _vencida_hace(db, ctx, dias=DIAS_PRORROGA + 1)

    r = _reservar(client, ctx, db)
    assert r.status_code == 402
    # El mensaje es para el CLIENTE FINAL, que no tiene por qué enterarse de
    # que el negocio le debe plata a un proveedor suyo.
    detalle = r.json()["detail"].lower()
    assert "escribile" in detalle
    assert "suscripción" not in detalle and "pag" not in detalle.replace("página", "")


# ══════════════════════════════════════════════════════════════════════
#  Lo que el corte NO puede tocar
# ══════════════════════════════════════════════════════════════════════

def test_el_dueno_sigue_pudiendo_entrar_al_panel(client, db, armar_empresa):
    """UN SISTEMA QUE TE DEJA AFUERA CUANDO LE DEBÉS PLATA TE IMPIDE PAGARLE.

    Es el error más fácil de cometer al agregar un corte por falta de pago, y
    el más caro: el que quería regularizar no puede, y el que dudaba se va.
    """
    ctx = armar_empresa()
    _vencida_hace(db, ctx, dias=DIAS_PRORROGA + 30)

    assert client.get("/empresa/actual", headers=token_de(ctx.dueno)).status_code == 200
    assert (
        client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).status_code
        == 200
    ), "Sobre todo esta: es la pantalla donde paga."
    assert client.get("/turnos", headers=token_de(ctx.dueno)).status_code == 200


def test_la_pagina_publica_se_sigue_viendo(client, db, armar_empresa):
    """No se apaga la vidriera: el cliente final igual necesita el teléfono y
    la dirección. Apagarla lo castigaría a él por una deuda ajena."""
    ctx = armar_empresa()
    _vencida_hace(db, ctx, dias=DIAS_PRORROGA + 5)

    r = client.get(f"/publico/{ctx.empresa.slug}")
    assert r.status_code == 200
    datos = r.json()
    assert datos["nombre"] == ctx.empresa.nombre
    assert datos["reservas_abiertas"] is False, (
        "La página tiene que avisar que no se puede reservar, para no hacerle "
        "completar todo el formulario a alguien que va a chocar al final."
    )


def test_los_turnos_ya_tomados_no_se_tocan(client, db, armar_empresa):
    """El que sacó turno para mañana lo tiene. La deuda es del negocio con
    nosotros, no del cliente con nadie."""
    from app.models.turno import Turno
    from sqlalchemy import select

    ctx = armar_empresa()
    r = _reservar(client, ctx, db)
    assert r.status_code in (200, 201), r.text
    turno_id = r.json()["turno_id"]

    _vencida_hace(db, ctx, dias=DIAS_PRORROGA + 10)

    turno = db.scalar(select(Turno).where(Turno.id == turno_id))
    assert turno is not None, "El turno sigue existiendo."

    en_agenda = client.get("/turnos", headers=token_de(ctx.dueno))
    assert en_agenda.status_code == 200


def test_una_empresa_en_prueba_nunca_se_corta(client, db, armar_empresa):
    """Todavía no le toca pagar. Cortarle la página durante la prueba es la
    mejor forma de que no se quede."""
    ctx = armar_empresa()
    ctx.empresa.prueba_hasta = dt.date.today() + dt.timedelta(days=3)
    ctx.empresa.suscripcion_vence = dt.date.today() - dt.timedelta(days=90)
    db.commit()

    assert _reservar(client, ctx, db).status_code in (200, 201)


def test_una_cuenta_sin_vencimiento_no_se_corta(client, db, armar_empresa):
    """Un piloto bonificado no tiene fecha de vencimiento. Sin este caso, un
    `None` se leería como «venció hace mucho»."""
    ctx = armar_empresa()
    ctx.empresa.prueba_hasta = None
    ctx.empresa.suscripcion_vence = None
    db.commit()

    assert _reservar(client, ctx, db).status_code in (200, 201)


def test_pagar_reabre_las_reservas_en_el_acto(client, db, armar_empresa):
    """El circuito completo, que es lo que hay que poder confiar: si alguien
    paga, tiene que volver a funcionar sin que nadie toque nada más."""
    from app.services import cobranza

    ctx = armar_empresa()
    _vencida_hace(db, ctx, dias=DIAS_PRORROGA + 5)
    assert _reservar(client, ctx, db).status_code == 402

    cobranza.registrar_pago(
        db, ctx.empresa, monto=13900, metodo="debito_automatico", plan="inicial"
    )
    db.commit()

    assert _reservar(client, ctx, db).status_code in (200, 201)
