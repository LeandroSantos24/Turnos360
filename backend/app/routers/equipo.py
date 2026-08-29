"""Equipo del negocio: lo que el dueño puede ver y hacer con sus usuarios.

Todo el router va con gate_dueno. Es información sobre las cuentas del
personal y la capacidad de generar un link para cambiarles la contraseña:
no es algo que tenga que ver recepción ni un profesional.
"""

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import DB, EmpresaActual, UsuarioActual, gate_dueno
from app.core.rate_limit import limiter
from app.schemas.equipo import (
    LinkRestablecerOut,
    MiembroCrear,
    MiembroEditar,
    MiembroEquipoOut,
)
from app.services import equipo as svc

router = APIRouter(prefix="/equipo", tags=["equipo"], dependencies=[Depends(gate_dueno)])


@router.get("/usuarios", response_model=list[MiembroEquipoOut])
def listar_equipo(empresa_id: EmpresaActual, db: DB) -> list[MiembroEquipoOut]:
    """Los usuarios del negocio, con su rol y si pueden recuperar su clave solos."""
    return svc.listar_equipo(db, empresa_id)


@router.post(
    "/usuarios",
    response_model=MiembroEquipoOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_miembro(
    datos: MiembroCrear, empresa_id: EmpresaActual, db: DB
) -> MiembroEquipoOut:
    """Da de alta un empleado.

    Hasta ahora esto solo lo podía hacer el super-admin: para sumar una
    recepcionista había que escribirnos. El rol viene acotado por el schema a
    recepción o profesional.
    """
    return svc.crear_miembro(db, empresa_id, datos)


@router.patch("/usuarios/{usuario_id}", response_model=MiembroEquipoOut)
def editar_miembro(
    usuario_id: int,
    datos: MiembroEditar,
    usuario: UsuarioActual,
    empresa_id: EmpresaActual,
    db: DB,
) -> MiembroEquipoOut:
    """Cambia nombre, email, rol o activación de un empleado.

    Corregirle el nombre a alguien era, hasta ahora, un pedido por WhatsApp.
    """
    return svc.editar_miembro(db, empresa_id, usuario_id, datos, quien_pide=usuario)


@router.post(
    "/usuarios/{usuario_id}/link-restablecer",
    response_model=LinkRestablecerOut,
)
@limiter.limit("20/hour")
def link_restablecer(
    request: Request,
    usuario_id: int,
    usuario: UsuarioActual,
    empresa_id: EmpresaActual,
    db: DB,
) -> LinkRestablecerOut:
    """Genera un link de un solo uso para que un empleado elija contraseña nueva.

    Pensado para el caso real de una PyME: el empleado no tiene email (o no lo
    revisa), se olvidó la clave, y está parado en el mostrador. El dueño
    genera el link y se lo manda por WhatsApp.

    El link vence en 60 minutos y sirve una sola vez, igual que el de
    "olvidé mi contraseña". Queda registrado en la auditoría quién lo generó.
    """
    return svc.generar_link_restablecer(
        db,
        empresa_id=empresa_id,
        quien_pide=usuario,
        usuario_id=usuario_id,
        ip=request.headers.get("x-real-ip") or (request.client.host if request.client else None),
    )
