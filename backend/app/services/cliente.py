"""Lógica de negocio de Cliente (E2).

REGLA 1 hecha código: toda función recibe empresa_id y filtra por él SIEMPRE.
El router nunca toca la base directamente; delega acá. Así la lógica
multi-tenant vive en un solo lugar y se puede reusar (p. ej. desde Celery).
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Cliente
from app.schemas.cliente import ClienteCrear, ClienteEditar


def listar(
    db: Session,
    empresa_id: int,
    *,
    buscar: str | None = None,
    solo_activos: bool = True,
    offset: int = 0,
    limite: int = 50,
) -> tuple[int, list[Cliente]]:
    """Devuelve (total, página) de clientes de ESTA empresa.

    Filtra siempre por empresa_id. Opcionalmente por texto (nombre, apellido,
    DNI, teléfono o email) y por estado activo. Devuelve el total para que
    el frontend pueda paginar.
    """
    condiciones = [Cliente.empresa_id == empresa_id]
    if solo_activos:
        condiciones.append(Cliente.activo.is_(True))
    if buscar:
        patron = f"%{buscar}%"
        condiciones.append(
            or_(
                Cliente.nombre.ilike(patron),
                Cliente.apellido.ilike(patron),
                Cliente.dni.ilike(patron),
                Cliente.telefono.ilike(patron),
                Cliente.email.ilike(patron),
            )
        )

    # total (para la paginación) — cuenta aplicando los mismos filtros
    total = db.scalar(
        select(func.count()).select_from(Cliente).where(*condiciones)
    )

    # página de resultados, ordenada por apellido y nombre
    items = list(
        db.scalars(
            select(Cliente)
            .where(*condiciones)
            .order_by(Cliente.apellido, Cliente.nombre)
            .offset(offset)
            .limit(limite)
        )
    )
    return total or 0, items


def obtener(db: Session, empresa_id: int, cliente_id: int) -> Cliente | None:
    """Trae UN cliente, pero solo si pertenece a ESTA empresa.

    La doble condición (id Y empresa_id) es lo que impide que la empresa A
    acceda a un cliente de la empresa B pasando un id ajeno.
    """
    return db.scalar(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.empresa_id == empresa_id,
        )
    )


def crear(db: Session, empresa_id: int, datos: ClienteCrear) -> Cliente:
    """Crea un cliente en ESTA empresa.

    El empresa_id lo ponemos NOSOTROS desde el token, nunca viene del body:
    el cliente no puede elegir en qué empresa crear (Regla 1).
    """
    cliente = Cliente(empresa_id=empresa_id, **datos.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def editar(
    db: Session, empresa_id: int, cliente_id: int, datos: ClienteEditar
) -> Cliente | None:
    """Edita solo los campos que vengan; devuelve None si no es de esta empresa."""
    cliente = obtener(db, empresa_id, cliente_id)
    if cliente is None:
        return None

    # exclude_unset: solo los campos que el usuario realmente mandó
    cambios = datos.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(cliente, campo, valor)

    db.commit()
    db.refresh(cliente)
    return cliente


def desactivar(db: Session, empresa_id: int, cliente_id: int) -> bool:
    """Baja lógica: marca activo=False (no borra). Devuelve si lo encontró.

    No borramos físicamente porque el cliente tiene historial, turnos y pagos
    asociados. Desactivar preserva la integridad y permite reactivar.
    """
    cliente = obtener(db, empresa_id, cliente_id)
    if cliente is None:
        return False
    cliente.activo = False
    db.commit()
    return True