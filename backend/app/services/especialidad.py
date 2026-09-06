"""El catálogo de especialidades de cada negocio.

QUÉ RESUELVE
────────────
La columna «Especialidades» de la tabla de profesionales existía desde el
principio y siempre mostró un guion: el modelo, la tabla puente y la asignación
estaban, pero no había forma de CREAR una. Leandro lo notó probando el alta
—«¿para qué dejás especialidad?»— y la respuesta honesta era «para nada
todavía».

POR QUÉ LAS CREA CADA NEGOCIO Y NO VIENEN DE FÁBRICA
────────────────────────────────────────────────────
Una lista cerrada no le sirve a nadie: una barbería quiere barbero, colorista y
peluquero; un centro de estética quiere depilación y cosmetología; un
consultorio quiere las especialidades médicas de verdad. Cualquier catálogo
nuestro sería el de un rubro y estaría mal para los otros ocho.
"""

import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agenda import Especialidad, Recurso, recurso_especialidad


def _normalizar(nombre: str) -> str:
    """Para comparar: sin mayúsculas, sin espacios de más y sin acentos.

    «Colorista», «colorista» y «Colorista » son la misma. Sin esto el listado
    se llena de duplicados que se ven distintos, y el dueño no entiende por qué
    aparece dos veces lo mismo.
    """
    limpio = " ".join((nombre or "").split()).lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", limpio)
        if unicodedata.category(c) != "Mn"
    )


def listar(db: Session, empresa_id: int) -> list[Especialidad]:
    return list(
        db.scalars(
            select(Especialidad)
            .where(Especialidad.empresa_id == empresa_id)
            .order_by(func.lower(Especialidad.nombre))
        ).all()
    )


def crear(db: Session, empresa_id: int, nombre: str) -> Especialidad:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Poné un nombre.")

    objetivo = _normalizar(nombre)
    for e in listar(db, empresa_id):
        if _normalizar(e.nombre) == objetivo:
            # Se devuelve la que ya está en vez de fallar: el dueño quería que
            # existiera «Colorista» y existe. Un error acá sería exigirle que
            # recuerde qué escribió hace tres meses.
            return e

    especialidad = Especialidad(empresa_id=empresa_id, nombre=nombre[:120])
    db.add(especialidad)
    db.flush()
    return especialidad


def _propia(db: Session, empresa_id: int, especialidad_id: int) -> Especialidad:
    e = db.get(Especialidad, especialidad_id)
    # El 404 tapa la diferencia entre «no existe» y «es de otro negocio»: un
    # 403 le confirmaría a alguien que ese id existe en otra empresa.
    if e is None or e.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esa especialidad no existe.")
    return e


def renombrar(db: Session, empresa_id: int, especialidad_id: int, nombre: str) -> Especialidad:
    e = _propia(db, empresa_id, especialidad_id)
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Poné un nombre.")

    objetivo = _normalizar(nombre)
    for otra in listar(db, empresa_id):
        if otra.id != e.id and _normalizar(otra.nombre) == objetivo:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Ya tenés una especialidad que se llama «{otra.nombre}».",
            )
    e.nombre = nombre[:120]
    db.flush()
    return e


def borrar(db: Session, empresa_id: int, especialidad_id: int) -> None:
    """Borra la especialidad y la saca de todos los profesionales.

    Se borra de verdad y no se desactiva: una especialidad no es un dato
    histórico —no hay turnos ni plata colgando de ella—, es una etiqueta. Un
    catálogo que solo crece y nunca limpia termina con quince entradas de las
    que se usan tres.

    Las filas del puente se borran a mano porque la tabla no tiene ON DELETE
    CASCADE: sin esto, el DELETE falla con una violación de clave foránea que
    dice «recurso_especialidad» y no explica nada.
    """
    e = _propia(db, empresa_id, especialidad_id)
    db.execute(
        recurso_especialidad.delete().where(
            recurso_especialidad.c.especialidad_id == e.id
        )
    )
    db.delete(e)
    db.flush()


def en_uso(db: Session, empresa_id: int, especialidad_id: int) -> int:
    """Cuántos profesionales la tienen. Para poder avisar antes de borrar."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(recurso_especialidad)
            .join(Recurso, Recurso.id == recurso_especialidad.c.recurso_id)
            .where(
                recurso_especialidad.c.especialidad_id == especialidad_id,
                Recurso.empresa_id == empresa_id,
            )
        )
        or 0
    )
