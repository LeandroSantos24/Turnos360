"""Endpoints del CRM de clientes (E2).

Todas las rutas exigen un token válido (vía EmpresaActual, que invoca al
guardián). El empresa_id sale del token y se le pasa al service: el cliente
nunca elige sobre qué empresa opera (Regla 1).
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DB, EmpresaActual
from app.schemas.cliente import (
    ClienteCrear,
    ClienteEditar,
    ClienteOut,
    ClientesPagina,
)
from app.services import cliente as svc

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("", response_model=ClientesPagina)
def listar_clientes(
    empresa_id: EmpresaActual,
    db: DB,
    buscar: str | None = Query(default=None, description="Texto en nombre, apellido, DNI, tel o email"),
    solo_activos: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=200),
) -> ClientesPagina:
    """Lista paginada de los clientes de la empresa, con búsqueda opcional."""
    total, items = svc.listar(
        db, empresa_id,
        buscar=buscar, solo_activos=solo_activos, offset=offset, limite=limite,
    )
    return ClientesPagina(total=total, items=items)


@router.get("/{cliente_id}", response_model=ClienteOut)
def obtener_cliente(cliente_id: int, empresa_id: EmpresaActual, db: DB) -> ClienteOut:
    """Devuelve un cliente por id. 404 si no existe o es de otra empresa."""
    cliente = svc.obtener(db, empresa_id, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return cliente


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def crear_cliente(datos: ClienteCrear, empresa_id: EmpresaActual, db: DB) -> ClienteOut:
    """Crea un cliente en la empresa del usuario autenticado."""
    return svc.crear(db, empresa_id, datos)


@router.patch("/{cliente_id}", response_model=ClienteOut)
def editar_cliente(
    cliente_id: int, datos: ClienteEditar, empresa_id: EmpresaActual, db: DB
) -> ClienteOut:
    """Edita los campos enviados de un cliente. 404 si no es de esta empresa."""
    cliente = svc.editar(db, empresa_id, cliente_id, datos)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return cliente


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_cliente(cliente_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    """Baja lógica del cliente (activo=False). 404 si no es de esta empresa."""
    if not svc.desactivar(db, empresa_id, cliente_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")