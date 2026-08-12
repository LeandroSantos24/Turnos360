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

from app.models import Cliente, Empresa, Recurso, Servicio, Turno
from app.models.items import ItemTurno
from app.models.finanzas import Pago
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


def _nombre_cliente(cliente: Cliente | None) -> str | None:
    if cliente is None:
        return None
    return f"{cliente.nombre} {cliente.apellido or ''}".strip()


def _resolver_nombres_lote(db: Session, turnos: list[Turno]) -> None:
    """Adjunta cliente_nombre, recurso_nombre y servicio_nombre a CADA turno.

    No son columnas: los seteamos como atributos para que el schema TurnoOut
    los incluya en la respuesta (útil para pintar la agenda sin más consultas).

    Por qué en lote y no de a uno: antes esta función recibía UN turno y hacía
    tres db.get(). En la vista de día con 40 turnos eso son hasta 120 consultas
    donde alcanzan 3, y en la vista de mes se multiplica por treinta. Era, por
    lejos, lo que más frenaba la agenda.

    Ahora son 3 consultas fijas sin importar cuántos turnos vengan: una por
    tipo de entidad, con un IN de los ids que aparecen. Los objetos que ya
    estén en la sesión igual salen del identity map de SQLAlchemy.
    """
    if not turnos:
        return

    def _traer(modelo, ids: set[int]) -> dict[int, object]:
        if not ids:
            return {}
        return {
            obj.id: obj
            for obj in db.scalars(select(modelo).where(modelo.id.in_(ids)))
        }

    clientes = _traer(Cliente, {t.cliente_id for t in turnos if t.cliente_id})
    recursos = _traer(Recurso, {t.recurso_id for t in turnos if t.recurso_id})
    servicios = _traer(Servicio, {t.servicio_id for t in turnos if t.servicio_id})

    for t in turnos:
        servicio = servicios.get(t.servicio_id) if t.servicio_id else None
        recurso = recursos.get(t.recurso_id) if t.recurso_id else None
        t.cliente_nombre = _nombre_cliente(
            clientes.get(t.cliente_id) if t.cliente_id else None
        )
        t.recurso_nombre = recurso.nombre if recurso else None
        t.servicio_nombre = servicio.nombre if servicio else None
        t.servicio_grupo = servicio.grupo_agenda if servicio else None


def _resolver_nombres(db: Session, turno: Turno) -> Turno:
    """Versión de un solo turno (crear / mover / cambiar estado / cobrar)."""
    _resolver_nombres_lote(db, [turno])
    return turno


def _total_con_items(turno: Turno, items_sum: float) -> float:
    """Total real del turno: (servicio + adicionales) con el descuento aplicado."""
    base = float(turno.importe_previsto or 0) + items_sum
    pct = float(turno.descuento_pct or 0)
    return round(base * (1 - pct / 100), 2)


