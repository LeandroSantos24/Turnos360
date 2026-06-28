"""Lógica de negocio de Turno (E2) — usa el motor de disponibilidad.

Al crear o mover un turno, se valida el hueco con esta_disponible() del motor
ANTES de guardar (salvo que sea sobreturno). Las transiciones de estado
siguen un flujo válido (no se puede finalizar un turno cancelado, etc.).

Regla 1: todo se filtra por empresa_id, igual que los demás services.
"""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cliente, Recurso, Servicio, Turno
from app.models.items import ItemTurno
from app.models.enums import EstadoTurno
from app.schemas.turno import TurnoCambiarEstado, TurnoCrear, TurnoMover
from app.services import disponibilidad as disp
from app.services import membresia as svc_membresia

# Transiciones de estado permitidas. Desde cada estado, a cuáles se puede pasar.
TRANSICIONES = {
    EstadoTurno.PENDIENTE: {EstadoTurno.CONFIRMADO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE},
    EstadoTurno.CONFIRMADO: {EstadoTurno.EN_CURSO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE},
    EstadoTurno.EN_CURSO: {EstadoTurno.FINALIZADO, EstadoTurno.CANCELADO},
    # Reapertura flexible (para corregir errores). Cuando haya roles, se
    # restringirá a que solo el dueño pueda hacer estas transiciones.
    EstadoTurno.FINALIZADO: {EstadoTurno.EN_CURSO, EstadoTurno.CONFIRMADO},
    EstadoTurno.CANCELADO: {EstadoTurno.CONFIRMADO, EstadoTurno.PENDIENTE},
    EstadoTurno.AUSENTE: set(),      # estado terminal
}

# Subconjunto de transiciones que un PROFESIONAL puede hacer en SUS turnos.
# Acotado al flujo de atención: empezar (en curso) y terminar (finalizado).
# Confirmar, cancelar, marcar ausente y reabrir quedan para recepción/dueño.
# (Si más adelante querés sumarle marcar AUSENTE, agregá EstadoTurno.AUSENTE acá.)
ESTADOS_PROFESIONAL = {EstadoTurno.EN_CURSO, EstadoTurno.FINALIZADO}


def _entidad_de_empresa(db, modelo, entidad_id: int, empresa_id: int):
    """Trae una entidad (Cliente/Recurso/Servicio) solo si es de esta empresa."""
    return db.scalar(
        select(modelo).where(modelo.id == entidad_id, modelo.empresa_id == empresa_id)
    )


def _resolver_nombres(db: Session, turno: Turno) -> Turno:
    """Adjunta cliente_nombre, recurso_nombre y servicio_nombre al objeto turno.

    No son columnas: los seteamos como atributos para que el schema TurnoOut
    los incluya en la respuesta (útil para pintar la agenda sin más consultas).
    """
    cliente = db.get(Cliente, turno.cliente_id)
    recurso = db.get(Recurso, turno.recurso_id)
    servicio = db.get(Servicio, turno.servicio_id) if turno.servicio_id else None
    turno.cliente_nombre = (
        f"{cliente.nombre} {cliente.apellido or ''}".strip() if cliente else None
    )
    turno.recurso_nombre = recurso.nombre if recurso else None
    turno.servicio_nombre = servicio.nombre if servicio else None
    turno.servicio_grupo = servicio.grupo_agenda if servicio else None
    return turno


def _total_con_items(turno: Turno, items_sum: float) -> float:
    """Total real del turno: (servicio + adicionales) con el descuento aplicado."""
    base = float(turno.importe_previsto or 0) + items_sum
    pct = float(turno.descuento_pct or 0)
    return round(base * (1 - pct / 100), 2)


def _setear_totales(db: Session, turnos: list[Turno]) -> None:
    """Suma los adicionales de cada turno en UNA query y setea turno.total."""
    if not turnos:
        return
    ids = [t.id for t in turnos]
    filas = db.execute(
        select(ItemTurno.turno_id, func.coalesce(func.sum(ItemTurno.precio * ItemTurno.cantidad), 0))
        .where(ItemTurno.turno_id.in_(ids))
        .group_by(ItemTurno.turno_id)
    ).all()
    sumas = {tid: float(s) for tid, s in filas}
    for t in turnos:
        t.total = _total_con_items(t, sumas.get(t.id, 0.0))


