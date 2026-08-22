"""Tareas de fondo de la agenda.

Hoy hay una sola: soltar los horarios que quedaron tomados por una seña que
nunca se pagó.
"""

import datetime as dt
import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.core.config import settings
from app.core.reloj import ahora_de_pared
from app.db.session import SessionLocal
from app.models import Turno
from app.models.enums import EstadoTurno

log = logging.getLogger("turnos360.agenda")


@celery_app.task(name="app.tasks.agenda.expirar_senas_pendientes")
def expirar_senas_pendientes() -> int:
    """Cancela las reservas que pidieron seña y no la pagaron a tiempo.

    POR QUÉ EXISTE
    --------------
    Una reserva con seña queda en PENDIENTE y OCUPA la agenda desde el
    segundo cero. Si el cliente cierra Mercado Pago sin pagar, ese horario
    queda tomado para siempre: no había nada que lo soltara. El negocio ve un
    turno que nadie va a venir a cumplir y un horario que no puede vender.

    Y como `/publico/{slug}/reservar` no pide login, eso también era la forma
    más barata de llenarle la agenda a un negocio desde afuera.

    QUÉ CANCELA Y QUÉ NO
    --------------------
    Solo turnos que pidieron seña y siguen impagos (`sena_estado ==
    "pendiente"`). Un turno que el dueño cargó a mano desde el panel también
    nace en PENDIENTE — cancelar esos automáticamente sería borrarle la
    agenda al negocio.

    Tampoco toca turnos que ya empezaron: no se reescribe el pasado. Un
    horario que ya pasó no le bloquea nada a nadie.

    SOBRE EL RELOJ
    --------------
    `creado_at` lo escribe Postgres con `now()`: es un INSTANTE real en UTC,
    no la "hora de pared" con la que trabaja el motor de agenda. Por eso acá
    se compara contra `datetime.now(timezone.utc)` y no contra
    `ahora_de_pared()` — son dos relojes distintos y mezclarlos daría tres
    horas de error, que es exactamente el bug que arreglamos en el fix-021.
    """
    minutos = int(settings.sena_minutos_para_pagar)
    if minutos <= 0:
        return 0

    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutos)
    canceladas = 0

    with SessionLocal() as db:
        turnos = db.scalars(
            select(Turno).where(
                Turno.estado == EstadoTurno.PENDIENTE,
                Turno.sena_estado == "pendiente",
                Turno.creado_at < limite,
                # Solo los que todavía no empezaron: el pasado no se toca.
                Turno.fecha_inicio > ahora_de_pared(),
            )
        ).all()

        for turno in turnos:
            turno.estado = EstadoTurno.CANCELADO
            turno.motivo_cancelacion = (
                f"La seña no se pagó dentro de los {minutos} minutos. "
                "El horario se liberó automáticamente."
            )
            canceladas += 1

        if canceladas:
            db.commit()
            log.info(
                "señas vencidas: horarios liberados",
                extra={"canceladas": canceladas, "minutos": minutos},
            )

    return canceladas
