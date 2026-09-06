"""Los dos agujeros del circuito de la seña que encontró la auditoría.

Los dos son de la misma familia: el turno y el link de pago se desincronizaban,
y en los dos casos el que perdía era alguien que había hecho todo bien.

  1. SEÑA SIN LINK. `crear_preferencia` devuelve None sin levantar —el negocio
     activó las señas y todavía no conectó su Mercado Pago, o la API falló—, y
     el turno quedaba con «seña pendiente» y ninguna forma de pagarla. Media
     hora después el barrido lo cancelaba. Al cliente se le había dicho «tu
     turno quedó solicitado».

  2. LINK SIN VENCIMIENTO. El turno se cancela a los 30 minutos; el link de
     Checkout Pro seguía pagable para siempre. El cliente volvía al día
     siguiente, pagaba, y el negocio se quedaba con plata de alguien que ya no
     tenía turno —y el horario vendido a otro—.

El primero es el más caro de los dos y no necesita que falle nada: alcanza con
que un dueño prenda las señas antes de pegar el token. Ese negocio perdía el
100 % de sus reservas web, de a una, en silencio.
"""

import datetime as dt


from app.core.config import settings
from app.models.enums import EstadoTurno
from app.models.turno import Turno
from app.services import mercadopago as mp


def _payload(ctx, hora=11):
    inicio = dt.datetime.combine(
        dt.date.today() + dt.timedelta(days=1), dt.time(hora, 0)
    )
    return {
        "servicio_id": ctx.servicio.id,
        "recurso_id": ctx.lucas.id,
        "inicio": inicio.isoformat(),
        "cliente": {
            "nombre": "Ana Web",
            "telefono": "2615551234",
            "email": "ana.web@example.com",
        },
    }


def _con_senas(db, ctx, monto=2000):
    ctx.empresa.cobro_modo = "sena"
    ctx.empresa.sena_activa = True
    ctx.empresa.sena_monto = monto
    db.commit()


# ══════════════════════════════════════════════════════════════════════
#  1. Nunca una seña que no se pueda pagar
# ══════════════════════════════════════════════════════════════════════

def test_sin_mercado_pago_conectado_el_turno_no_queda_con_sena_pendiente(
    client, db, armar_empresa, monkeypatch
):
    """EL caso caro, y el que no necesita que falle nada.

    El dueño prende las señas y todavía no pegó su Access Token. Antes: cada
    reserva quedaba con seña pendiente, sin link, y se cancelaba sola a la
    media hora. El negocio perdía todas las reservas web sin ver un error.
    """
    ctx = armar_empresa()
    _con_senas(db, ctx)
    # Sin token, `crear_preferencia` corta al principio y devuelve None.
    monkeypatch.setattr(mp, "token_de", lambda _e: None)

    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json=_payload(ctx))
    assert r.status_code in (200, 201), r.text

    turno = db.get(Turno, r.json()["turno_id"])
    db.refresh(turno)
    assert turno.sena_estado is None, (
        "Sin link de pago no puede quedar una seña pendiente: el barrido la "
        "cancela a los 30 minutos y el cliente nunca supo que tenía que pagar."
    )
    assert turno.sena_monto is None
    assert r.json().get("pago_url") in (None, "")


def test_si_mercado_pago_falla_tampoco(client, db, armar_empresa, monkeypatch):
    """Mismo desenlace por otra causa: la API de MP contestó mal."""
    ctx = armar_empresa()
    _con_senas(db, ctx)
    monkeypatch.setattr(mp, "crear_preferencia", lambda *a, **k: None)

    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json=_payload(ctx, 12))
    assert r.status_code in (200, 201), r.text

    turno = db.get(Turno, r.json()["turno_id"])
    db.refresh(turno)
    assert turno.sena_estado is None
    assert turno.sena_monto is None


def test_el_turno_sin_link_sobrevive_al_barrido_de_senas(
    client, db, armar_empresa, monkeypatch
):
    """La consecuencia de verdad, verificada de punta a punta.

    No alcanza con que los campos queden en None: lo que importa es que el
    turno SIGA VIVO después de que corra el barrido. Es lo único que el
    negocio nota.
    """
    from app.tasks import agenda as tarea

    ctx = armar_empresa()
    _con_senas(db, ctx)
    monkeypatch.setattr(mp, "token_de", lambda _e: None)

    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json=_payload(ctx, 13))
    turno_id = r.json()["turno_id"]

    # Lo envejecemos más allá de la ventana de pago.
    turno = db.get(Turno, turno_id)
    turno.creado_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        minutes=int(settings.sena_minutos_para_pagar) + 10
    )
    db.commit()

    from contextlib import contextmanager

    @contextmanager
    def _sesion():
        yield db

    monkeypatch.setattr(tarea, "SessionLocal", _sesion)
    tarea.expirar_senas_pendientes()

    db.refresh(turno)
    assert turno.estado != EstadoTurno.CANCELADO, (
        "El turno se canceló solo por una seña que nunca se le pudo cobrar."
    )


