"""Regresión del fix-022: la silla doble y la seña que nunca vencía.

EL TEST QUE IMPORTA es `test_dos_personas_no_pueden_quedarse_con_la_misma_silla`:
levanta DOS conexiones de verdad a Postgres, las sincroniza con una barrera
para que confirmen en el mismo instante, y exige que solo una se quede con el
horario.

Contra el código anterior ese test da "las dos reservaron" en el 100% de las
corridas. No es una carrera improbable: la vidriera es pública, y un negocio
que publica «a las 20:00 abrimos los turnos del sábado» tiene diez personas
apretando el botón en el mismo segundo.
"""

import datetime as dt
import threading
import uuid

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.candados import bloquear_agenda
from app.core.config import settings
from app.core.reloj import ahora_de_pared
from app.db.session import engine
from app.models import Cliente, Empresa, Recurso, Rubro, Turno
from app.models.agenda import HorarioRecurso, Servicio
from app.models.enums import EstadoTurno, TipoRecurso
from app.schemas.turno import TurnoCrear
from app.services import turno as turno_svc
from app.tasks import agenda as tareas_agenda


def _dentro_de(dias: int, hora: int = 10) -> dt.datetime:
    """Una fecha futura a una hora FIJA del día.

    A propósito no se usa `ahora_de_pared() + N días` a secas: corriendo la
    suite a las 23:44, un turno de 30 minutos cruzaba la medianoche, se salía
    de la franja horaria del recurso y el test fallaba por un motivo que no
    tenía nada que ver con lo que estaba probando. Un test que solo falla de
    madrugada es peor que no tenerlo.
    """
    base = ahora_de_pared() + dt.timedelta(days=dias)
    return base.replace(hour=hora, minute=0, second=0, microsecond=0)


# ══════════════════════════════════════════════════════════════════════════
#  1. La carrera de verdad, con dos conexiones a Postgres
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def negocio_real():
    """Una empresa COMMITEADA, para que dos conexiones distintas la vean.

    El resto de la suite corre dentro de una transacción que se revierte, y
    eso acá no sirve: dos conexiones separadas no ven lo que la otra no
    commiteó. Por eso este fixture escribe de verdad y limpia al final.
    """
    s = uuid.uuid4().hex[:8]
    ses = Session(bind=engine)
    rubro = Rubro(codigo=f"race-{s}", nombre="Carrera", preset={})
    ses.add(rubro)
    ses.flush()
    emp = Empresa(nombre="Carrera", slug=f"race-{s}", rubro_id=rubro.id)
    ses.add(emp)
    ses.flush()
    recurso = Recurso(empresa_id=emp.id, nombre="Silla 1", tipo=TipoRecurso.PERSONA)
    ses.add(recurso)
    ses.flush()
    servicio = Servicio(empresa_id=emp.id, nombre="Corte", duracion_min=30, precio=1000)
    ses.add(servicio)
    ses.flush()
    servicio.recursos.append(recurso)
    for dia in range(7):
        ses.add(HorarioRecurso(
            empresa_id=emp.id, recurso_id=recurso.id, dia_semana=dia,
            hora_desde=dt.time(0, 0), hora_hasta=dt.time(23, 59),
        ))
    ana = Cliente(empresa_id=emp.id, nombre="Ana", telefono="1111")
    beto = Cliente(empresa_id=emp.id, nombre="Beto", telefono="2222")
    ses.add_all([ana, beto])
    ses.commit()

    datos = {
        "empresa_id": emp.id, "recurso_id": recurso.id, "servicio_id": servicio.id,
        "ana_id": ana.id, "beto_id": beto.id, "rubro_id": rubro.id,
    }
    ses.close()

    try:
        yield datos
    finally:
        limpiar = Session(bind=engine)
        eid = datos["empresa_id"]
        limpiar.execute(delete(Turno).where(Turno.empresa_id == eid))
        limpiar.execute(HorarioRecurso.__table__.delete().where(HorarioRecurso.empresa_id == eid))
        limpiar.execute(
            Servicio.__table__.metadata.tables["servicio_recurso"].delete().where(
                text("servicio_id = :sid").bindparams(sid=datos["servicio_id"])
            )
        )
        limpiar.execute(delete(Servicio).where(Servicio.empresa_id == eid))
        limpiar.execute(delete(Cliente).where(Cliente.empresa_id == eid))
        limpiar.execute(delete(Recurso).where(Recurso.empresa_id == eid))
        limpiar.execute(delete(Empresa).where(Empresa.id == eid))
        limpiar.execute(delete(Rubro).where(Rubro.id == datos["rubro_id"]))
        limpiar.commit()
        limpiar.close()


