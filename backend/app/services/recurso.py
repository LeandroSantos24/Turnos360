"""Lógica de negocio de Recurso (E2).

Regla 1 aplicada en DOS lugares:
1. El recurso se filtra siempre por empresa_id (como clientes).
2. Las especialidades que se le asignan DEBEN ser de la misma empresa:
   resolvemos los ids contra la base filtrando por empresa_id, así nadie
   puede asignarle a su recurso una especialidad de otra empresa.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Especialidad, Recurso
from app.schemas.recurso import RecursoCrear, RecursoEditar


def _especialidades_de_empresa(
    db: Session, empresa_id: int, especialidad_ids: list[int]
) -> list[Especialidad]:
    """Resuelve ids → objetos Especialidad, SOLO los que sean de esta empresa.

    Si un id no pertenece a la empresa (o no existe), simplemente no entra
    en el resultado: el recurso nunca termina con una especialidad ajena.
    """
    if not especialidad_ids:
        return []
    return list(
        db.scalars(
            select(Especialidad).where(
                Especialidad.empresa_id == empresa_id,
                Especialidad.id.in_(especialidad_ids),
            )
        )
    )


def listar(
    db: Session,
    empresa_id: int,
    *,
    solo_activos: bool = True,
    tipo: str | None = None,
) -> tuple[int, list[Recurso]]:
    """Devuelve (total, lista) de recursos de esta empresa.

    selectinload precarga las especialidades en una sola query extra, en vez
    de una por recurso (evita el problema N+1).
    """
    condiciones = [Recurso.empresa_id == empresa_id]
    if solo_activos:
        condiciones.append(Recurso.activo.is_(True))
    if tipo:
        condiciones.append(Recurso.tipo == tipo)

    total = db.scalar(
        select(func.count()).select_from(Recurso).where(*condiciones)
    )
    items = list(
        db.scalars(
            select(Recurso)
            .where(*condiciones)
            .options(selectinload(Recurso.especialidades))
            .order_by(Recurso.nombre)
        )
    )
    return total or 0, items


def obtener(db: Session, empresa_id: int, recurso_id: int) -> Recurso | None:
    """Trae un recurso por id, solo si es de esta empresa (con sus especialidades)."""
    return db.scalar(
        select(Recurso)
        .where(Recurso.id == recurso_id, Recurso.empresa_id == empresa_id)
        .options(selectinload(Recurso.especialidades))
    )


def crear(db: Session, empresa_id: int, datos: RecursoCrear) -> Recurso:
    """Crea un recurso y le asigna sus especialidades (validadas por empresa)."""
    payload = datos.model_dump(exclude={"especialidad_ids"})
    recurso = Recurso(empresa_id=empresa_id, **payload)
    recurso.especialidades = _especialidades_de_empresa(
        db, empresa_id, datos.especialidad_ids
    )
    db.add(recurso)
    db.commit()
    db.refresh(recurso)
    return recurso


def editar(
    db: Session, empresa_id: int, recurso_id: int, datos: RecursoEditar
) -> Recurso | None:
    """Edita los campos enviados. Si vienen especialidad_ids, reemplaza el set."""
    recurso = obtener(db, empresa_id, recurso_id)
    if recurso is None:
        return None

    cambios = datos.model_dump(exclude_unset=True)

    # Las especialidades se manejan aparte (no es una columna simple)
    if "especialidad_ids" in cambios:
        nuevos_ids = cambios.pop("especialidad_ids")
        recurso.especialidades = _especialidades_de_empresa(db, empresa_id, nuevos_ids)

    for campo, valor in cambios.items():
        setattr(recurso, campo, valor)

    db.commit()
    db.refresh(recurso)
    return recurso


def desactivar(db: Session, empresa_id: int, recurso_id: int) -> bool:
    """Baja lógica del recurso (activo=False). No borra: tiene turnos asociados."""
    recurso = obtener(db, empresa_id, recurso_id)
    if recurso is None:
        return False
    recurso.activo = False
    db.commit()
    return True