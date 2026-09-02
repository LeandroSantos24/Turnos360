"""Endpoints de turnos: la reserva (E2).

El service ya valida disponibilidad con el motor y controla las transiciones
de estado; acá solo exponemos esas operaciones por HTTP, atadas al guardián.

Roles:
- Crear / mover / descuento = gestión del día (gate_gestion: dueño + recepción).
- Cambiar estado: dueño/recepción todo; el PROFESIONAL puede operar SOLO sus
  propios turnos y solo el flujo de atención (en curso / finalizado).
- Agenda (listar sin cliente_id): el profesional ve SOLO lo suyo (forzado).
  Con cliente_id es la ficha/historial del cliente, abierta a todo el equipo.
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DB,
    EmpresaActual,
    UsuarioActual,
    contexto_profesional,
    gate_gestion,
    sucursal_visible,
)
from sqlalchemy import select

from app.models import Recurso
from app.models.enums import EstadoTurno
from app.schemas.turno import (
    TurnoCambiarEstado,
    TurnoDescuento,
    TurnoCrear,
    TurnoMover,
    TurnoOut,
    TurnosPagina,
)
from app.services import turno as svc
from app.services import servicio as svc_servicio
from app.services.disponibilidad import calcular_huecos

router = APIRouter(prefix="/turnos", tags=["turnos"])


def sin_plata(turno) -> TurnoOut:
    """El mismo turno, sin un solo importe adentro.

    El filtro por recurso ya estaba bien: un profesional ve solo SUS
    turnos. Lo que faltaba es que esos turnos no vinieran con el total,
    la seña y el saldo. El barbero que atiende no tiene por qué saber
    cuánto factura el local, y hoy lo veía en cada fila de su agenda.

    `cobrado` SÍ se deja: es un booleano operativo, no un importe, y el
    profesional necesita saber si al cliente ya le cobraron para no
    pedirle plata de nuevo en el mostrador.
    """
    salida = TurnoOut.model_validate(turno)
    salida.total = 0.0
    salida.senado = 0.0
    salida.pagado_total = 0.0
    salida.saldo = None
    salida.sena_monto = None
    salida.importe_previsto = None
    salida.descuento_pct = 0.0
    return salida

@router.get("/huecos", response_model=list[dt.datetime])
def buscar_huecos(
    empresa_id: EmpresaActual,
    db: DB,
    recurso_id: int = Query(..., description="Barbero a consultar"),
    fecha: dt.date = Query(..., description="Día a consultar (YYYY-MM-DD)"),
    servicio_id: int = Query(..., description="Servicio: define duración y carril"),
) -> list[dt.datetime]:
    """Horarios de inicio libres para ese servicio, ese día y ese barbero.

    Reutiliza el motor de disponibilidad: respeta franjas de trabajo,
    excepciones, buffer y el carril (grupo_agenda) del servicio.
    """
    servicio = svc_servicio.obtener(db, empresa_id, servicio_id)
    if servicio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado"
        )
    return calcular_huecos(
        db,
        empresa_id,
        recurso_id,
        fecha,
        duracion_min=servicio.duracion_min,
        paso_min=servicio.paso_turno_min,
        grupo_agenda=servicio.grupo_agenda,
    )

def _solo_mi_local(db, usuario, empresa_id: int, recurso_id: int | None) -> None:
    """Recepción no agenda en un local que no es el suyo.

    La pantalla ya solo le ofrece a la gente de su local (el listado de
    recursos viene filtrado), así que un recurso de otro local solo puede
    llegar a mano. Se responde 404 y no 403 por el mismo criterio de siempre:
    decir "no autorizado" confirmaría que ese profesional existe.
    """
    if recurso_id is None:
        return
    limite = sucursal_visible(usuario, None)
    if limite is None:  # dueño o admin: sin restricción
        return
    suya = db.scalar(
        select(Recurso.sucursal_id).where(
            Recurso.id == recurso_id, Recurso.empresa_id == empresa_id
        )
    )
    if suya is not None and suya != limite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ese profesional no trabaja en tu local.",
        )


@router.get("", response_model=TurnosPagina)
def listar_turnos(
    usuario: UsuarioActual,
    db: DB,
    recurso_id: int | None = Query(default=None, description="Filtrar por recurso (agenda de un barbero)"),
    cliente_id: int | None = Query(default=None, description="Filtrar por cliente (historial)"),
    sucursal_id: int | None = Query(default=None, description="Filtrar por local"),
    desde: dt.datetime | None = Query(default=None, description="Turnos desde esta fecha/hora"),
    hasta: dt.datetime | None = Query(default=None, description="Turnos hasta esta fecha/hora"),
    estado: EstadoTurno | None = Query(default=None),
) -> TurnosPagina:
    """Lista turnos de la empresa, filtrables por recurso, rango y estado.

    Es la consulta que alimenta la vista de agenda. Para un PROFESIONAL, la
    agenda (sin cliente_id) se fuerza a SU recurso: ignora el recurso_id que
    mande. Con cliente_id es la ficha del cliente (historial completo del
    negocio), que está abierta a todo el equipo.
    """
    es_prof, mi_recurso = contexto_profesional(usuario)
    if es_prof and cliente_id is None:
        if mi_recurso is None:
            # Profesional todavía sin recurso asignado: agenda vacía (no error).
            return TurnosPagina(total=0, items=[])
        recurso_id = mi_recurso  # fuerza el suyo, ignora lo pedido

    # Recepción ve solo la agenda de SU local. El dueño ve la que pida.
    sucursal_id = sucursal_visible(usuario, sucursal_id)

    total, items = svc.listar(
        db, usuario.empresa_id,
        recurso_id=recurso_id, cliente_id=cliente_id, sucursal_id=sucursal_id,
        desde=desde, hasta=hasta, estado=estado,
    )
    if es_prof:
        items = [sin_plata(t) for t in items]
    return TurnosPagina(total=total, items=items)


@router.get("/{turno_id}", response_model=TurnoOut)
def obtener_turno(
    turno_id: int, usuario: UsuarioActual, empresa_id: EmpresaActual, db: DB
) -> TurnoOut:
    """Devuelve un turno por id. 404 si no existe o es de otra empresa."""
    turno = svc.obtener(db, empresa_id, turno_id)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    es_prof, _ = contexto_profesional(usuario)
    return sin_plata(turno) if es_prof else turno


@router.post(
    "/{turno_id}/pedir-resena",
    dependencies=[Depends(gate_gestion)],
)
def pedir_resena(turno_id: int, empresa_id: EmpresaActual, db: DB) -> dict:
    """Le manda al cliente el pedido de reseña en Google, ahora.

    Distinto de la campaña automática: esta se dispara a mano, para el cliente
    que el dueño eligió y mientras todavía está en el local.
    """
    return svc.pedir_resena_manual(db, empresa_id, turno_id)


@router.post(
    "",
    response_model=TurnoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def crear_turno(
    datos: TurnoCrear, usuario: UsuarioActual, empresa_id: EmpresaActual, db: DB
) -> TurnoOut:
    """Crea un turno validando disponibilidad. 409 si el horario no está libre."""
    _solo_mi_local(db, usuario, empresa_id, datos.recurso_id)
    return svc.crear(db, empresa_id, datos)


@router.patch(
    "/{turno_id}/mover",
    response_model=TurnoOut,
    dependencies=[Depends(gate_gestion)],
)
def mover_turno(
    turno_id: int,
    datos: TurnoMover,
    usuario: UsuarioActual,
    empresa_id: EmpresaActual,
    db: DB,
) -> TurnoOut:
    """Reprograma un turno (horario y/o recurso). 409 si el nuevo horario choca."""
    if datos.recurso_id is not None:
        _solo_mi_local(db, usuario, empresa_id, datos.recurso_id)
    turno = svc.mover(db, empresa_id, turno_id, datos)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return turno


@router.patch("/{turno_id}/estado", response_model=TurnoOut)
def cambiar_estado_turno(
    turno_id: int, datos: TurnoCambiarEstado, usuario: UsuarioActual, db: DB
) -> TurnoOut:
    """Cambia el estado del turno (confirmar, atender, cancelar, REABRIR...).

    Sin gate de rol fijo: dueño y recepción pueden todo; el PROFESIONAL solo
    sus propios turnos y solo el flujo de atención (en curso / finalizado).
    El service hace cumplir esas dos reglas a partir de recurso_profesional.
    409 si la transición de estado no es válida.
    """
    es_prof, mi_recurso = contexto_profesional(usuario)
    if es_prof and mi_recurso is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Todavía no estás vinculado a una agenda. Pedile al dueño que te asigne tu recurso.",
        )

    turno = svc.cambiar_estado(
        db,
        usuario.empresa_id,
        turno_id,
        datos,
        recurso_profesional=mi_recurso if es_prof else None,
    )
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return sin_plata(turno) if es_prof else turno


@router.patch(
    "/{turno_id}/descuento",
    response_model=TurnoOut,
    dependencies=[Depends(gate_gestion)],
)
def aplicar_descuento_turno(
    turno_id: int, datos: TurnoDescuento, empresa_id: EmpresaActual, db: DB
) -> TurnoOut:
    """Aplica un % de descuento al turno (0-100). Parte del armado del cobro."""
    turno = svc.aplicar_descuento(db, empresa_id, turno_id, datos.descuento_pct)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return turno
