"""Regresión del fix-021: los recordatorios salían con tres horas de corrimiento.

EL BUG
------
El motor guarda "hora de pared etiquetada UTC": un turno de las 10:00 en
Mendoza se guarda como 10:00+00:00, sin convertir. Es una convención
deliberada y está documentada en tres lugares del repo.

El barrido que encola los recordatorios era el único lugar del sistema que no
la respetaba: comparaba contra `datetime.now(timezone.utc)`, tres horas
adelantado. Consecuencias medibles:

  · El recordatorio de "2 horas antes" se encolaba cuando faltaban CINCO, o
    sea entre las 3:30 y las 4:15 de la madrugada, con el texto "en un rato,
    a las 09:00".
  · El de 24 h salía 26-28 h antes.
  · Y como efecto de costado, un turno reservado con menos de ~26 h de
    anticipación no entraba nunca en la ventana: no recibía recordatorio jamás.

Los tests de recordatorios que ya existían llamaban a `enviar_recordatorio()`
directo, salteándose el cálculo de la ventana. Por eso nadie lo vio.
"""

import datetime as dt
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.reloj import ahora_de_pared, hoy_de_pared
from app.models import Mensaje, Turno
from app.models.enums import EstadoMensaje, EstadoTurno
from app.tasks import emails


# ══════════════════════════════════════════════════════════════════════════
#  1. El reloj compartido
# ══════════════════════════════════════════════════════════════════════════


def test_el_reloj_de_pared_no_es_utc_real():
    """Si esto empieza a fallar es porque alguien lo "simplificó" a now(UTC),
    y con eso vuelve todo el corrimiento."""
    pared = ahora_de_pared()
    utc = dt.datetime.now(dt.timezone.utc)
    diferencia = abs((utc - pared).total_seconds())
    offset = dt.datetime.now(ZoneInfo(settings.zona_horaria)).utcoffset()
    assert abs(diferencia - abs(offset.total_seconds())) < 5


def test_el_reloj_de_pared_se_etiqueta_utc():
    """La convención completa: la hora es local, la etiqueta es UTC. Sin la
    etiqueta, comparar contra una fecha de turno explota."""
    ahora = ahora_de_pared()
    assert ahora.tzinfo == dt.timezone.utc
    local = dt.datetime.now(ZoneInfo(settings.zona_horaria))
    assert ahora.hour == local.hour


def test_hoy_de_pared_es_el_dia_del_negocio():
    esperado = dt.datetime.now(ZoneInfo(settings.zona_horaria)).date()
    assert hoy_de_pared() == esperado


def test_la_vidriera_y_las_tareas_usan_EL_MISMO_reloj():
    """Una convención repetida en dos lugares se desincroniza. Este test fija
    que hay una sola función."""
    from app.services import publico

    assert publico._ahora_de_pared is ahora_de_pared


# ══════════════════════════════════════════════════════════════════════════
#  2. EL test: la ventana se calcula sobre la hora de pared
# ══════════════════════════════════════════════════════════════════════════


def _dentro_de(dias: int, hora: int = 10) -> dt.datetime:
    """Una fecha futura a una hora FIJA del día.

    A propósito no se usa `ahora_de_pared() + N días` a secas: corriendo la
    suite a las 23:50, un turno de 30 minutos cruzaba la medianoche y se
    salía de la franja horaria del recurso. El test fallaba por eso y no por
    lo que estaba probando.
    """
    base = ahora_de_pared() + dt.timedelta(days=dias)
    return base.replace(hour=hora, minute=0, second=0, microsecond=0)


