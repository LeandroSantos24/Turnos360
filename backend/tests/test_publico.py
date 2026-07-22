"""Flujo público (sin login): vidriera, reserva online y webhook de Mercado Pago.

Incluye las dos protecciones del webhook que agregamos en el pre-deploy:
idempotencia (los reintentos de MP no vuelven a consultar la API) y el cruce
de tenant (un pago no puede marcar la seña de un turno de otra empresa).
"""

import datetime as dt

from app.models import Cliente
from app.models.enums import EstadoTurno
from app.models.turno import Turno


def _maniana_a_las(hora: int) -> dt.datetime:
    # Aware (UTC): los horarios y turnos se guardan con zona horaria, y la
    # disponibilidad no puede comparar naive contra aware.
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).replace(
        hour=hora, minute=0, second=0, microsecond=0
    )


def _payload(ctx, hora: int, nombre="Ana Gomez", telefono="2615550001"):
    return {
        "servicio_id": ctx.servicio.id,
        "recurso_id": ctx.lucas.id,
        "inicio": _maniana_a_las(hora).isoformat(),
        "cliente": {
            "nombre": nombre,
            "telefono": telefono,
            "email": "ana@example.com",
        },
    }


def test_vidriera_responde_y_pausada_da_404(client, db, armar_empresa):
    ctx = armar_empresa()
    ok = client.get(f"/publico/{ctx.empresa.slug}")
    assert ok.status_code == 200
    assert ok.json()["nombre"] == ctx.empresa.nombre

    assert client.get("/publico/slug-que-no-existe").status_code == 404

    ctx.empresa.activa = False
    db.flush()
    # Negocio pausado por el super-admin: su página pública desaparece.
    assert client.get(f"/publico/{ctx.empresa.slug}").status_code == 404


def test_reserva_crea_turno_pendiente(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json=_payload(ctx, 10))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "pendiente"

    turno = db.get(Turno, cuerpo["turno_id"])
    assert turno is not None
    assert turno.empresa_id == ctx.empresa.id
    assert turno.recurso_id == ctx.lucas.id


def test_matching_de_cliente_por_telefono_y_nombre(client, db, armar_empresa):
    """La regla de la ficha única: mismo teléfono + mismo nombre (normalizado)
    suman a la MISMA ficha; mismo teléfono con OTRO nombre es OTRA persona
    (el padre que reserva para el hijo con su número)."""
    ctx = armar_empresa()

    def clientes_de_la_empresa():
        return (
            db.query(Cliente).filter(Cliente.empresa_id == ctx.empresa.id).count()
        )

    antes = clientes_de_la_empresa()

    r1 = client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json=_payload(ctx, 10, nombre="Ana Gomez", telefono="2615550001"),
    )
    assert r1.status_code == 200
    assert clientes_de_la_empresa() == antes + 1

    # Misma persona (nombre con mayúsculas y espacios de más): NO crea otra ficha.
    r2 = client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json=_payload(ctx, 12, nombre="  ANA   gomez ", telefono="2615550001"),
    )
    assert r2.status_code == 200
    assert clientes_de_la_empresa() == antes + 1

    # Mismo teléfono pero otra persona: ficha nueva, no se pisan historiales.
    r3 = client.post(
        f"/publico/{ctx.empresa.slug}/reservar",
        json=_payload(ctx, 14, nombre="Pedro Gomez", telefono="2615550001"),
    )
    assert r3.status_code == 200
    assert clientes_de_la_empresa() == antes + 2


def test_reservar_con_profesional_que_no_hace_el_servicio(client, db, armar_empresa):
    ctx = armar_empresa()
    ctx.servicio.recursos.remove(ctx.pablo)
    db.flush()
    payload = _payload(ctx, 10)
    payload["recurso_id"] = ctx.pablo.id
    r = client.post(f"/publico/{ctx.empresa.slug}/reservar", json=payload)
    assert r.status_code == 400


def test_cupon_invalido_no_valida(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        f"/publico/{ctx.empresa.slug}/cupon/validar",
        json={"codigo": "NO-EXISTE", "servicio_id": ctx.servicio.id},
    )
    assert r.status_code == 200
    assert r.json()["valido"] is False


# ─── Webhook de Mercado Pago ─────────────────────────────────────────────


def _turno_con_sena(db, ctx, hora=16) -> Turno:
    inicio = _maniana_a_las(hora)
    turno = Turno(
        empresa_id=ctx.empresa.id,
        cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id,
        recurso_id=ctx.lucas.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=EstadoTurno.PENDIENTE,
        sena_estado="pendiente",
    )
    db.add(turno)
    db.flush()
    return turno


def test_webhook_mp_marca_la_sena_y_es_idempotente(
    client, db, armar_empresa, monkeypatch
):
    """El flujo bueno + la protección: MP reintenta la MISMA notificación
    varias veces; solo la primera debe costar una llamada a la API de MP."""
    ctx = armar_empresa()
    turno = _turno_con_sena(db, ctx)

    llamadas = {"n": 0}

    def consultar_falso(token, payment_id):
        llamadas["n"] += 1
        return {
            "id": payment_id,
            "status": "approved",
            "external_reference": str(turno.id),
        }

    monkeypatch.setattr("app.services.mercadopago.token_de", lambda emp: "TOKEN-TEST")
    monkeypatch.setattr(
        "app.services.mercadopago.consultar_pago", consultar_falso
    )

    url = f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=777"

    r1 = client.post(url)
    assert r1.status_code == 200
    db.refresh(turno)
    assert turno.sena_estado == "pagada"
    assert turno.estado == EstadoTurno.CONFIRMADO  # pagó la seña => confirmado
    assert turno.mp_payment_id == "777"
    assert llamadas["n"] == 1

    # Reintento de MP con el mismo payment_id: responde ok pero NO re-consulta.
    r2 = client.post(url)
    assert r2.status_code == 200
    assert llamadas["n"] == 1


def test_webhook_mp_no_cruza_empresas(client, db, armar_empresa, monkeypatch):
    """Un pago cuyo external_reference apunta a un turno de OTRA empresa no
    puede marcar nada: el webhook valida el tenant antes de tocar el turno."""
    ctx_a = armar_empresa("Empresa A")
    ctx_b = armar_empresa("Empresa B")
    turno_b = _turno_con_sena(db, ctx_b)

    monkeypatch.setattr("app.services.mercadopago.token_de", lambda emp: "TOKEN-TEST")
    monkeypatch.setattr(
        "app.services.mercadopago.consultar_pago",
        lambda token, pid: {
            "id": pid,
            "status": "approved",
            "external_reference": str(turno_b.id),
        },
    )

    # La notificación llega al slug de A, pero el pago referencia un turno de B.
    r = client.post(f"/publico/mp/webhook/{ctx_a.empresa.slug}?type=payment&data.id=888")
    assert r.status_code == 200  # a MP siempre se le responde ok

    db.refresh(turno_b)
    assert turno_b.sena_estado == "pendiente"  # intacto
    assert turno_b.mp_payment_id is None
