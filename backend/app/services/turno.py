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
from app.core.candados import bloquear_agenda
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
    """Total real del turno: (servicio + adicionales) − % − descuento fijo.

    Es LA cuenta del total: la usan la agenda, el saldo y el cobro. El fijo va
    después del % y nunca deja el total en negativo.
    """
    base = float(turno.importe_previsto or 0) + items_sum
    pct = float(turno.descuento_pct or 0)
    fijo = float(getattr(turno, "descuento_monto", 0) or 0)
    return round(max(base * (1 - pct / 100) - fijo, 0.0), 2)


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
        # Los anulados no pagaron nada: sumarlos dejaba un saldo menor al
        # real y la recepción le cobraba de menos al cliente.
        .where(Pago.turno_id.in_(ids), Pago.anulado.is_(False))
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
        # Saldo = total − TODO lo pagado (seña, cobros parciales, gift card).
        # Antes restaba solo la seña: después de un cobro parcial el saldo
        # seguía mostrando el total.
        t.saldo = round(max((t.total or 0.0) - cobros.get(t.id, 0.0), 0.0), 2)
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
    sucursal_id: int | None = None,
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
    if sucursal_id is not None:
        # Se filtra por la columna del turno y no joineando con recurso: el
        # local quedó copiado al crearlo justamente para esto, y para que un
        # turno viejo siga contando en el local donde ocurrió aunque el
        # profesional se haya mudado después.
        condiciones.append(Turno.sucursal_id == sucursal_id)
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

    # 2.5. CANDADO. Entre preguntar «¿está libre?» y hacer el INSERT no
    # había nada: dos personas confirmando con milisegundos de diferencia
    # se quedaban las dos con la misma silla, y las dos recibían «tu turno
    # quedó reservado». Ver app/core/candados.py.
    #
    # Va incluso para los sobreturnos: cuestan poco y así el orden es
    # siempre el mismo, sin depender de por qué rama entró la reserva.
    bloquear_agenda(db, empresa_id, datos.recurso_id)

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
    cubierto = _abono_cubre_servicio(
        db, empresa_id, datos.cliente_id, servicio.id, datos.fecha_inicio.date()
    )

    # El servicio tiene que prestarse en el local donde atiende esta persona.
    # Con un solo local siempre se cumple (todo servicio nace ofrecido en
    # todos), así que este chequeo no se nota hasta que hay varios.
    from app.services import servicio as servicio_svc

    if not servicio_svc.se_ofrece_en(db, servicio.id, recurso.sucursal_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{servicio.nombre}» no se ofrece en el local donde atiende "
            f"{recurso.nombre}. Agregalo a ese local desde Servicios, o elegí "
            "a alguien de otro local.",
        )

    # Importe: si está cubierto por abono → 0. Si no, el que vino o el del
    # servicio EN ESE LOCAL (el mismo corte puede costar distinto en cada uno).
    if cubierto:
        importe = 0
    elif datos.importe_previsto is not None:
        importe = datos.importe_previsto
    else:
        importe = servicio_svc.precio_en(db, servicio, recurso.sucursal_id)

    # 4. Crear el turno
    turno = Turno(
        empresa_id=empresa_id,
        # El turno se hace donde atiende el profesional. Se copia en vez de
        # joinear: si mañana esa persona se muda de local, los turnos que ya
        # pasaron tienen que seguir contando en el local donde ocurrieron.
        sucursal_id=recurso.sucursal_id,
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
        select(Turno)
        .where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
        .with_for_update()
    )
    if turno is None:
        return None

    # Un turno atendido o cobrado ya es un hecho económico: moverlo de día o
    # de profesional reescribe a quién se le atribuye una plata ya cobrada.
    if turno.estado in (EstadoTurno.FINALIZADO, EstadoTurno.AUSENTE) or turno.cobrado:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este turno ya fue atendido o cobrado y no se puede reprogramar. "
            "Si fue un error, reabrilo o anulá el cobro primero.",
        )

    nuevo_recurso_id = datos.recurso_id or turno.recurso_id
    nuevo_recurso = None
    if datos.recurso_id is not None:
        # si cambia de recurso, validar que el nuevo sea de la empresa
        nuevo_recurso = _entidad_de_empresa(db, Recurso, datos.recurso_id, empresa_id)
        if nuevo_recurso is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")

    # recalcular duración a partir del servicio (la misma de antes)
    duracion = (turno.fecha_fin - turno.fecha_inicio) if turno.fecha_fin else dt.timedelta(minutes=30)
    nueva_fin = datos.fecha_inicio + duracion

    # grupo de agenda del servicio del turno (para la regla de carriles)
    serv_turno = db.get(Servicio, turno.servicio_id) if turno.servicio_id else None
    grupo_turno = serv_turno.grupo_agenda if serv_turno else None

    # Mismo candado que al crear: mover un turno a un hueco es exactamente
    # la misma carrera. Se traba el recurso DESTINO, que es donde puede
    # haber colisión.
    bloquear_agenda(db, empresa_id, nuevo_recurso_id)

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

    # Si el turno se movió de fecha, vuelve a tener derecho a su
    # recordatorio. Los flags no se reseteaban nunca: al turno que MÁS chance
    # tiene de olvidarse —justo el que le cambiaron el horario— era al único
    # que no le llegaba el aviso.
    if datos.fecha_inicio != turno.fecha_inicio:
        turno.recordatorio_enviado = False
        turno.recordatorio_2h_enviado = False

    # Reasignado a alguien de OTRO local: el turno se muda con él. Antes se
    # quedaba en el local viejo y el cobro entraba a la caja de un local donde
    # no se atendió.
    if nuevo_recurso is not None and nuevo_recurso.sucursal_id != turno.sucursal_id:
        from app.services import servicio as servicio_svc

        if turno.servicio_id and not servicio_svc.se_ofrece_en(
            db, turno.servicio_id, nuevo_recurso.sucursal_id
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Ese servicio no se ofrece en el local de ese profesional.",
            )
        turno.sucursal_id = nuevo_recurso.sucursal_id

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

    # Reabrir un turno que había soltado el hueco (cancelado) lo vuelve a
    # ocupar. Mientras estuvo cancelado, ese horario pudo venderse: sin este
    # chequeo, reabrirlo creaba la silla doble. Mismo candado que crear/mover.
    if (
        turno.estado not in disp.ESTADOS_OCUPAN
        and datos.estado in disp.ESTADOS_OCUPAN
        and not turno.es_sobreturno
        and turno.fecha_fin is not None
    ):
        bloquear_agenda(db, empresa_id, turno.recurso_id)
        serv = db.get(Servicio, turno.servicio_id) if turno.servicio_id else None
        if not disp.esta_disponible(
            db, empresa_id, turno.recurso_id, turno.fecha_inicio, turno.fecha_fin,
            excluir_turno_id=turno.id,
            grupo_agenda=serv.grupo_agenda if serv else None,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Ese horario ya está ocupado por otro turno. Movelo a otro "
                "horario antes de reabrirlo.",
            )

    # Un turno cancelado no puede seguir facturando. Si tiene cobro del
    # mostrador (o uso de gift card) vigente, primero se anula el cobro. La
    # seña online sí puede quedar: es la política de seña no reembolsable, y
    # si se devuelve, Mercado Pago avisa y se revierte sola.
    if datos.estado == EstadoTurno.CANCELADO:
        cobrado = db.scalar(
            select(func.count(Pago.id)).where(
                Pago.turno_id == turno.id,
                Pago.anulado.is_(False),
                Pago.origen.is_distinct_from("sena"),
            )
        )
        if cobrado:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Este turno tiene un cobro registrado. Anulá el cobro antes de "
                "cancelarlo, así la plata sale de la caja y de las estadísticas.",
            )

    turno.estado = datos.estado
    if datos.estado == EstadoTurno.CANCELADO and datos.motivo_cancelacion:
        turno.motivo_cancelacion = datos.motivo_cancelacion
    db.commit()
    db.refresh(turno)

    # Emails del workflow (por cola; jamás bloquean ni rompen la operación).
    try:
        from app.core.cola import encolar
        from app.services.empresa import automs_de
        from app.tasks.emails import enviar_cancelacion, pedir_resena

        if datos.estado == EstadoTurno.CANCELADO:
            encolar(enviar_cancelacion, turno.id)
        elif datos.estado == EstadoTurno.FINALIZADO:
            # La reseña NO sale en el mismo momento en que se marca el turno
            # como terminado: ahí la persona está pagando, poniéndose el
            # abrigo y saliendo. O no ve el mail, o lo ve y le molesta —y un
            # pedido de reseña que molesta es peor que no pedirla—. Sale unas
            # horas después, cuando ya está en su casa y el buen rato es un
            # recuerdo. El dueño elige cuántas en Campañas.
            horas = int(
                (automs_de(db.get(Empresa, empresa_id)) or {})
                .get("resena_google", {})
                .get("horas_despues", 2)
            )
            if horas > 0:
                pedir_resena.apply_async((turno.id,), countdown=horas * 3600)
            else:
                encolar(pedir_resena, turno.id)
    except Exception:
        pass

    return _resolver_nombres(db, turno)