def _turno_en(db, ctx, cuando: dt.datetime, estado=EstadoTurno.CONFIRMADO) -> Turno:
    t = Turno(
        empresa_id=ctx.empresa.id,
        recurso_id=ctx.lucas.id,
        cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id,
        estado=estado,
        fecha_inicio=cuando,
        fecha_fin=cuando + dt.timedelta(minutes=30),
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture()
def encolar(db, monkeypatch):
    """Corre el barrido contra la sesión del test y captura lo que encola."""
    encolados: list[tuple[str, int]] = []

    class Cola:
        def __init__(self, nombre):
            self.nombre = nombre

        def delay(self, turno_id):
            encolados.append((self.nombre, turno_id))

    monkeypatch.setattr(emails, "enviar_recordatorio", Cola("24h"))
    monkeypatch.setattr(emails, "enviar_recordatorio_2h", Cola("2h"))

    class SesionDelTest:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            db.flush()
            return False

    monkeypatch.setattr(emails, "SessionLocal", SesionDelTest)

    def correr():
        encolados.clear()
        emails.encolar_recordatorios()
        return encolados

    return correr


def _prender(db, empresa, *codigos):
    empresa.automatizaciones = {c: {"activa": True} for c in codigos}
    db.flush()


def test_el_recordatorio_de_2h_se_encola_cuando_faltan_2_horas(
    db, armar_empresa, encolar
):
    """EL test del fix.

    Con el bug, este turno se encolaba cuando faltaban CINCO horas: el cliente
    recibía "en un rato" mientras dormía. Y con la ventana calculada mal, a
    las 2 h reales ya no entraba.
    """
    ctx = armar_empresa()
    ctx.lucas = ctx.lucas
    _prender(db, ctx.empresa, "recordatorio_2h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(minutes=120))

    assert ("2h", turno.id) in encolar()


def test_a_cinco_horas_todavia_NO_se_encola(db, armar_empresa, encolar):
    """El otro lado del mismo bug: cinco horas antes era justo cuando el
    código viejo lo mandaba."""
    ctx = armar_empresa()
    _prender(db, ctx.empresa, "recordatorio_2h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(minutes=300))

    assert ("2h", turno.id) not in encolar()


def test_el_recordatorio_de_24h_se_encola_a_24_horas(db, armar_empresa, encolar):
    ctx = armar_empresa()
    _prender(db, ctx.empresa, "recordatorio_24h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24))

    assert ("24h", turno.id) in encolar()


def test_un_turno_reservado_para_dentro_de_25_horas_recibe_su_recordatorio(
    db, armar_empresa, encolar
):
    """El efecto de costado más silencioso del corrimiento.

    Con la ventana corrida a 26-28 h, un turno sacado con 25 h de
    anticipación no entraba NUNCA: para cuando el barrido lo miraba, ya había
    pasado de largo. El cliente no recibía recordatorio y nadie se enteraba
    de por qué.
    """
    ctx = armar_empresa()
    _prender(db, ctx.empresa, "recordatorio_24h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24, minutes=30))

    assert ("24h", turno.id) in encolar()


def test_a_27_horas_no_se_encola(db, armar_empresa, encolar):
    """Con el bug, esta era justo la hora a la que salía el de 24 h."""
    ctx = armar_empresa()
    _prender(db, ctx.empresa, "recordatorio_24h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=27))

    assert ("24h", turno.id) not in encolar()


# ══════════════════════════════════════════════════════════════════════════
#  3. El flag ya no se quema con la campaña apagada
# ══════════════════════════════════════════════════════════════════════════


def test_con_la_campana_apagada_el_flag_NO_se_marca(db, armar_empresa, encolar):
    """El dueño prende la campaña y tiene que empezar a funcionar.

    Antes el flag se marcaba igual: todos los turnos que habían pasado por la
    ventana con el switch en off quedaban marcados para siempre. Prendía la
    campaña, "no funcionaba" durante el primer día, y no había ningún error
    que mirar.
    """
    ctx = armar_empresa()
    ctx.empresa.automatizaciones = {"recordatorio_24h": {"activa": False}}
    db.flush()
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24))

    assert encolar() == []
    db.refresh(turno)
    assert turno.recordatorio_enviado is False, "el flag se quemó con la campaña apagada"

    # Y ahora la prende: el mismo turno tiene que salir.
    _prender(db, ctx.empresa, "recordatorio_24h")
    assert ("24h", turno.id) in encolar()


def test_con_la_campana_de_2h_apagada_el_flag_tampoco_se_marca(
    db, armar_empresa, encolar
):
    """El mismo control para el segundo recordatorio.

    Lo agregué porque una mutación sobrevivió: había escrito el test solo
    para el de 24 h, así que el de 2 h se podía volver a romper sin que nada
    avisara. Es el que más se prende después, justamente.
    """
    ctx = armar_empresa()
    ctx.empresa.automatizaciones = {"recordatorio_2h": {"activa": False}}
    db.flush()
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(minutes=120))

    assert encolar() == []
    db.refresh(turno)
    assert turno.recordatorio_2h_enviado is False

    _prender(db, ctx.empresa, "recordatorio_2h")
    assert ("2h", turno.id) in encolar()


def test_con_la_campana_de_2h_prendida_no_se_repite(db, armar_empresa, encolar):
    ctx = armar_empresa()
    _prender(db, ctx.empresa, "recordatorio_2h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(minutes=120))

    assert ("2h", turno.id) in encolar()
    db.refresh(turno)
    assert turno.recordatorio_2h_enviado is True
    assert encolar() == []


def test_con_la_campana_prendida_el_flag_se_marca_y_no_se_repite(
    db, armar_empresa, encolar
):
    """La otra mitad: el flag tiene que seguir evitando el doble envío."""
    ctx = armar_empresa()
    _prender(db, ctx.empresa, "recordatorio_24h")
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24))

    assert ("24h", turno.id) in encolar()
    db.refresh(turno)
    assert turno.recordatorio_enviado is True
    assert encolar() == [], "el segundo barrido lo volvió a encolar"


# ══════════════════════════════════════════════════════════════════════════
#  4. Reprogramar devuelve el derecho al recordatorio
# ══════════════════════════════════════════════════════════════════════════


def test_al_mover_un_turno_vuelve_a_tener_recordatorio(db, armar_empresa):
    """Al turno que MÁS chance tiene de olvidarse —justo el que le cambiaron
    el horario— era al único que no le llegaba el aviso."""
    from types import SimpleNamespace

    from app.services import turno as turno_svc

    ctx = armar_empresa()
    turno = _turno_en(db, ctx, _dentro_de(2))
    turno.recordatorio_enviado = True
    turno.recordatorio_2h_enviado = True
    db.flush()

    turno_svc.mover(
        db,
        ctx.empresa.id,
        turno.id,
        SimpleNamespace(
            fecha_inicio=_dentro_de(4),
            recurso_id=None,
        ),
    )

    db.refresh(turno)
    assert turno.recordatorio_enviado is False
    assert turno.recordatorio_2h_enviado is False


def test_mover_un_turno_a_la_misma_hora_no_toca_los_flags(db, armar_empresa):
    """Cambiar solo el profesional no es motivo para volver a avisar."""
    from types import SimpleNamespace

    from app.services import turno as turno_svc

    ctx = armar_empresa()
    cuando = _dentro_de(2)
    turno = _turno_en(db, ctx, cuando)
    turno.recordatorio_enviado = True
    db.flush()

    turno_svc.mover(
        db, ctx.empresa.id, turno.id,
        SimpleNamespace(fecha_inicio=cuando, recurso_id=ctx.pablo.id),
    )

    db.refresh(turno)
    assert turno.recordatorio_enviado is True


# ══════════════════════════════════════════════════════════════════════════
#  5. Un turno cancelado no recibe "mañana tenés tu turno"
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("estado", [EstadoTurno.CANCELADO, EstadoTurno.AUSENTE])
@pytest.mark.parametrize("tarea", ["enviar_recordatorio", "enviar_recordatorio_2h"])
def test_un_turno_cancelado_no_recibe_recordatorio(
    db, armar_empresa, monkeypatch, estado, tarea
):
    """Entre que el barrido encola y el worker desagota pueden pasar minutos.

    Si en ese rato el cliente cancela, recibía igual "mañana tenés tu turno"
    — el peor mail posible, porque lo hace dudar de si la cancelación entró.
    """
    ctx = armar_empresa()
    ctx.cliente.email = "cliente@example.com"
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24), estado=estado)

    class SesionDelTest:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(emails, "SessionLocal", SesionDelTest)

    with patch.object(emails.mailer, "enviar") as enviar:
        getattr(emails, tarea)(turno.id)

    assert not enviar.called, f"le mandó un recordatorio a un turno {estado.value}"