def _correr_carrera(datos, cuando) -> dict:
    """Dos reservas para el mismo hueco, largando exactamente juntas."""
    barrera = threading.Barrier(2)
    resultado: dict[str, str] = {}

    def reservar(quien: str, cliente_id: int):
        ses = Session(bind=engine)
        try:
            barrera.wait(timeout=10)
            turno_svc.crear(
                ses, datos["empresa_id"],
                TurnoCrear(
                    cliente_id=cliente_id,
                    recurso_id=datos["recurso_id"],
                    servicio_id=datos["servicio_id"],
                    fecha_inicio=cuando,
                ),
            )
            resultado[quien] = "reservó"
        except Exception as e:
            resultado[quien] = f"rechazada: {type(e).__name__}"
        finally:
            ses.close()

    hilos = [
        threading.Thread(target=reservar, args=("ana", datos["ana_id"])),
        threading.Thread(target=reservar, args=("beto", datos["beto_id"])),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    return resultado


@pytest.mark.parametrize("intento", range(3))
def test_dos_personas_no_pueden_quedarse_con_la_misma_silla(negocio_real, intento):
    """EL test del fix.

    Antes: las dos reservaban, las dos recibían "tu turno quedó reservado", y
    el barbero se enteraba cuando aparecían las dos a las 15:00.

    Se repite tres veces porque una carrera que se gana por casualidad una vez
    no prueba nada.
    """
    cuando = _dentro_de(3, hora=10 + intento)

    resultado = _correr_carrera(negocio_real, cuando)

    assert len(resultado) == 2, f"algún hilo no terminó: {resultado}"
    ganadores = [q for q, r in resultado.items() if r == "reservó"]
    assert len(ganadores) == 1, f"se quedaron las dos con la silla: {resultado}"

    # Y en la base tiene que haber UN turno, no dos.
    ses = Session(bind=engine)
    cuantos = len(ses.scalars(
        select(Turno).where(
            Turno.empresa_id == negocio_real["empresa_id"],
            Turno.fecha_inicio == cuando,
        )
    ).all())
    ses.close()
    assert cuantos == 1, f"quedaron {cuantos} turnos en el mismo horario"


def test_dos_reservas_de_horarios_distintos_no_se_estorban(negocio_real):
    """El candado no puede convertirse en una fila de a uno.

    Si trabara de más, un negocio con movimiento tendría a todos esperando
    por reservas que no compiten entre sí.
    """
    base = _dentro_de(5)
    barrera = threading.Barrier(2)
    resultado: dict[str, str] = {}

    def reservar(quien, cliente_id, cuando):
        ses = Session(bind=engine)
        try:
            barrera.wait(timeout=10)
            turno_svc.crear(
                ses, negocio_real["empresa_id"],
                TurnoCrear(
                    cliente_id=cliente_id, recurso_id=negocio_real["recurso_id"],
                    servicio_id=negocio_real["servicio_id"], fecha_inicio=cuando,
                ),
            )
            resultado[quien] = "reservó"
        except Exception as e:
            resultado[quien] = f"rechazada: {e}"
        finally:
            ses.close()

    hilos = [
        threading.Thread(target=reservar, args=("ana", negocio_real["ana_id"], base)),
        threading.Thread(
            target=reservar,
            args=("beto", negocio_real["beto_id"], base + dt.timedelta(hours=2)),
        ),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)

    assert resultado == {"ana": "reservó", "beto": "reservó"}, resultado


# ══════════════════════════════════════════════════════════════════════════
#  2. El candado, por dentro
# ══════════════════════════════════════════════════════════════════════════


def test_el_candado_bloquea_al_segundo_que_llega(db):
    """Semántica del candado, sin hilos: determinista."""
    otra = Session(bind=engine)
    try:
        bloquear_agenda(db, 424242, 7)

        libre = otra.scalar(text("SELECT pg_try_advisory_xact_lock(424242, 7)"))
        assert libre is False, "el segundo pudo entrar igual"

        # Otro recurso de la misma empresa NO está trabado.
        otro_recurso = otra.scalar(text("SELECT pg_try_advisory_xact_lock(424242, 8)"))
        assert otro_recurso is True

        # Ni el mismo recurso de otra empresa.
        otra.rollback()
        otra_empresa = otra.scalar(text("SELECT pg_try_advisory_xact_lock(424243, 7)"))
        assert otra_empresa is True
    finally:
        otra.rollback()
        otra.close()


def test_el_candado_se_suelta_solo_al_terminar_la_transaccion(db):
    """Es la razón de usar un lock de transacción y no uno de sesión: no hay
    forma de olvidarse de liberarlo."""
    suelta = Session(bind=engine)
    try:
        suelta.execute(text("SELECT pg_advisory_xact_lock(515151, 3)"))
        assert db.scalar(text("SELECT pg_try_advisory_xact_lock(515151, 3)")) is False
        suelta.rollback()          # se termina la transacción, sin desbloquear a mano
        db.rollback()
        assert db.scalar(text("SELECT pg_try_advisory_xact_lock(515151, 3)")) is True
    finally:
        suelta.close()
        db.rollback()


def _espia_orden(monkeypatch) -> list[str]:
    """Anota en qué orden se llama al candado y al motor."""
    orden: list[str] = []

    real_lock = turno_svc.bloquear_agenda
    real_disp = turno_svc.disp.esta_disponible

    def lock(db, empresa_id, recurso_id):
        orden.append(f"candado({empresa_id},{recurso_id})")
        return real_lock(db, empresa_id, recurso_id)

    def disponible(*a, **k):
        orden.append("motor")
        return real_disp(*a, **k)

    monkeypatch.setattr(turno_svc, "bloquear_agenda", lock)
    monkeypatch.setattr(turno_svc.disp, "esta_disponible", disponible)
    return orden


def test_al_crear_el_candado_va_ANTES_de_preguntar(db, armar_empresa, monkeypatch):
    """Trabar después de consultar no sirve para nada: la carrera ya pasó."""
    ctx = armar_empresa()
    orden = _espia_orden(monkeypatch)

    turno_svc.crear(db, ctx.empresa.id, TurnoCrear(
        cliente_id=ctx.cliente.id, recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        fecha_inicio=_dentro_de(2),
    ))

    assert orden[0] == f"candado({ctx.empresa.id},{ctx.lucas.id})", orden
    assert "motor" in orden and orden.index("motor") > 0


def test_al_mover_el_candado_tambien_va_antes(db, armar_empresa, monkeypatch):
    from types import SimpleNamespace

    ctx = armar_empresa()
    turno = turno_svc.crear(db, ctx.empresa.id, TurnoCrear(
        cliente_id=ctx.cliente.id, recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        fecha_inicio=_dentro_de(2),
    ))
    orden = _espia_orden(monkeypatch)

    turno_svc.mover(db, ctx.empresa.id, turno.id, SimpleNamespace(
        fecha_inicio=_dentro_de(3), recurso_id=ctx.pablo.id,
    ))

    assert orden[0] == f"candado({ctx.empresa.id},{ctx.pablo.id})", orden


# ══════════════════════════════════════════════════════════════════════════
#  3. La seña que no se paga suelta el horario
# ══════════════════════════════════════════════════════════════════════════


def _reserva_con_sena(db, ctx, *, hace_minutos: int, cuando=None) -> Turno:
    turno = Turno(
        empresa_id=ctx.empresa.id, recurso_id=ctx.lucas.id, cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id, estado=EstadoTurno.PENDIENTE,
        sena_estado="pendiente", sena_monto=5000,
        fecha_inicio=cuando or _dentro_de(2),
        fecha_fin=(cuando or _dentro_de(2)) + dt.timedelta(minutes=30),
        creado_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=hace_minutos),
    )
    db.add(turno)
    db.flush()
    return turno