def aplicar_descuento(
    db: Session, empresa_id: int, turno_id: int, pct: float, monto: float | None = None
) -> Turno | None:
    """Guarda el descuento del turno (% y/o fijo en pesos).

    No se toca el precio de un turno ya cobrado: el turno diría un total y la
    caja otro. Tampoco se acepta un descuento que deje el total por debajo de
    lo ya pagado (por ejemplo, la seña).
    """
    from app.services.finanzas import total_y_pagado

    turno = db.scalar(
        select(Turno)
        .where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
        .with_for_update()
    )
    if turno is None:
        return None
    if turno.cobrado:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El turno ya está cobrado. Para cambiar el precio, anulá el cobro primero.",
        )
    previo = (turno.descuento_pct, turno.descuento_monto)
    turno.descuento_pct = pct
    if monto is not None:
        turno.descuento_monto = monto
    total, pagado = total_y_pagado(db, turno)
    if total + 0.009 < pagado:
        turno.descuento_pct, turno.descuento_monto = previo
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Con ese descuento el total (${total:,.2f}) queda por debajo de lo "
            f"ya pagado (${pagado:,.2f}).",
        )
    db.commit()
    db.refresh(turno)
    _setear_totales(db, [turno])
    return _resolver_nombres(db, turno)

def _abono_cubre_servicio(
    db: Session, empresa_id: int, cliente_id: int, servicio_id: int, fecha: dt.date
) -> bool:
    """¿El cliente tiene un abono que cubre este servicio EL DÍA DEL TURNO?

    Devuelve True si: tiene membresía vigente en esa fecha, el servicio está
    en la lista de cubiertos del plan y, si el plan no es ilimitado, le queda
    cupo. Si la lista está vacía, NO cubre.

    Antes se miraba la vigencia de HOY (un turno de dentro de dos meses salía
    gratis con un abono que vencía mañana) y `cantidad_cupos` no se
    controlaba nunca: un plan de 4 cortes cubría cortes ilimitados en $0.
    """
    membresia = svc_membresia.membresia_vigente_en(db, empresa_id, cliente_id, fecha)
    if not membresia:
        return False
    plan = membresia.plan
    if not plan:
        return False
    if servicio_id not in (plan.servicios_cubiertos or []):
        return False
    if not plan.ilimitado and plan.cantidad_cupos:
        return svc_membresia.cupos_usados(db, membresia) < int(plan.cantidad_cupos)
    return True


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
