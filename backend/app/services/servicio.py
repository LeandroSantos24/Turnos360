"""Lógica de negocio de Servicio (E2). Mismo patrón multi-tenant que clientes."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Recurso, Servicio, ServicioSucursal, Sucursal
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


def _recursos_de(db: Session, empresa_id: int, ids: list[int]) -> list[Recurso]:
    """Recursos de ESTA empresa entre los ids pedidos (filtra ajenos: Regla 1)."""
    if not ids:
        return []
    return list(
        db.scalars(
            select(Recurso).where(
                Recurso.empresa_id == empresa_id, Recurso.id.in_(ids)
            )
        )
    )


def crear(db: Session, empresa_id: int, datos: ServicioCrear) -> Servicio:
    payload = datos.model_dump()
    recurso_ids = payload.pop("recurso_ids", [])
    payload.pop("sucursales", None)
    servicio = Servicio(empresa_id=empresa_id, **payload)
    servicio.recursos = _recursos_de(db, empresa_id, recurso_ids)
    db.add(servicio)
    db.flush()
    # El listener del modelo ya lo dejó ofrecido en todos los locales abiertos.
    # Si el dueño eligió algunos en particular, se reemplaza ahora.
    if datos.sucursales is not None:
        fijar_sucursales(db, empresa_id, servicio, datos.sucursales)
    db.commit()
    db.refresh(servicio)
    return servicio


def editar(
    db: Session, empresa_id: int, servicio_id: int, datos: ServicioEditar
) -> Servicio | None:
    servicio = obtener(db, empresa_id, servicio_id)
    if servicio is None:
        return None
    cambios = datos.model_dump(exclude_unset=True)
    recurso_ids = cambios.pop("recurso_ids", None)
    cambios.pop("sucursales", None)
    for campo, valor in cambios.items():
        setattr(servicio, campo, valor)
    if recurso_ids is not None:  # viene la lista => reemplaza el set completo
        servicio.recursos = _recursos_de(db, empresa_id, recurso_ids)
    if datos.sucursales is not None:
        fijar_sucursales(db, empresa_id, servicio, datos.sucursales)
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

# ══════════════════════════════════════════════════════════════════════
#  En qué locales se ofrece cada servicio (E16, paso 3b)
# ══════════════════════════════════════════════════════════════════════


def sucursales_de(db: Session, servicio_id: int) -> list[ServicioSucursal]:
    return list(
        db.scalars(
            select(ServicioSucursal)
            .where(ServicioSucursal.servicio_id == servicio_id)
            .order_by(ServicioSucursal.sucursal_id)
        )
    )


def mapa_de_sucursales(
    db: Session, servicio_ids: list[int]
) -> dict[int, list[ServicioSucursal]]:
    """Los locales de VARIOS servicios en una sola consulta.

    Sin esto, listar 30 servicios haría 30 consultas más — el clásico N+1 que
    no se nota en desarrollo con tres servicios y sí en un negocio real.
    """
    if not servicio_ids:
        return {}
    filas = db.scalars(
        select(ServicioSucursal)
        .where(ServicioSucursal.servicio_id.in_(servicio_ids))
        .order_by(ServicioSucursal.sucursal_id)
    )
    mapa: dict[int, list[ServicioSucursal]] = {}
    for f in filas:
        mapa.setdefault(f.servicio_id, []).append(f)
    return mapa


def fijar_sucursales(
    db: Session, empresa_id: int, servicio: Servicio, pedidas
) -> None:
    """Reemplaza los locales donde se ofrece el servicio.

    Dos candados:

    1. Un local que no es de esta empresa no existe (Regla 1). La FK compuesta
       lo rechazaría igual, pero un 404 explica y un IntegrityError no.
    2. No puede quedar en cero. Un servicio ofrecido en ningún lado no da
       error: da un servicio invisible, que es peor, porque nadie se entera
       hasta que un cliente no lo encuentra en la página de reservas.
    """
    if not pedidas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "El servicio tiene que ofrecerse en al menos un local. Si ya no lo "
            "prestás en ninguno, desactivalo.",
        )

    propias = set(
        db.scalars(select(Sucursal.id).where(Sucursal.empresa_id == empresa_id))
    )
    ajenas = [p.sucursal_id for p in pedidas if p.sucursal_id not in propias]
    if ajenas:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Alguno de esos locales no existe en este negocio."
        )

    db.query(ServicioSucursal).filter(
        ServicioSucursal.servicio_id == servicio.id
    ).delete(synchronize_session=False)

    vistas: set[int] = set()
    for p in pedidas:
        if p.sucursal_id in vistas:
            continue
        vistas.add(p.sucursal_id)
        db.add(
            ServicioSucursal(
                empresa_id=empresa_id,
                servicio_id=servicio.id,
                sucursal_id=p.sucursal_id,
                precio=p.precio,
            )
        )
    db.flush()


def precio_en(db: Session, servicio: Servicio, sucursal_id: int) -> float | None:
    """Cuánto sale este servicio EN ESE local.

    El precio propio del local si lo tiene; si no, el del servicio. Ese
    fallback es lo que hace que subir el precio general alcance con tocarlo
    una vez.
    """
    fila = db.get(ServicioSucursal, (servicio.id, sucursal_id))
    if fila is not None and fila.precio is not None:
        return float(fila.precio)
    return servicio.precio


def se_ofrece_en(db: Session, servicio_id: int, sucursal_id: int) -> bool:
    return db.get(ServicioSucursal, (servicio_id, sucursal_id)) is not None
