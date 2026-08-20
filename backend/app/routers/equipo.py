"""Equipo del negocio: lo que el dueño puede ver y hacer con sus usuarios.

Todo el router va con gate_dueno. Es información sobre las cuentas del
personal y la capacidad de generar un link para cambiarles la contraseña:
no es algo que tenga que ver recepción ni un profesional.
"""

from fastapi import APIRouter, Depends, Request

from app.api.deps import DB, EmpresaActual, UsuarioActual, gate_dueno
from app.core.rate_limit import limiter
from app.schemas.equipo import LinkRestablecerOut, MiembroEquipoOut
from app.services import equipo as svc

router = APIRouter(prefix="/equipo", tags=["equipo"], dependencies=[Depends(gate_dueno)])


@router.get("/usuarios", response_model=list[MiembroEquipoOut])
def listar_equipo(empresa_id: EmpresaActual, db: DB) -> list[MiembroEquipoOut]:
    """Los usuarios del negocio, con su rol y si pueden recuperar su clave solos."""
    return svc.listar_equipo(db, empresa_id)


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
