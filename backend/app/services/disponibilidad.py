"""Motor de disponibilidad (E2) — el corazón de la agenda.

Responde: ¿qué horarios libres tiene un recurso un día dado, para un servicio
de cierta duración? Cruza cuatro capas: horarios del recurso, excepciones
(bloqueos), duración + buffer del servicio, y turnos ya reservados.

NO escribe en la base: solo lee y calcula. El CRUD de turnos (E2-21) usa
estas funciones para validar antes de crear un turno.

Regla matemática central (solapamiento de intervalos):
    [ini_a, fin_a) y [ini_b, fin_b) se pisan si  ini_a < fin_b  Y  ini_b < fin_a.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExcepcionAgenda, HorarioRecurso, Servicio, Turno
from app.models.enums import EstadoTurno

# Estados que OCUPAN la agenda. Un turno cancelado o con ausencia libera el hueco.
ESTADOS_OCUPAN = (
    EstadoTurno.PENDIENTE,
    EstadoTurno.CONFIRMADO,
    EstadoTurno.EN_CURSO,
    EstadoTurno.FINALIZADO,
)


def hay_solapamiento(
    ini_a: dt.datetime, fin_a: dt.datetime,
    ini_b: dt.datetime, fin_b: dt.datetime,
) -> bool:
    """True si los intervalos [ini_a, fin_a) y [ini_b, fin_b) se pisan."""
    return ini_a < fin_b and ini_b < fin_a


def _fecha_bloqueada(
    db: Session, empresa_id: int, recurso_id: int, fecha: dt.date
) -> bool:
    """True si la fecha cae dentro de una excepción del recurso o de la empresa.

    Considera tanto las excepciones propias del recurso como las generales
    (recurso_id NULL = feriado de toda la empresa).
    """
    excepcion = db.scalar(
        select(ExcepcionAgenda).where(
            ExcepcionAgenda.empresa_id == empresa_id,
            ExcepcionAgenda.fecha_desde <= fecha,
            ExcepcionAgenda.fecha_hasta >= fecha,
            # del recurso O general (NULL)
            (ExcepcionAgenda.recurso_id == recurso_id)
            | (ExcepcionAgenda.recurso_id.is_(None)),
        )
    )
    return excepcion is not None


def _franjas_del_dia(
    db: Session, empresa_id: int, recurso_id: int, fecha: dt.date
) -> list[tuple[dt.time, dt.time]]:
    """Devuelve las franjas horarias del recurso para el día de la semana dado,
    respetando la vigencia (vigencia_desde/hasta) si está definida."""
    dia_semana = fecha.weekday()  # 0=lunes … 6=domingo (igual que nuestro modelo)
    horarios = db.scalars(
        select(HorarioRecurso).where(
            HorarioRecurso.empresa_id == empresa_id,
            HorarioRecurso.recurso_id == recurso_id,
            HorarioRecurso.dia_semana == dia_semana,
        )
    )
    franjas = []
    for h in horarios:
        if h.vigencia_desde and fecha < h.vigencia_desde:
            continue
        if h.vigencia_hasta and fecha > h.vigencia_hasta:
            continue
        franjas.append((h.hora_desde, h.hora_hasta))
    return sorted(franjas)


def _turnos_ocupados(
    db: Session, empresa_id: int, recurso_id: int, fecha: dt.date
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Intervalos [inicio, fin) de los turnos que ocupan al recurso ese día."""
    inicio_dia = dt.datetime.combine(fecha, dt.time.min, tzinfo=dt.timezone.utc)
    fin_dia = inicio_dia + dt.timedelta(days=1)
    turnos = db.scalars(
        select(Turno).where(
            Turno.empresa_id == empresa_id,
            Turno.recurso_id == recurso_id,
            Turno.estado.in_(ESTADOS_OCUPAN),
            Turno.fecha_inicio >= inicio_dia,
            Turno.fecha_inicio < fin_dia,
        )
    )
    return [(t.fecha_inicio, t.fecha_fin) for t in turnos if t.fecha_inicio and t.fecha_fin]


