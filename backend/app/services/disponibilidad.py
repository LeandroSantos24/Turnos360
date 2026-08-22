"""Motor de disponibilidad (E2) — el corazón de la agenda.

Responde: ¿qué horarios libres tiene un recurso un día dado, para un servicio
de cierta duración? Cruza cuatro capas: horarios del recurso, excepciones
(bloqueos), duración + buffer del servicio, y turnos ya reservados.

NO escribe en la base: solo lee y calcula. El CRUD de turnos (E2-21) usa
estas funciones para validar antes de crear un turno.

Regla matemática central (solapamiento de intervalos):
    [ini_a, fin_a) y [ini_b, fin_b) se pisan si  ini_a < fin_b  Y  ini_b < fin_a.

Regla de carriles (grupo_agenda): dos turnos solo se bloquean si se pisan en el
tiempo Y comparten el mismo grupo_agenda. Servicios de grupos distintos conviven
a la misma hora (corte + tintura + barba en paralelo).
"""

import datetime as dt
from dataclasses import dataclass

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

# Una franja de trabajo tal como sale de la base, antes de aplicarle la
# vigencia: (hora_desde, hora_hasta, vigencia_desde, vigencia_hasta).
_Franja = tuple[dt.time, dt.time, dt.date | None, dt.date | None]
# Un turno que ocupa la agenda: (turno_id, inicio, fin, grupo_agenda).
_Ocupado = tuple[int, dt.datetime, dt.datetime, str | None]


def hay_solapamiento(
    ini_a: dt.datetime, fin_a: dt.datetime,
    ini_b: dt.datetime, fin_b: dt.datetime,
) -> bool:
    """True si los intervalos [ini_a, fin_a) y [ini_b, fin_b) se pisan."""
    return ini_a < fin_b and ini_b < fin_a


def _bloquean_entre_si(
    ini_a: dt.datetime, fin_a: dt.datetime, grupo_a: str | None,
    ini_b: dt.datetime, fin_b: dt.datetime, grupo_b: str | None,
) -> bool:
    """True si dos turnos se bloquean: se pisan en el tiempo Y comparten carril.

    Regla de carriles: servicios de grupos distintos conviven a la misma hora
    (corte + tintura + barba en paralelo). Solo chocan si están en el mismo
    grupo_agenda. Si alguno no tiene grupo (None), se comporta como antes:
    bloquea con cualquiera que se pise.
    """
    if not hay_solapamiento(ini_a, fin_a, ini_b, fin_b):
        return False
    # Si alguno no tiene grupo definido, bloquea (comportamiento conservador)
    if grupo_a is None or grupo_b is None:
        return True
    # Mismo grupo = mismo carril = se bloquean
    return grupo_a == grupo_b


def _fecha_bloqueada(
    db: Session,
    empresa_id: int,
    recurso_id: int,
    fecha: dt.date,
    agenda: "AgendaPrecargada | None" = None,
) -> bool:
    """True si la fecha cae dentro de una excepción del recurso o de la empresa.

    Considera tanto las excepciones propias del recurso como las generales
    (recurso_id NULL = feriado de toda la empresa).
    """
    if agenda is not None:
        agenda._verificar(recurso_id, fecha)
        for clave in (recurso_id, None):
            for desde, hasta in agenda.excepciones.get(clave, ()):
                if desde <= fecha <= hasta:
                    return True
        return False

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


def _aplicar_vigencia(
    crudas: "list[_Franja] | tuple[_Franja, ...]", fecha: dt.date
) -> list[tuple[dt.time, dt.time]]:
    """Descarta las franjas que todavía no rigen o que ya vencieron.

    Vive aparte a propósito: es la única regla del filtrado y la comparten los
    dos caminos (consultar y leer de la precarga). Si estuviera duplicada,
    alcanzaría con tocar una sola copia para que los dos caminos dejaran de
    dar la misma respuesta.
    """
    franjas = []
    for desde, hasta, vig_desde, vig_hasta in crudas:
        if vig_desde and fecha < vig_desde:
            continue
        if vig_hasta and fecha > vig_hasta:
            continue
        franjas.append((desde, hasta))
    return sorted(franjas)