def test_con_mercado_pago_andando_la_sena_sigue_quedando_pendiente(
    client, db, armar_empresa, monkeypatch
):
    """El control del control: si el arreglo borrara la seña SIEMPRE, los
    tests de arriba pasarían y el circuito de cobro no existiría más."""
    ctx = armar_empresa()
    _con_senas(db, ctx)
    monkeypatch.setattr(
        mp, "crear_preferencia", lambda *a, **k: "https://mp.test/checkout/abc"
    )

    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json=_payload(ctx, 14))
    assert r.json()["pago_url"] == "https://mp.test/checkout/abc"

    turno = db.get(Turno, r.json()["turno_id"])
    db.refresh(turno)
    assert turno.sena_estado == "pendiente"
    assert float(turno.sena_monto) == 2000


# ══════════════════════════════════════════════════════════════════════
#  2. El link vence cuando vence el turno
# ══════════════════════════════════════════════════════════════════════

def _preferencia_enviada(monkeypatch) -> dict:
    """Intercepta el POST a Mercado Pago y devuelve el payload que se mandó."""
    capturado: dict = {}

    class _Respuesta:
        def raise_for_status(self):
            return None

        def json(self):
            return {"init_point": "https://mp.test/checkout/abc"}

    def _post(url, json=None, headers=None, timeout=None):
        capturado.update(json or {})
        return _Respuesta()

    monkeypatch.setattr(mp.httpx, "post", _post)
    return capturado


def test_la_preferencia_vence_junto_con_el_turno(db, armar_empresa, monkeypatch):
    """Sin esto, el cliente vuelve mañana al link viejo y paga un turno que ya
    se canceló y se le vendió a otro."""
    ctx = armar_empresa()
    _con_senas(db, ctx)
    monkeypatch.setattr(mp, "token_de", lambda _e: "TOKEN-DE-PRUEBA")

    turno = Turno(
        empresa_id=ctx.empresa.id,
        sucursal_id=ctx.sede.id,
        recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        cliente_id=ctx.cliente.id,
        fecha_inicio=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
        fecha_fin=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1, minutes=30),
        estado=EstadoTurno.PENDIENTE,
        sena_monto=2000,
    )
    db.add(turno)
    db.flush()

    enviado = _preferencia_enviada(monkeypatch)
    assert mp.crear_preferencia(ctx.empresa, turno, "Seña") is not None

    assert enviado.get("expires") is True, "La preferencia no vence nunca."

    desde = dt.datetime.fromisoformat(enviado["expiration_date_from"])
    hasta = dt.datetime.fromisoformat(enviado["expiration_date_to"])
    ventana = (hasta - desde).total_seconds() / 60

    minutos = int(settings.sena_minutos_para_pagar)
    assert minutos <= ventana <= minutos + 10, (
        f"El link vive {ventana:.0f} min y el turno se cancela a los {minutos}. "
        "Si el link dura más, se puede pagar un turno que ya no existe; si "
        "dura menos, se rechaza un pago que llegó a horario."
    )


def test_no_se_ofrecen_medios_de_pago_que_tardan_dias(db, armar_empresa, monkeypatch):
    """Rapipago y los cajeros acreditan en uno a tres días; el turno se cancela
    en treinta minutos. El cliente hacía todo bien y perdía el turno igual."""
    ctx = armar_empresa()
    _con_senas(db, ctx)
    monkeypatch.setattr(mp, "token_de", lambda _e: "TOKEN-DE-PRUEBA")

    turno = Turno(
        empresa_id=ctx.empresa.id,
        sucursal_id=ctx.sede.id,
        recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        cliente_id=ctx.cliente.id,
        fecha_inicio=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
        fecha_fin=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1, minutes=30),
        estado=EstadoTurno.PENDIENTE,
        sena_monto=2000,
    )
    db.add(turno)
    db.flush()

    enviado = _preferencia_enviada(monkeypatch)
    mp.crear_preferencia(ctx.empresa, turno, "Seña")

    excluidos = {
        e["id"]
        for e in (enviado.get("payment_methods") or {}).get("excluded_payment_types", [])
    }
    assert {"ticket", "atm"} <= excluidos, (
        f"Se siguen ofreciendo medios offline: {excluidos}. Con una seña, el "
        "pago tiene que ser instantáneo o el turno se cancela antes de acreditar."
    )
