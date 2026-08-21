"""Endpoints de la empresa actual: preset del rubro + landing pública editable."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import DB, EmpresaActual, UsuarioActual, gate_dueno
from app.core.rate_limit import limiter
from app.schemas.empresa import MiSuscripcionOut, SuscripcionOut, AutomatizacionesConfig, EmpresaActualOut, LandingConfig, ReglasReservaConfig, SeguimientoConfig, SenasConfigIn, SenasConfigOut
from app.services import empresa as svc
from app.services import mercadopago as mp

router = APIRouter(prefix="/empresa", tags=["empresa"])


@router.get("/actual", response_model=EmpresaActualOut)
def empresa_actual(empresa_id: EmpresaActual, db: DB) -> EmpresaActualOut:
    """Datos de la empresa logueada + el preset de su rubro (módulos, terminología)."""
    return svc.obtener_config(db, empresa_id)


@router.get("/landing", response_model=LandingConfig)
def leer_landing(empresa_id: EmpresaActual, db: DB) -> LandingConfig:
    """Contenido actual de la landing pública (pantalla "Mi página")."""
    return svc.obtener_landing(db, empresa_id)


@router.put(
    "/landing",
    response_model=LandingConfig,
    dependencies=[Depends(gate_dueno)],
)
def guardar_landing(datos: LandingConfig, empresa_id: EmpresaActual, db: DB) -> LandingConfig:
    """Guarda el contenido de la landing. Solo el dueño (config del negocio)."""
    return svc.actualizar_landing(db, empresa_id, datos)

@router.get(
    "/reglas-reserva",
    response_model=ReglasReservaConfig,
    dependencies=[Depends(gate_dueno)],
)
def leer_reglas_reserva(empresa_id: EmpresaActual, db: DB) -> ReglasReservaConfig:
    """Reglas de la reserva pública (anticipación, ventana, qué datos pedir)."""
    return svc.obtener_reglas_reserva(db, empresa_id)


@router.put(
    "/reglas-reserva",
    response_model=ReglasReservaConfig,
    dependencies=[Depends(gate_dueno)],
)
def guardar_reglas_reserva(
    datos: ReglasReservaConfig, empresa_id: EmpresaActual, db: DB
) -> ReglasReservaConfig:
    """Solo el dueño: cambia cómo le entran los turnos al negocio."""
    return svc.actualizar_reglas_reserva(db, empresa_id, datos)


@router.get(
    "/seguimiento",
    response_model=SeguimientoConfig,
    dependencies=[Depends(gate_dueno)],
)
def leer_seguimiento(empresa_id: EmpresaActual, db: DB) -> SeguimientoConfig:
    """Meta Pixel y Google Tag del negocio."""
    return svc.obtener_seguimiento(db, empresa_id)


@router.put(
    "/seguimiento",
    response_model=SeguimientoConfig,
    dependencies=[Depends(gate_dueno)],
)
def guardar_seguimiento(
    datos: SeguimientoConfig, empresa_id: EmpresaActual, db: DB
) -> SeguimientoConfig:
    return svc.actualizar_seguimiento(db, empresa_id, datos)


@router.get("/senas", response_model=SenasConfigOut, dependencies=[Depends(gate_dueno)])
def ver_senas(empresa_id: EmpresaActual, db: DB) -> SenasConfigOut:
    """Config de señas con Mercado Pago (solo el dueño)."""
    return svc.config_senas(db, empresa_id)


@router.put("/senas", response_model=SenasConfigOut, dependencies=[Depends(gate_dueno)])
def guardar_senas(datos: SenasConfigIn, empresa_id: EmpresaActual, db: DB) -> SenasConfigOut:
    """Activa/desactiva señas, fija el monto y conecta la cuenta de MP."""
    if datos.sena_activa and not datos.sena_monto:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Para activar señas hay que definir el monto.",
        )
    try:
        return svc.guardar_senas(db, empresa_id, datos)
    except mp.TokenInvalido as e:
        # 422 y no 500: no es un error del sistema, es un dato mal pegado.
        # El mensaje viene escrito para mostrárselo al dueño tal cual.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e


@router.post("/senas/probar", dependencies=[Depends(gate_dueno)])
def probar_senas(empresa_id: EmpresaActual, db: DB) -> dict:
    """Revalida contra Mercado Pago el token ya guardado.

    Es el botón que permite contestar «¿está funcionando?» sin tener que
    esperar a que un cliente intente pagar.
    """
    try:
        cuenta = svc.probar_mp(db, empresa_id)
    except mp.TokenInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    return {"ok": True, "cuenta": cuenta}


@router.get(
    "/automatizaciones",
    response_model=AutomatizacionesConfig,
    dependencies=[Depends(gate_dueno)],
)
def ver_automatizaciones(empresa_id: EmpresaActual, db: DB) -> AutomatizacionesConfig:
    """Config de campañas / automatizaciones (solo el dueño)."""
    return svc.config_automatizaciones(db, empresa_id)


@router.put(
    "/automatizaciones",
    response_model=AutomatizacionesConfig,
    dependencies=[Depends(gate_dueno)],
)
def guardar_automatizaciones(
    datos: AutomatizacionesConfig, empresa_id: EmpresaActual, db: DB
) -> AutomatizacionesConfig:
    return svc.guardar_automatizaciones(db, empresa_id, datos.model_dump())


@router.post("/automatizaciones/probar", dependencies=[Depends(gate_dueno)])
@limiter.limit("10/hour")
def probar_campana(
    request: Request, tipo: str, usuario: UsuarioActual, empresa_id: EmpresaActual, db: DB
) -> dict:
    """Manda una MUESTRA de la campaña al email que indique el dueño.

    Sirve para ver cómo queda sin esperar a que se cumpla la condición real
    (que alguien cumpla años o lleve 60 días sin venir).
    """
    validos = {"recordatorio_24h", "recordatorio_2h", "cumple", "resena_google", "inactivos"}
    if tipo not in validos:
        raise HTTPException(status_code=400, detail="Campaña desconocida")

    # El destino ya NO se elige: va al email del usuario que pidió la prueba.
    # Antes era un parámetro libre, así que con una cuenta de prueba gratuita
    # se podía mandar cualquier contenido a cualquier destinatario desde la
    # casilla oficial de Turnos360 (phishing con marca propia), y de paso
    # quemar la cuota diaria de envíos que comparten todos los negocios.
    destino = usuario.email
    try:
        from app.tasks.emails import enviar_prueba_campana

        enviar_prueba_campana.delay(empresa_id, tipo, destino)
    except Exception:
        raise HTTPException(status_code=503, detail="No se pudo encolar el envío")
    return {"detalle": f"Te mandamos la prueba a {destino}. Puede tardar un minuto."}


@router.get(
    "/mi-suscripcion",
    response_model=MiSuscripcionOut,
    dependencies=[Depends(gate_dueno)],
)
def leer_mi_suscripcion(empresa_id: EmpresaActual, db: DB) -> MiSuscripcionOut:
    """Plan, vencimiento, historial de pagos y datos para transferir.

    Solo el dueño: es información comercial del negocio, no operativa.
    """
    from app.services.suscripcion import mi_suscripcion

    return MiSuscripcionOut(**mi_suscripcion(db, empresa_id))


@router.get("/suscripcion", response_model=SuscripcionOut)
def leer_suscripcion(empresa_id: EmpresaActual, db: DB) -> SuscripcionOut:
    """Estado de la suscripción del negocio (para la pantalla de Configuración)."""
    from app.models.organizacion import Empresa
    from app.services.suscripcion import estado_suscripcion

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return SuscripcionOut(**estado_suscripcion(empresa))