def _franjas_del_dia(
    db: Session,
    empresa_id: int,
    recurso_id: int,
    fecha: dt.date,
    agenda: "AgendaPrecargada | None" = None,
) -> list[tuple[dt.time, dt.time]]:
    """Devuelve las franjas horarias del recurso para el día de la semana dado,
    respetando la vigencia (vigencia_desde/hasta) si está definida."""
    dia_semana = fecha.weekday()  # 0=lunes … 6=domingo (igual que nuestro modelo)

    if agenda is not None:
        agenda._verificar(recurso_id, fecha)
        return _aplicar_vigencia(agenda.horarios.get((recurso_id, dia_semana), ()), fecha)

    horarios = db.scalars(
        select(HorarioRecurso).where(
            HorarioRecurso.empresa_id == empresa_id,
            HorarioRecurso.recurso_id == recurso_id,
            HorarioRecurso.dia_semana == dia_semana,
        )
    )
    crudas: list[_Franja] = [
        (h.hora_desde, h.hora_hasta, h.vigencia_desde, h.vigencia_hasta)
        for h in horarios
    ]
    return _aplicar_vigencia(crudas, fecha)


def _turnos_ocupados(
    db: Session,
    empresa_id: int,
    recurso_id: int,
    fecha: dt.date,
    agenda: "AgendaPrecargada | None" = None,
) -> list[_Ocupado]:
    """Turnos que ocupan al recurso ese día: (id, inicio, fin, grupo_agenda).

    El grupo_agenda viene del servicio del turno: dos turnos solo se bloquean
    entre sí si comparten el mismo grupo (corte vs tintura vs barba son carriles
    paralelos que conviven). Un turno cuyo servicio no tiene grupo (None) bloquea
    con cualquiera (comportamiento clásico).

    Devuelve el id del turno porque quien excluye (al mover un turno) tiene que
    poder identificarlo sin adivinar: antes se lo buscaba por fecha_inicio, y
    con dos turnos que arrancan a la misma hora en carriles distintos —el caso
    normal de una peluquería— esa búsqueda devolvía cualquiera de los dos.

    Una sola consulta con LEFT JOIN al servicio: antes se hacía un db.get() por
    turno, y el endpoint público de horarios llegaba a cientos de consultas.
    """
    if agenda is not None:
        agenda._verificar(recurso_id, fecha)
        return list(agenda.turnos.get((recurso_id, fecha), ()))

    inicio_dia = dt.datetime.combine(fecha, dt.time.min, tzinfo=dt.timezone.utc)
    fin_dia = inicio_dia + dt.timedelta(days=1)
    filas = db.execute(
        select(Turno.id, Turno.fecha_inicio, Turno.fecha_fin, Servicio.grupo_agenda)
        .outerjoin(Servicio, Servicio.id == Turno.servicio_id)
        .where(
            Turno.empresa_id == empresa_id,
            Turno.recurso_id == recurso_id,
            Turno.estado.in_(ESTADOS_OCUPAN),
            Turno.fecha_inicio >= inicio_dia,
            Turno.fecha_inicio < fin_dia,
        )
    ).all()
    return [
        (tid, ini, fin, grupo)
        for tid, ini, fin, grupo in filas
        if ini and fin
    ]