@pytest.mark.parametrize("estado", [EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO])
def test_un_turno_vigente_SI_recibe_recordatorio(db, armar_empresa, monkeypatch, estado):
    """El control de arriba no puede haber apagado el caso normal."""
    ctx = armar_empresa()
    ctx.cliente.email = "cliente@example.com"
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24), estado=estado)

    class SesionDelTest:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(emails, "SessionLocal", SesionDelTest)

    with patch.object(emails.mailer, "enviar") as enviar:
        emails.enviar_recordatorio(turno.id)

    assert enviar.called


# ══════════════════════════════════════════════════════════════════════════
#  6. Un email que no sale deja rastro
# ══════════════════════════════════════════════════════════════════════════


def test_si_el_smtp_falla_queda_registrado_y_logueado(db, armar_empresa, monkeypatch, caplog):
    """Ninguna pantalla muestra los mensajes de canal EMAIL. Sin el log, un
    SMTP mal configurado quema los recordatorios de todo el mes y nadie se
    entera: el healthcheck sigue dando 200 y todo parece sano."""
    ctx = armar_empresa()
    ctx.cliente.email = "cliente@example.com"
    turno = _turno_en(db, ctx, ahora_de_pared() + dt.timedelta(hours=24))

    class SesionDelTest:
        def __enter__(self):
            return db

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(emails, "SessionLocal", SesionDelTest)

    def explotar(*_a, **_k):
        raise RuntimeError("SMTP no configurado")

    monkeypatch.setattr(emails.mailer, "enviar", explotar)

    with caplog.at_level("WARNING"):
        emails.enviar_recordatorio(turno.id)

    assert "email no enviado" in caplog.text

    msg = db.scalars(select(Mensaje).where(Mensaje.turno_id == turno.id)).first()
    assert msg is not None
    assert msg.estado == EstadoMensaje.FALLIDO


