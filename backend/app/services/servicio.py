"""Lógica de negocio de Servicio (E2). Mismo patrón multi-tenant que clientes."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Servicio
from app.schemas.servicio import ServicioCrear, ServicioEditar


def listar(
    db: Session, empresa_id: int, *, solo_activos: bool = True
) -> tuple[int, list[Servicio]]:
    condiciones = [Servicio.empresa_id == empresa_id]
    if solo_activos:
        condiciones.append(Servicio.activo.is_(True))
    total = db.scalar(select(func.count()).select_from(Servicio).where(*condiciones))
    items = list(
        db.scalars(select(Servicio).where(*condiciones).order_by(Servicio.nombre))
    )
    return total or 0, items


def obtener(db: Session, empresa_id: int, servicio_id: int) -> Servicio | None:
    return db.scalar(
        select(Servicio).where(
            Servicio.id == servicio_id, Servicio.empresa_id == empresa_id
        )
    )


def crear(db: Session, empresa_id: int, datos: ServicioCrear) -> Servicio:
    servicio = Servicio(empresa_id=empresa_id, **datos.model_dump())
    db.add(servicio)
    db.commit()
    db.refresh(servicio)
    return servicio


def editar(
    db: Session, empresa_id: int, servicio_id: int, datos: ServicioEditar
) -> Servicio | None:
    servicio = obtener(db, empresa_id, servicio_id)
    if servicio is None:
        return None
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(servicio, campo, valor)
    db.commit()
    db.refresh(servicio)
    return servicio


def desactivar(db: Session, empresa_id: int, servicio_id: int) -> bool:
    servicio = obtener(db, empresa_id, servicio_id)
    if servicio is None:
        return False
    servicio.activo = False
    db.commit()
    return True