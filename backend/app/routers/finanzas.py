"""Endpoints de finanzas (E10): métodos de pago, cobros, caja, gastos.

El empresa_id sale del token; el usuario actual queda registrado en cada
operación (quién abrió/cerró la caja, quién cobró, quién cargó el gasto).

Roles (criterio "lecturas abiertas, escrituras gateadas"):
- Configurar métodos de pago (crear/editar/borrar) = dueño (gate_dueno).
- Operar el día (abrir/cerrar caja, cobrar, gastos, categorías) = dueño +
  recepción (gate_gestion).
- LISTAR métodos de pago queda abierto: el flujo de cobro de recepción lo
  necesita para elegir con qué se paga. Igual el resto de las lecturas.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DB, EmpresaActual, UsuarioActual, gate_dueno, gate_gestion
from app.models.enums import TipoMovimiento
from app.schemas.finanzas import (
    CajaAbrir,
    CajaCerrar,
    CajaOut,
    CajaDetalle,
    CajaResumen,
    CategoriaCrear,
    CategoriaOut,
    CobradoCliente,
    CobroCrear,
    CobroOut,
    GastoCrear,
    MetodoPagoCrear,
    MetodoPagoEditar,
    MetodoPagoOut,
    MovimientoOut,
    PagoOut,
)
from app.services import finanzas as svc

router = APIRouter(tags=["finanzas"])


# ─────────────────────────── Métodos de pago ────────────────────────────────

@router.get("/metodos-pago", response_model=list[MetodoPagoOut])
def listar_metodos(empresa_id: EmpresaActual, db: DB) -> list[MetodoPagoOut]:
    # Abierto: el cobro (recepción) necesita la lista para elegir método.
    return svc.listar_metodos(db, empresa_id)


@router.post(
    "/metodos-pago",
    response_model=MetodoPagoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_dueno)],
)
def crear_metodo(datos: MetodoPagoCrear, empresa_id: EmpresaActual, db: DB) -> MetodoPagoOut:
    return svc.crear_metodo(db, empresa_id, datos)


@router.patch(
    "/metodos-pago/{metodo_id}",
    response_model=MetodoPagoOut,
    dependencies=[Depends(gate_dueno)],
)
def editar_metodo(
    metodo_id: int, datos: MetodoPagoEditar, empresa_id: EmpresaActual, db: DB
) -> MetodoPagoOut:
    m = svc.editar_metodo(db, empresa_id, metodo_id, datos)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Método de pago no encontrado")
    return m


@router.delete(
    "/metodos-pago/{metodo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(gate_dueno)],
)
def borrar_metodo(metodo_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    if not svc.borrar_metodo(db, empresa_id, metodo_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Método de pago no encontrado")


# ─────────────────────────── Categorías de gasto ────────────────────────────

@router.get("/categorias-financieras", response_model=list[CategoriaOut])
def listar_categorias(empresa_id: EmpresaActual, db: DB) -> list[CategoriaOut]:
    return svc.listar_categorias(db, empresa_id)


@router.post(
    "/categorias-financieras",
    response_model=CategoriaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def crear_categoria(datos: CategoriaCrear, empresa_id: EmpresaActual, db: DB) -> CategoriaOut:
    return svc.crear_categoria(db, empresa_id, datos)


# ─────────────────────────── Caja ───────────────────────────────────────────

@router.get("/caja/actual", response_model=CajaResumen | None)
def caja_actual(empresa_id: EmpresaActual, db: DB) -> CajaResumen | None:
    """La caja abierta con sus cifras al momento, o null si no hay ninguna abierta."""
    caja = svc.caja_abierta(db, empresa_id)
    if caja is None:
        return None
    return svc.resumen_caja(db, empresa_id, caja)


@router.get("/cajas", response_model=list[CajaOut])
def listar_cajas(empresa_id: EmpresaActual, db: DB) -> list[CajaOut]:
    """Historial de cajas con sus fechas y saldos."""
    return svc.listar_cajas(db, empresa_id)


@router.get("/cajas/{caja_id}/detalle", response_model=CajaDetalle)
def detalle_caja(caja_id: int, empresa_id: EmpresaActual, db: DB) -> CajaDetalle:
    """Resumen y movimientos de una caja (para el cierre imprimible)."""
    det = svc.detalle_caja(db, empresa_id, caja_id)
    if det is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Caja no encontrada")
    return det


@router.post(
    "/caja/abrir",
    response_model=CajaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def abrir_caja(
    datos: CajaAbrir, empresa_id: EmpresaActual, usuario: UsuarioActual, db: DB
) -> CajaOut:
    caja = svc.abrir_caja(db, empresa_id, datos, usuario.id)
    if caja is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una caja abierta")
    return caja


@router.post(
    "/caja/cerrar",
    response_model=CajaResumen,
    dependencies=[Depends(gate_gestion)],
)
def cerrar_caja(
    datos: CajaCerrar, empresa_id: EmpresaActual, usuario: UsuarioActual, db: DB
) -> CajaResumen:
    resumen = svc.cerrar_caja(db, empresa_id, datos, usuario.id)
    if resumen is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay una caja abierta para cerrar")
    return resumen


# ─────────────────────────── Cobro de un turno ──────────────────────────────

@router.post(
    "/turnos/{turno_id}/cobro",
    response_model=CobroOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def registrar_cobro(
    turno_id: int, datos: CobroCrear, empresa_id: EmpresaActual, usuario: UsuarioActual, db: DB
) -> CobroOut:
    cobro = svc.registrar_cobro(db, empresa_id, turno_id, datos, usuario.id)
    if cobro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado")
    return cobro


@router.get("/turnos/{turno_id}/pagos", response_model=list[PagoOut])
def pagos_de_turno(turno_id: int, empresa_id: EmpresaActual, db: DB) -> list[PagoOut]:
    return svc.pagos_de_turno(db, empresa_id, turno_id)


# ─────────────────────────── Gastos / movimientos ───────────────────────────

@router.post(
    "/gastos",
    response_model=MovimientoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_gestion)],
)
def registrar_gasto(
    datos: GastoCrear, empresa_id: EmpresaActual, usuario: UsuarioActual, db: DB
) -> MovimientoOut:
    return svc.registrar_gasto(db, empresa_id, datos, usuario.id)


@router.get("/movimientos", response_model=list[MovimientoOut])
def listar_movimientos(
    empresa_id: EmpresaActual,
    db: DB,
    tipo: TipoMovimiento | None = Query(default=None),
) -> list[MovimientoOut]:
    return svc.listar_movimientos(db, empresa_id, tipo)


# ─────────────────────────── Historial comercial ───────────────────────────

@router.get("/clientes/{cliente_id}/cobrado", response_model=CobradoCliente)
def cobrado_cliente(
    cliente_id: int, empresa_id: EmpresaActual, db: DB
) -> CobradoCliente:
    """Total realmente cobrado a un cliente (para su historial comercial)."""
    return svc.total_cobrado_cliente(db, empresa_id, cliente_id)