# ══════════════════════════════════════════════════════════════════════════
#  7. "Vence hoy" es hoy para el negocio, no para el servidor
# ══════════════════════════════════════════════════════════════════════════
#
# Estos tests usan dos zonas horarias que están 26 h separadas
# (Kiritimati UTC+14 y Etc/GMT+12 = UTC-12). A cualquier hora del día, la
# fecha en una es MAYOR que en la otra — nunca coinciden.
#
# Eso los hace deterministas: no dependen de a qué hora corra la suite. Con
# `date.today()` (la zona del servidor) las dos ramas darían el mismo
# resultado y alguna de las dos afirmaciones falla, sí o sí.

ADELANTE = "Pacific/Kiritimati"   # UTC+14
ATRAS = "Etc/GMT+12"              # UTC-12


def test_las_dos_zonas_del_test_siempre_caen_en_dias_distintos(monkeypatch):
    """Si esto fallara, los tres tests de abajo no probarían nada."""
    monkeypatch.setattr(settings, "zona_horaria", ADELANTE)
    adelante = hoy_de_pared()
    monkeypatch.setattr(settings, "zona_horaria", ATRAS)
    atras = hoy_de_pared()
    assert adelante > atras


def test_hoy_de_pared_sigue_la_zona_del_negocio(monkeypatch):
    monkeypatch.setattr(settings, "zona_horaria", ADELANTE)
    adelante = hoy_de_pared()
    monkeypatch.setattr(settings, "zona_horaria", ATRAS)
    assert hoy_de_pared() != adelante, "usó la zona del servidor, no la del negocio"


def test_un_cupon_que_vence_hoy_sirve_hasta_la_medianoche_del_negocio(
    db, armar_empresa, monkeypatch
):
    """A las 21:30 de Argentina el servidor (UTC) ya está en el día siguiente.

    Un cupón que vence hoy dejaba de andar tres horas antes de tiempo: el
    cliente lo pegaba, leía «el código venció», y el negocio perdía la venta
    sin enterarse nunca de por qué.
    """
    from app.models.cupon import CuponDescuento
    from app.services import cupones

    ctx = armar_empresa()

    monkeypatch.setattr(settings, "zona_horaria", ATRAS)
    vence = hoy_de_pared()          # el último día, visto desde la zona de atrás

    cupon = CuponDescuento(
        empresa_id=ctx.empresa.id, codigo="PRUEBA10", tipo="porcentaje",
        valor=10, activo=True, vence_el=vence, servicios_ids=[],
    )
    db.add(cupon)
    db.flush()

    # Para el negocio todavía es su último día: tiene que servir.
    encontrado, _desc, motivo = cupones.validar_cupon(db, ctx.empresa.id, "PRUEBA10", ctx.servicio.id)
    assert encontrado is not None, f"lo rechazó en su último día: {motivo}"

    # Y desde una zona que ya pasó de día, tiene que estar vencido.
    monkeypatch.setattr(settings, "zona_horaria", ADELANTE)
    encontrado, _desc, motivo = cupones.validar_cupon(db, ctx.empresa.id, "PRUEBA10", ctx.servicio.id)
    assert encontrado is None and "venc" in motivo.lower()


def test_una_giftcard_que_vence_hoy_vale_hasta_la_medianoche_del_negocio(monkeypatch):
    """Mismo borde que el cupón, y con más plata adentro: una gift card que
    el cliente compró y va a usar el último día."""
    from app.models.modulos.giftcards import GiftCard

    monkeypatch.setattr(settings, "zona_horaria", ATRAS)
    tarjeta = GiftCard(vence=hoy_de_pared())

    assert tarjeta.esta_vencida is False, "la venció en su último día"

    monkeypatch.setattr(settings, "zona_horaria", ADELANTE)
    assert tarjeta.esta_vencida is True


def test_la_vidriera_arranca_en_el_dia_del_negocio(client, db, armar_empresa, monkeypatch):
    """A las 21:30 de Argentina el servidor (UTC) ya está en el día siguiente:
    el cliente abría la página y le mostraba mañana sin pedirlo."""
    from app.routers import publico as router_publico

    ctx = armar_empresa()
    ctx.empresa.activa = True
    db.flush()

    visto = {}

    def espia(db_, slug, servicio_id, recurso_id, desde, dias):
        visto["desde"] = desde
        return []

    monkeypatch.setattr(router_publico.svc, "huecos", espia)

    for zona in (ATRAS, ADELANTE):
        monkeypatch.setattr(settings, "zona_horaria", zona)
        client.get(
            f"/publico/{ctx.empresa.slug}/horarios",
            params={"servicio_id": ctx.servicio.id},
        )
        assert visto["desde"] == hoy_de_pared(), (
            f"con la zona en {zona} arrancó en {visto['desde']} "
            f"y el día del negocio era {hoy_de_pared()}"
        )
