"""El catálogo de especialidades del negocio.

Leer es libre para cualquiera con sesión —la agenda y el editor las muestran—;
crear, renombrar y borrar es configuración del negocio y va detrás del gate de
dueño, igual que el catálogo de servicios o el de recursos.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.recurso import EspecialidadOut
from app.services import especialidad as svc

router = APIRouter(prefix="/especialidades", tags=["especialidades"])


class EspecialidadIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)


class EspecialidadConUso(EspecialidadOut):
    """La especialidad más cuánta gente la tiene.

    El número va en el listado y no detrás de un click porque es justo lo que
    hace falta ANTES de borrar: «esto lo tienen 3 profesionales» cambia la
    decisión, y preguntarlo después de apretar es tarde.
    """

    en_uso: int = 0


@router.get("", response_model=list[EspecialidadConUso])
def listar(empresa_id: EmpresaActual, db: DB) -> list[EspecialidadConUso]:
    return [
        EspecialidadConUso(
            id=e.id, nombre=e.nombre, en_uso=svc.en_uso(db, empresa_id, e.id)
        )
        for e in svc.listar(db, empresa_id)
    ]


@router.post(
    "",
    response_model=EspecialidadOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(gate_dueno)],
)
def crear(datos: EspecialidadIn, empresa_id: EmpresaActual, db: DB) -> EspecialidadOut:
    e = svc.crear(db, empresa_id, datos.nombre)
    db.commit()
    db.refresh(e)
    return EspecialidadOut.model_validate(e)


@router.patch(
    "/{especialidad_id}",
    response_model=EspecialidadOut,
    dependencies=[Depends(gate_dueno)],
)
def renombrar(
    especialidad_id: int, datos: EspecialidadIn, empresa_id: EmpresaActual, db: DB
) -> EspecialidadOut:
    e = svc.renombrar(db, empresa_id, especialidad_id, datos.nombre)
    db.commit()
    db.refresh(e)
    return EspecialidadOut.model_validate(e)


@router.delete(
    "/{especialidad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(gate_dueno)],
)
def borrar(especialidad_id: int, empresa_id: EmpresaActual, db: DB) -> None:
    svc.borrar(db, empresa_id, especialidad_id)
    db.commit()
