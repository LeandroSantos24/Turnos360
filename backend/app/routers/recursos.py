"""Endpoints de recursos: lo reservable de cada empresa (E2).

Mismo patrón que clientes: todas las rutas exigen token (EmpresaActual),
el empresa_id sale del token y se delega en el service.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DB, EmpresaActual
from app.models.enums import TipoRecurso
from app.schemas.recurso import (
    RecursoCrear,
    RecursoEditar,
    RecursoOut,
    RecursosPagina,
)
from app.services import recurso as svc

router = APIRouter(prefix="/recursos", tags=["recursos"])


@router.get("", response_model=RecursosPagina)
def listar_recursos(
    empresa_id: EmpresaActual,
    db: DB,
    solo_activos: bool = Query(default=True),
    tipo: TipoRecurso | None = Query(default=None, description="Filtrar por persona/box/equipo"),
) -> RecursosPagina:
    """Lista los recursos de la empresa, opcionalmente filtrados por tipo."""
    total, items = svc.listar(
        db, empresa_id, solo_activos=solo_activos, tipo=tipo.value if tipo else None
    )
    return RecursosPagina(total=total, items=items)


@router.get("/{recurso_id}", response_model=RecursoOut)
def obtener_recurso(recurso_id: int, empresa_id: EmpresaActual, db: DB) -> RecursoOut:
    """Devuelve un recurso por id. 404 si no existe o es de otra empresa."""
    recurso = svc.obtener(db, empresa_id, recurso_id)
    if recurso is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return recurso


@router.post("", response_model=RecursoOut, status_code=status.HTTP_201_CREATED)
def crear_recurso(datos: RecursoCrear, empresa_id: EmpresaActual, db: DB) -> RecursoOut:
    """Crea un recurso en la empresa del usuario autenticado."""
    return svc.crear(db, empresa_id, datos)


@router.patch("/{recurso_id}", response_model=RecursoOut)
def editar_recurso(
    recurso_id: int, datos: RecursoEditar, empresa_id: EmpresaActual, db: DB
) -> RecursoOut:
    """Edita los campos enviados de un recurso. 404 si no es de esta empresa."""
    recurso = svc.editar(db, empresa_id, recurso_id, datos)
    if recurso is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return recurso


@router.delete("/{recurso_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_recurso(recurso_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    """Baja lógica del recurso. 404 si no es de esta empresa."""
    if not svc.desactivar(db, empresa_id, recurso_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")