def listar(
    db: Session,
    empresa_id: int,
    *,
    recurso_id: int | None = None,
    cliente_id: int | None = None,
    desde: dt.datetime | None = None,
    hasta: dt.datetime | None = None,
    estado: EstadoTurno | None = None,
) -> tuple[int, list[Turno]]:
    """Lista turnos de la empresa, filtrables por recurso, rango de fechas y estado.

    Es el corazón de la vista de agenda: 'dame los turnos de Juan esta semana'.
    """
    condiciones = [Turno.empresa_id == empresa_id]
    if recurso_id is not None:
        condiciones.append(Turno.recurso_id == recurso_id)
    if cliente_id is not None:
        condiciones.append(Turno.cliente_id == cliente_id)
    if desde is not None:
        condiciones.append(Turno.fecha_inicio >= desde)
    if hasta is not None:
        condiciones.append(Turno.fecha_inicio < hasta)
    if estado is not None:
        condiciones.append(Turno.estado == estado)

    total = db.scalar(select(func.count()).select_from(Turno).where(*condiciones))
    turnos = list(
        db.scalars(
            select(Turno).where(*condiciones).order_by(Turno.fecha_inicio)
        )
    )
    for t in turnos:
        _resolver_nombres(db, t)
    _setear_totales(db, turnos)
    return total or 0, turnos


def obtener(db: Session, empresa_id: int, turno_id: int) -> Turno | None:
    """Trae un turno por id, solo si es de esta empresa, con nombres resueltos."""
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None
    _resolver_nombres(db, turno)
    _setear_totales(db, [turno])
    return turno


def crear(db: Session, empresa_id: int, datos: TurnoCrear) -> Turno:
    """Crea un turno validando disponibilidad con el motor (salvo sobreturno).

    Pasos: valida que cliente/recurso/servicio sean de la empresa → calcula
    fecha_fin desde la duración del servicio → pregunta al motor si el hueco
    está libre → si lo está (o es sobreturno), guarda.
    """
    # 1. Las tres entidades deben ser de esta empresa (Regla 1)
    cliente = _entidad_de_empresa(db, Cliente, datos.cliente_id, empresa_id)
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
    recurso = _entidad_de_empresa(db, Recurso, datos.recurso_id, empresa_id)
    if recurso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")
    servicio = _entidad_de_empresa(db, Servicio, datos.servicio_id, empresa_id)
    if servicio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado")

    # 2. El sistema calcula la fecha de fin (no la manda el cliente)
    fecha_fin = datos.fecha_inicio + dt.timedelta(minutes=servicio.duracion_min)

    # 3. Validar disponibilidad con el motor (salvo que sea sobreturno).
    # Le pasamos el grupo_agenda del servicio: solo bloquea con turnos del
    # mismo carril (corte vs tintura vs barba conviven a la misma hora).
    if not datos.es_sobreturno:
        libre = disp.esta_disponible(
            db, empresa_id, datos.recurso_id, datos.fecha_inicio, fecha_fin,
            grupo_agenda=servicio.grupo_agenda,
        )
        if not libre:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El horario no está disponible (fuera de agenda, bloqueado o ya ocupado)",
            )

    # 3.5. ¿El cliente tiene un abono activo que cubre este servicio?
    # Si sí: el turno queda en $0 y se marca como cubierto (para finanzas).
    cubierto = _abono_cubre_servicio(db, empresa_id, datos.cliente_id, servicio.id)

    # Importe: si está cubierto por abono → 0. Si no, el que vino o el del servicio.
    if cubierto:
        importe = 0
    elif datos.importe_previsto is not None:
        importe = datos.importe_previsto
    else:
        importe = servicio.precio

    # 4. Crear el turno
    turno = Turno(
        empresa_id=empresa_id,
        cliente_id=datos.cliente_id,
        recurso_id=datos.recurso_id,
        servicio_id=datos.servicio_id,
        tipo=datos.tipo,
        estado=EstadoTurno.PENDIENTE,
        categoria=datos.categoria,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=fecha_fin,
        es_sobreturno=datos.es_sobreturno,
        importe_previsto=importe,
        cubierto_por_abono=cubierto,
        notas=datos.notas,
    )

    db.add(turno)
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)


