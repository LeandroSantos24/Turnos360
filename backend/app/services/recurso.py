"""Lógica de negocio de Recurso (E2).

Regla 1 aplicada en VARIOS lugares:
1. El recurso se filtra siempre por empresa_id (como clientes).
2. Las especialidades que se le asignan DEBEN ser de la misma empresa.
3. El usuario que se vincula (usuario_id) DEBE ser de la misma empresa y no
   puede estar ya vinculado a otro recurso (relación 1-a-1 con el profesional).
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Especialidad, Recurso, Usuario
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


def _validar_usuario_vinculable(
    db: Session,
    empresa_id: int,
    usuario_id: int | None,
    *,
    recurso_id_actual: int | None = None,
) -> None:
    """Valida el vínculo recurso→usuario antes de guardarlo.

    - usuario_id None: desvincular o sin vínculo → nada que validar.
    - El usuario debe existir y ser de ESTA empresa (Regla 1: nadie vincula un
      usuario de otra empresa).
    - El usuario no puede estar ya vinculado a OTRO recurso (1-a-1). Al editar,
      se excluye el propio recurso del chequeo.
    """
    if usuario_id is None:
        return

    usuario = db.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id, Usuario.empresa_id == empresa_id
        )
    )
    if usuario is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "El usuario a vincular no existe o no es de esta empresa",
        )

    condiciones = [
        Recurso.usuario_id == usuario_id,
        Recurso.empresa_id == empresa_id,
    ]
    if recurso_id_actual is not None:
        condiciones.append(Recurso.id != recurso_id_actual)
    ya_vinculado = db.scalar(select(Recurso).where(*condiciones))
    if ya_vinculado is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ese usuario ya está vinculado al recurso '{ya_vinculado.nombre}'. "
            "Desvinculalo primero de ese recurso.",
        )


def usuarios_vinculables(db: Session, empresa_id: int) -> list[dict]:
    """Usuarios activos de la empresa, con el recurso al que ya están vinculados.

    Alimenta el selector "Usuario vinculado" del formulario de recurso. Marca
    cuáles están libres (recurso_id None) y cuáles ya tienen recurso, para que
    la UI respete el 1-a-1.
    """
    usuarios = list(
        db.scalars(
            select(Usuario)
            .where(Usuario.empresa_id == empresa_id, Usuario.activo.is_(True))
            .order_by(Usuario.nombre)
        )
    )
    # Vínculos existentes: usuario_id -> recurso
    recursos_vinculados = list(
        db.scalars(
            select(Recurso).where(
                Recurso.empresa_id == empresa_id,
                Recurso.usuario_id.is_not(None),
            )
        )
    )
    por_usuario = {r.usuario_id: r for r in recursos_vinculados}

    salida: list[dict] = []
    for u in usuarios:
        r = por_usuario.get(u.id)
        salida.append(
            {
                "id": u.id,
                "nombre": u.nombre,
                "email": u.email,
                "rol": u.rol,
                "recurso_id": r.id if r else None,
                "recurso_nombre": r.nombre if r else None,
            }
        )
    return salida


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
    _validar_usuario_vinculable(db, empresa_id, datos.usuario_id)
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

    # Si se toca el vínculo con un usuario, validarlo (empresa + 1-a-1).
    if "usuario_id" in cambios:
        _validar_usuario_vinculable(
            db, empresa_id, cambios["usuario_id"], recurso_id_actual=recurso_id
        )

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