@pytest.fixture()
def barrer(db, monkeypatch):
    class SesionDelTest:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            db.flush()
            return False

    monkeypatch.setattr(tareas_agenda, "SessionLocal", SesionDelTest)
    return tareas_agenda.expirar_senas_pendientes


def test_una_sena_que_no_se_pago_suelta_el_horario(db, armar_empresa, barrer):
    """El horario quedaba tomado para siempre: no había nada que lo liberara."""
    ctx = armar_empresa()
    turno = _reserva_con_sena(db, ctx, hace_minutos=45)

    assert barrer() == 1
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO
    assert "seña no se pagó" in (turno.motivo_cancelacion or "")


def test_una_sena_recien_creada_NO_se_cancela(db, armar_empresa, barrer):
    """El cliente está pagando en este momento. Cancelarle la reserva mientras
    escribe el número de la tarjeta sería peor que el problema original."""
    ctx = armar_empresa()
    turno = _reserva_con_sena(db, ctx, hace_minutos=5)

    assert barrer() == 0
    db.refresh(turno)
    assert turno.estado == EstadoTurno.PENDIENTE


def test_un_turno_del_panel_JAMAS_se_cancela_solo(db, armar_empresa, barrer):
    """Los turnos que el dueño carga a mano también nacen en PENDIENTE.

    Si el barrido mirara solo el estado, le borraría la agenda al negocio
    entero. Por eso exige además que haya una seña impaga.
    """
    ctx = armar_empresa()
    turno = Turno(
        empresa_id=ctx.empresa.id, recurso_id=ctx.lucas.id, cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id, estado=EstadoTurno.PENDIENTE,
        sena_estado=None,
        fecha_inicio=_dentro_de(2),
        fecha_fin=_dentro_de(2) + dt.timedelta(minutes=30),
        creado_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10),
    )
    db.add(turno)
    db.flush()

    assert barrer() == 0
    db.refresh(turno)
    assert turno.estado == EstadoTurno.PENDIENTE