def mover(
    db: Session, empresa_id: int, turno_id: int, datos: TurnoMover
) -> Turno | None:
    """Reprograma un turno (nuevo horario y/o recurso), revalidando disponibilidad.

    Excluye el propio turno del chequeo (si no, chocaría consigo mismo).
    """
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None

    nuevo_recurso_id = datos.recurso_id or turno.recurso_id
    if datos.recurso_id is not None:
        # si cambia de recurso, validar que el nuevo sea de la empresa
        if _entidad_de_empresa(db, Recurso, datos.recurso_id, empresa_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")

    # recalcular duración a partir del servicio (la misma de antes)
    duracion = (turno.fecha_fin - turno.fecha_inicio) if turno.fecha_fin else dt.timedelta(minutes=30)
    nueva_fin = datos.fecha_inicio + duracion

    # grupo de agenda del servicio del turno (para la regla de carriles)
    serv_turno = db.get(Servicio, turno.servicio_id) if turno.servicio_id else None
    grupo_turno = serv_turno.grupo_agenda if serv_turno else None

    # validar el nuevo hueco, excluyendo este mismo turno
    if not turno.es_sobreturno:
        libre = disp.esta_disponible(
            db, empresa_id, nuevo_recurso_id, datos.fecha_inicio, nueva_fin,
            excluir_turno_id=turno.id,
            grupo_agenda=grupo_turno,
        )
        if not libre:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El nuevo horario no está disponible",
            )

    turno.fecha_inicio = datos.fecha_inicio
    turno.fecha_fin = nueva_fin
    turno.recurso_id = nuevo_recurso_id
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)


def cambiar_estado(
    db: Session,
    empresa_id: int,
    turno_id: int,
    datos: TurnoCambiarEstado,
    *,
    recurso_profesional: int | None = None,
) -> Turno | None:
    """Cambia el estado del turno respetando las transiciones válidas.

    recurso_profesional:
      - None  -> quien gestiona es dueño/recepción: sin restricción de propiedad.
      - <id>  -> quien gestiona es un profesional: el turno DEBE ser de ese
                 recurso y la transición DEBE estar en ESTADOS_PROFESIONAL
                 (solo en curso / finalizado). Si no, 403.
    La capa de ruta traduce rol -> recurso_profesional; el service no conoce roles.
    """
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None

    # Restricción del profesional: solo SUS turnos y solo el flujo de atención.
    if recurso_profesional is not None:
        if turno.recurso_id != recurso_profesional:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Solo podés gestionar tus propios turnos",
            )
        if datos.estado not in ESTADOS_PROFESIONAL:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Como profesional solo podés marcar el turno en curso o finalizado",
            )

    # ¿La transición es válida? (no se puede finalizar un cancelado, etc.)
    permitidos = TRANSICIONES[turno.estado]
    if datos.estado not in permitidos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede pasar de '{turno.estado.value}' a '{datos.estado.value}'",
        )

    turno.estado = datos.estado
    if datos.estado == EstadoTurno.CANCELADO and datos.motivo_cancelacion:
        turno.motivo_cancelacion = datos.motivo_cancelacion
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)


def aplicar_descuento(
    db: Session, empresa_id: int, turno_id: int, pct: float
) -> Turno | None:
    """Guarda el % de descuento del turno. None si no es de esta empresa."""
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None
    turno.descuento_pct = pct
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)

def _abono_cubre_servicio(
    db: Session, empresa_id: int, cliente_id: int, servicio_id: int
) -> bool:
    """¿El cliente tiene un abono activo que cubre este servicio?

    Devuelve True si: tiene membresía vigente Y el servicio está en la lista
    de servicios cubiertos del plan. Si la lista está vacía, NO cubre (el dueño
    debe marcar explícitamente qué servicios incluye el abono).
    """
    membresia = svc_membresia.membresia_activa_de(db, empresa_id, cliente_id)
    if not membresia:
        return False
    plan = membresia.plan
    if not plan:
        return False
    cubiertos = plan.servicios_cubiertos or []
    return servicio_id in cubiertos