def calcular_huecos(
    db: Session,
    empresa_id: int,
    recurso_id: int,
    fecha: dt.date,
    duracion_min: int,
    *,
    buffer_min: int = 0,
    paso_min: int = 15,
) -> list[dt.datetime]:
    """Devuelve los horarios de INICIO posibles para un turno ese día.

    Un horario es válido si:
    - cae dentro de una franja de trabajo del recurso,
    - el turno completo (duración + buffer) entra en la franja,
    - no se pisa con ningún turno ya ocupado.

    paso_min: cada cuántos minutos se ofrecen turnos (15 = :00, :15, :30, :45).
    """
    # Día bloqueado por excepción → sin huecos
    if _fecha_bloqueada(db, empresa_id, recurso_id, fecha):
        return []

    franjas = _franjas_del_dia(db, empresa_id, recurso_id, fecha)
    if not franjas:
        return []

    ocupados = _turnos_ocupados(db, empresa_id, recurso_id, fecha)
    total_min = duracion_min + buffer_min
    huecos: list[dt.datetime] = []

    for hora_desde, hora_hasta in franjas:
        inicio = dt.datetime.combine(fecha, hora_desde, tzinfo=dt.timezone.utc)
        limite = dt.datetime.combine(fecha, hora_hasta, tzinfo=dt.timezone.utc)

        # Avanzo en pasos dentro de la franja
        actual = inicio
        while actual + dt.timedelta(minutes=total_min) <= limite:
            fin = actual + dt.timedelta(minutes=duracion_min)
            # ¿Choca con algún turno ocupado?
            choca = any(
                hay_solapamiento(actual, fin, ini_o, fin_o)
                for ini_o, fin_o in ocupados
            )
            if not choca:
                huecos.append(actual)
            actual += dt.timedelta(minutes=paso_min)

    return huecos


def esta_disponible(
    db: Session,
    empresa_id: int,
    recurso_id: int,
    inicio: dt.datetime,
    fin: dt.datetime,
    *,
    excluir_turno_id: int | None = None,
) -> bool:
    """¿Puede reservarse un turno [inicio, fin) en este recurso? (validación exacta).

    La usa el CRUD de turnos antes de crear/mover. Chequea bloqueos, que entre
    en una franja de trabajo, y que no se pise con otro turno.

    excluir_turno_id: al MOVER un turno, se excluye a sí mismo del chequeo
    (si no, chocaría consigo mismo).
    """
    fecha = inicio.date()

    # 1. Día bloqueado
    if _fecha_bloqueada(db, empresa_id, recurso_id, fecha):
        return False

    # 2. ¿Entra dentro de alguna franja de trabajo?
    dentro_de_franja = False
    for hora_desde, hora_hasta in _franjas_del_dia(db, empresa_id, recurso_id, fecha):
        ini_franja = dt.datetime.combine(fecha, hora_desde, tzinfo=dt.timezone.utc)
        fin_franja = dt.datetime.combine(fecha, hora_hasta, tzinfo=dt.timezone.utc)
        if inicio >= ini_franja and fin <= fin_franja:
            dentro_de_franja = True
            break
    if not dentro_de_franja:
        return False

    # 3. ¿Choca con un turno ya ocupado? (excluyendo el propio si se está moviendo)
    for ini_o, fin_o in _turnos_ocupados(db, empresa_id, recurso_id, fecha):
        # nota: _turnos_ocupados no filtra por id; el filtro de exclusión va acá
        if excluir_turno_id is not None:
            turno_o = db.scalar(
                select(Turno).where(
                    Turno.fecha_inicio == ini_o,
                    Turno.recurso_id == recurso_id,
                    Turno.empresa_id == empresa_id,
                )
            )
            if turno_o and turno_o.id == excluir_turno_id:
                continue
        if hay_solapamiento(inicio, fin, ini_o, fin_o):
            return False

    return True