def _setear_totales(db: Session, turnos: list[Turno]) -> None:
    """Suma adicionales y señas de cada turno en 2 queries y setea los totales.

    `saldo` es el número que importa al cobrar: total menos lo ya pagado por
    adelantado. Sin él, el diálogo de cobro mostraba el total completo de un
    turno señado y la recepción le cobraba al cliente la seña dos veces.
    """
    if not turnos:
        return
    ids = [t.id for t in turnos]
    filas = db.execute(
        select(ItemTurno.turno_id, func.coalesce(func.sum(ItemTurno.precio * ItemTurno.cantidad), 0))
        .where(ItemTurno.turno_id.in_(ids))
        .group_by(ItemTurno.turno_id)
    ).all()
    sumas = {tid: float(s) for tid, s in filas}

    # Pagos del turno, en lote (una query para toda la vista). Se traen
    # separados por origen para distinguir la seña del cobro del mostrador.
    filas_s = db.execute(
        select(
            Pago.turno_id,
            Pago.origen,
            func.coalesce(func.sum(Pago.monto), 0),
        )
        .where(Pago.turno_id.in_(ids))
        .group_by(Pago.turno_id, Pago.origen)
    ).all()
    senas: dict[int, float] = {}
    cobros: dict[int, float] = {}
    for tid, origen, monto in filas_s:
        if origen == "sena":
            senas[tid] = senas.get(tid, 0.0) + float(monto)
        cobros[tid] = cobros.get(tid, 0.0) + float(monto)

    for t in turnos:
        t.total = _total_con_items(t, sumas.get(t.id, 0.0))
        t.senado = senas.get(t.id, 0.0)
        t.saldo = round(max((t.total or 0.0) - t.senado, 0.0), 2)
        # TODA la plata registrada de este turno (seña + cobro del mostrador).
        # Sirve para avisar cuando se reabre un turno que ya tenía cobros:
        # el pago no se anula solo, y si nadie lo mira el arqueo del día
        # cierra con una diferencia que después nadie sabe explicar.
        #
        # OJO con el nombre: `cobrado` YA EXISTE como columna booleana del
        # modelo. Asignarle un float acá lo marcaría como sucio y SQLAlchemy
        # podría escribir ese número en una columna boolean en el próximo
        # commit. Por eso este atributo se llama distinto.
        t.pagado_total = round(cobros.get(t.id, 0.0), 2)


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

    turnos = list(
        db.scalars(
            select(Turno).where(*condiciones).order_by(Turno.fecha_inicio)
        )
    )
    # El count se calcula sobre la lista en vez de con una segunda consulta:
    # esta función no pagina (trae todo el rango pedido), así que len() da el
    # mismo número que COUNT(*) y ahorra un viaje entero a la base en cada
    # carga de la agenda. Si algún día se pagina, vuelve el COUNT.
    total = len(turnos)
    _resolver_nombres_lote(db, turnos)
    _setear_totales(db, turnos)
    return total, turnos


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

    # Aviso al cliente del cambio (por cola; nunca rompe la operación).
    try:
        from app.tasks.emails import enviar_reprogramacion

        enviar_reprogramacion.delay(turno.id)
    except Exception:
        pass

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

    # Emails del workflow (por cola; jamás bloquean ni rompen la operación).
    try:
        from app.tasks.emails import enviar_cancelacion, pedir_resena

        if datos.estado == EstadoTurno.CANCELADO:
            enviar_cancelacion.delay(turno.id)
        elif datos.estado == EstadoTurno.FINALIZADO:
            pedir_resena.delay(turno.id)
    except Exception:
        pass

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


def pedir_resena_manual(db: Session, empresa_id: int, turno_id: int) -> dict:
    """Manda el pedido de reseña a este cliente, ahora.

    Existe además de la campaña automática porque no son lo mismo: la
    automática le escribe a todos, y el botón se lo manda solo a quien el
    dueño eligió, mientras el cliente todavía está en el local y contento. Esa
    reseña es la que llega a cinco estrellas.

    Las validaciones se hacen ACÁ y no dentro de la task de Celery: la task
    corre en otro proceso y falla en silencio, así que el dueño apretaría el
    botón, vería "enviado" y el mail no saldría nunca.
    """
    from app.models.enums import EstadoMensaje
    from app.models.mensajeria import Mensaje
    from app.services.empresa import automs_de

    turno = db.get(Turno, turno_id)
    if turno is None or turno.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado")

    if turno.estado != EstadoTurno.FINALIZADO:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La reseña se pide cuando el turno está finalizado.",
        )

    cliente = db.get(Cliente, turno.cliente_id) if turno.cliente_id else None
    if cliente is None or not (cliente.email or "").strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Este cliente no tiene email cargado. Agregalo en su ficha y volvé a intentar.",
        )

    empresa = db.get(Empresa, empresa_id)
    cfg = automs_de(empresa).get("resena_google", {})
    if not (cfg.get("link") or "").strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Falta el link de tu ficha de Google. Cargalo en Campañas → Reseña en Google.",
        )

    # No pedirle dos veces por el mismo turno: es la forma más rápida de que
    # un cliente contento deje de estarlo.
    ya = db.scalar(
        select(Mensaje).where(
            Mensaje.empresa_id == empresa_id,
            Mensaje.turno_id == turno_id,
            Mensaje.contenido.like("pedido_resena%"),
            Mensaje.estado == EstadoMensaje.ENVIADO,
        )
    )
    if ya is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya se le pidió la reseña por este turno.",
        )

    from app.tasks.emails import pedir_resena

    pedir_resena.delay(turno_id, manual=True)
    return {"ok": True, "email": cliente.email}