def test_una_sena_ya_pagada_no_se_toca(db, armar_empresa, barrer):
    ctx = armar_empresa()
    turno = _reserva_con_sena(db, ctx, hace_minutos=120)
    turno.sena_estado = "pagada"
    turno.estado = EstadoTurno.CONFIRMADO
    db.flush()

    assert barrer() == 0
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CONFIRMADO


def test_un_turno_que_ya_paso_no_se_reescribe(db, armar_empresa, barrer):
    """Un horario que ya pasó no le bloquea nada a nadie, y cancelarlo ahora
    solo ensuciaría el historial del negocio."""
    ctx = armar_empresa()
    turno = _reserva_con_sena(
        db, ctx, hace_minutos=120, cuando=_dentro_de(-1)
    )

    assert barrer() == 0
    db.refresh(turno)
    assert turno.estado == EstadoTurno.PENDIENTE


def test_el_plazo_es_configurable_y_en_cero_apaga_todo(
    db, armar_empresa, barrer, monkeypatch
):
    ctx = armar_empresa()
    _reserva_con_sena(db, ctx, hace_minutos=45)

    monkeypatch.setattr(settings, "sena_minutos_para_pagar", 0)
    assert barrer() == 0, "con el plazo en 0 no tiene que cancelar nada"

    monkeypatch.setattr(settings, "sena_minutos_para_pagar", 120)
    assert barrer() == 0, "45 minutos con un plazo de 120 no vence"

    monkeypatch.setattr(settings, "sena_minutos_para_pagar", 30)
    assert barrer() == 1