def calcular_huecos(
    db: Session,
    empresa_id: int,
    recurso_id: int,
    fecha: dt.date,
    duracion_min: int,
    *,
    buffer_min: int = 0,
    paso_min: int = 15,
    grupo_agenda: str | None = None,
    agenda: "AgendaPrecargada | None" = None,
) -> list[dt.datetime]:
    """Devuelve los horarios de INICIO posibles para un turno ese día.

    Un horario es válido si:
    - cae dentro de una franja de trabajo del recurso,
    - el turno completo (duración + buffer) entra en la franja,
    - no se pisa con ningún turno ocupado del MISMO carril (grupo_agenda).

    paso_min: cada cuántos minutos se ofrecen turnos (15 = :00, :15, :30, :45).
    grupo_agenda: el carril del servicio que se está buscando. Solo se bloquea
    con turnos ocupados del mismo grupo.
    """
    # Día bloqueado por excepción → sin huecos
    if _fecha_bloqueada(db, empresa_id, recurso_id, fecha, agenda):
        return []

    franjas = _franjas_del_dia(db, empresa_id, recurso_id, fecha, agenda)
    if not franjas:
        return []

    ocupados = _turnos_ocupados(db, empresa_id, recurso_id, fecha, agenda)
    total_min = duracion_min + buffer_min
    huecos: list[dt.datetime] = []

    for hora_desde, hora_hasta in franjas:
        inicio = dt.datetime.combine(fecha, hora_desde, tzinfo=dt.timezone.utc)
        limite = dt.datetime.combine(fecha, hora_hasta, tzinfo=dt.timezone.utc)

        # Avanzo en pasos dentro de la franja
        actual = inicio
        while actual + dt.timedelta(minutes=total_min) <= limite:
            fin = actual + dt.timedelta(minutes=duracion_min)
            # ¿Choca con algún turno ocupado del mismo carril?
            choca = any(
                _bloquean_entre_si(actual, fin, grupo_agenda, ini_o, fin_o, grupo_o)
                for _id_o, ini_o, fin_o, grupo_o in ocupados
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
    grupo_agenda: str | None = None,
) -> bool:
    """¿Puede reservarse un turno [inicio, fin) en este recurso? (validación exacta).

    La usa el CRUD de turnos antes de crear/mover. Chequea bloqueos, que entre
    en una franja de trabajo, y que no se pise con otro turno del mismo carril.

    excluir_turno_id: al MOVER un turno, se excluye a sí mismo del chequeo
    (si no, chocaría consigo mismo).
    grupo_agenda: el carril del servicio del turno. Solo se bloquea con turnos
    ocupados del mismo grupo (corte vs tintura vs barba conviven).
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

    # 3. ¿Choca con un turno ya ocupado del mismo carril? (excluyendo el propio si se mueve)
    #    La exclusión es por id, directa. Antes se resolvía buscando un turno con
    #    la misma fecha_inicio: con dos turnos a la misma hora en carriles
    #    distintos, esa consulta devolvía uno cualquiera de los dos y el motor
    #    podía saltearse un choque real (o rechazar un movimiento válido).
    for id_o, ini_o, fin_o, grupo_o in _turnos_ocupados(db, empresa_id, recurso_id, fecha):
        if excluir_turno_id is not None and id_o == excluir_turno_id:
            continue
        if _bloquean_entre_si(inicio, fin, grupo_agenda, ini_o, fin_o, grupo_o):
            return False

    return True

# ══════════════════════════════════════════════════════════════════════════
#  Precarga: las mismas respuestas en 3 consultas en vez de cientos
# ══════════════════════════════════════════════════════════════════════════
#
# El motor está pensado para responder UNA pregunta: los huecos de UN recurso
# UN día. Eso son tres consultas (excepciones, horarios, turnos) y está bien.
#
# El problema es quién lo llama. La vidriera pública pide hasta 31 días para
# todos los profesionales que hacen el servicio. Con 8 profesionales eso es
# 31 × 8 = 248 llamadas × 3 consultas = 744 consultas para pintar UNA pantalla
# — la primera que ve un cliente, y la que decide si reserva o se va.
#
# La forma del problema no es "las consultas son lentas": cada una es
# instantánea. Es que son 744 idas y vueltas a Postgres, y ese costo fijo por
# viaje es el que se multiplica.
#
# La solución no es cachear ni adivinar: es traer de una sola vez la ventana
# completa y que el cálculo sea exactamente el mismo, sobre datos que ya están
# en memoria. Las tres consultas son las MISMAS tres, sin el filtro de día.
#
# POR QUÉ ESTO PODRÍA SALIR MAL Y CÓMO SE EVITA
# ----------------------------------------------
# Un motor que lee de un diccionario en vez de la base miente en silencio si
# le preguntan por un día que no precargó: el diccionario devuelve "no hay
# turnos" y el sistema ofrece un horario que en realidad está tomado. Por eso
# la precarga recuerda su ventana y **revienta** si le preguntan afuera. Es
# preferible un error visible a un sobreturno.


@dataclass(frozen=True)
class AgendaPrecargada:
    """Los mismos datos que consultaría el motor, para una ventana de días.

    Se arma con `precargar()` y se le pasa a `calcular_huecos(agenda=...)`.
    Sin ella el motor sigue funcionando igual que siempre, consultando.
    """

    desde: dt.date
    hasta: dt.date
    recursos: frozenset[int]
    # recurso_id (o None = feriado de toda la empresa) -> [(desde, hasta)]
    excepciones: dict[int | None, list[tuple[dt.date, dt.date]]]
    # (recurso_id, dia_semana) -> [(hora_desde, hora_hasta, vig_desde, vig_hasta)]
    horarios: dict[tuple[int, int], list[_Franja]]
    # (recurso_id, fecha) -> [(turno_id, inicio, fin, grupo_agenda)]
    turnos: dict[tuple[int, dt.date], list[_Ocupado]]

    def _verificar(self, recurso_id: int, fecha: dt.date) -> None:
        """Se pregunta por algo que no se precargó -> error, no silencio."""
        if not (self.desde <= fecha <= self.hasta):
            raise ValueError(
                f"La agenda precargada cubre del {self.desde} al {self.hasta} "
                f"y se preguntó por el {fecha}. Sin esto el motor devolvería "
                "'no hay nada reservado' y ofrecería un horario ya tomado."
            )
        if recurso_id not in self.recursos:
            raise ValueError(
                f"El recurso {recurso_id} no está en la agenda precargada. "
                "Mismo riesgo: contestaría que tiene el día entero libre."
            )


def precargar(
    db: Session,
    empresa_id: int,
    recurso_ids: list[int],
    desde: dt.date,
    hasta: dt.date,
) -> AgendaPrecargada:
    """Trae de una sola vez todo lo que el motor necesita para esa ventana.

    Tres consultas, sin importar cuántos días ni cuántos recursos.
    """
    recursos = frozenset(recurso_ids)
    if not recursos or hasta < desde:
        return AgendaPrecargada(desde, hasta, recursos, {}, {}, {})

    excepciones: dict[int | None, list[tuple[dt.date, dt.date]]] = {}
    for rid, d1, d2 in db.execute(
        select(
            ExcepcionAgenda.recurso_id,
            ExcepcionAgenda.fecha_desde,
            ExcepcionAgenda.fecha_hasta,
        ).where(
            ExcepcionAgenda.empresa_id == empresa_id,
            ExcepcionAgenda.fecha_desde <= hasta,
            ExcepcionAgenda.fecha_hasta >= desde,
            ExcepcionAgenda.recurso_id.in_(recursos)
            | ExcepcionAgenda.recurso_id.is_(None),
        )
    ).all():
        excepciones.setdefault(rid, []).append((d1, d2))

    horarios: dict[tuple[int, int], list[_Franja]] = {}
    for h in db.scalars(
        select(HorarioRecurso).where(
            HorarioRecurso.empresa_id == empresa_id,
            HorarioRecurso.recurso_id.in_(recursos),
        )
    ):
        horarios.setdefault((h.recurso_id, h.dia_semana), []).append(
            (h.hora_desde, h.hora_hasta, h.vigencia_desde, h.vigencia_hasta)
        )

    inicio = dt.datetime.combine(desde, dt.time.min, tzinfo=dt.timezone.utc)
    fin = dt.datetime.combine(hasta, dt.time.min, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
    turnos: dict[tuple[int, dt.date], list[_Ocupado]] = {}
    for rid, tid, ini, fin_t, grupo in db.execute(
        select(
            Turno.recurso_id,
            Turno.id,
            Turno.fecha_inicio,
            Turno.fecha_fin,
            Servicio.grupo_agenda,
        )
        .outerjoin(Servicio, Servicio.id == Turno.servicio_id)
        .where(
            Turno.empresa_id == empresa_id,
            Turno.recurso_id.in_(recursos),
            Turno.estado.in_(ESTADOS_OCUPAN),
            Turno.fecha_inicio >= inicio,
            Turno.fecha_inicio < fin,
        )
    ).all():
        if not ini or not fin_t:
            continue
        # Mismo criterio que la consulta por día: el turno cae en el día de su
        # fecha_inicio. Un turno que cruza la medianoche pertenece al día en
        # que empieza, igual que antes.
        turnos.setdefault((rid, ini.date()), []).append((tid, ini, fin_t, grupo))

    return AgendaPrecargada(desde, hasta, recursos, excepciones, horarios, turnos)