def test_el_horario_liberado_se_vuelve_a_poder_reservar(db, armar_empresa, barrer):
    """El punto de todo esto: que el negocio pueda vender ese hueco."""
    from app.services import disponibilidad as disp

    ctx = armar_empresa()
    cuando = _dentro_de(2)
    _reserva_con_sena(db, ctx, hace_minutos=45, cuando=cuando)

    ocupado = disp.esta_disponible(
        db, ctx.empresa.id, ctx.lucas.id, cuando, cuando + dt.timedelta(minutes=30)
    )
    assert ocupado is False, "el hueco tendría que estar tomado antes del barrido"

    barrer()

    libre = disp.esta_disponible(
        db, ctx.empresa.id, ctx.lucas.id, cuando, cuando + dt.timedelta(minutes=30)
    )
    assert libre is True, "el barrido canceló el turno pero el hueco sigue tomado"


def test_creado_at_se_llena_solo(db, armar_empresa):
    """Si la columna quedara en null, el barrido no vería nunca esos turnos."""
    ctx = armar_empresa()
    turno = turno_svc.crear(db, ctx.empresa.id, TurnoCrear(
        cliente_id=ctx.cliente.id, recurso_id=ctx.lucas.id,
        servicio_id=ctx.servicio.id,
        fecha_inicio=_dentro_de(2),
    ))
    db.refresh(turno)
    assert turno.creado_at is not None
    # Es un instante REAL en UTC, no la hora de pared: la diferencia contra
    # now(UTC) tiene que ser de segundos, no de tres horas.
    delta = abs((dt.datetime.now(dt.timezone.utc) - turno.creado_at).total_seconds())
    assert delta < 120, f"creado_at está a {delta}s de ahora: ¿mezclaron relojes?"


# ══════════════════════════════════════════════════════════════════════════
#  4. Un pago que llega tarde no revive el turno en silencio
# ══════════════════════════════════════════════════════════════════════════


def _webhook_de(client, db, ctx, turno, monkeypatch, payment_id="9001"):
    def consultar_falso(token, pid):
        return {
            "id": pid,
            "status": "approved",
            "external_reference": str(turno.id),
            "transaction_amount": 5000,
        }

    monkeypatch.setattr("app.services.mercadopago.token_de", lambda emp: "TOKEN-TEST")
    monkeypatch.setattr("app.services.mercadopago.consultar_pago", consultar_falso)
    return client.post(
        f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id={payment_id}"
    )


def test_un_pago_sobre_un_turno_cancelado_no_lo_revive(
    client, db, armar_empresa, monkeypatch, caplog
):
    """La secuencia real: la seña vence, el horario se libera y se vende a
    otra persona, y RECIÉN AHÍ llega el pago del primero.

    Confirmarlo sería crear la silla doble por la puerta de atrás. La plata
    entró igual —está en la cuenta del negocio— así que se registra, pero el
    turno queda cancelado y con una nota, y sale un WARNING en el log.
    """
    ctx = armar_empresa()
    ctx.empresa.activa = True
    turno = _reserva_con_sena(db, ctx, hace_minutos=90)
    turno.estado = EstadoTurno.CANCELADO
    turno.motivo_cancelacion = "La seña no se pagó dentro de los 30 minutos."
    db.flush()

    with caplog.at_level("WARNING"):
        r = _webhook_de(client, db, ctx, turno, monkeypatch)

    assert r.status_code == 200
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO, "revivió un turno ya cancelado"
    assert turno.sena_estado == "pagada", "la plata entró y no quedó registrada"
    assert "OJO" in (turno.motivo_cancelacion or ""), "el negocio no ve que entró plata"
    assert "ya no está vigente" in caplog.text


def test_un_pago_sobre_un_turno_vigente_lo_confirma_como_siempre(
    client, db, armar_empresa, monkeypatch
):
    """El control de arriba no puede haber roto el camino normal."""
    ctx = armar_empresa()
    ctx.empresa.activa = True
    turno = _reserva_con_sena(db, ctx, hace_minutos=5)
    db.flush()

    r = _webhook_de(client, db, ctx, turno, monkeypatch, payment_id="9002")

    assert r.status_code == 200
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CONFIRMADO
    assert turno.sena_estado == "pagada"
    assert "OJO" not in (turno.motivo_cancelacion or "")
