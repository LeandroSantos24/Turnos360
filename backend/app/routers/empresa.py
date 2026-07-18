"""Endpoints de la empresa actual: preset del rubro + landing pública editable."""

from fastapi import APIRouter, Depends, HTTPException, HTTPException, status

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.empresa import SuscripcionOut, AutomatizacionesConfig, EmpresaActualOut, LandingConfig, SenasConfigIn, SenasConfigOut
from app.services import empresa as svc

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
    return svc.guardar_senas(db, empresa_id, datos)


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
def probar_campana(
    tipo: str, destino: str, empresa_id: EmpresaActual, db: DB
) -> dict:
    """Manda una MUESTRA de la campaña al email que indique el dueño.

    Sirve para ver cómo queda sin esperar a que se cumpla la condición real
    (que alguien cumpla años o lleve 60 días sin venir).
    """
    validos = {"recordatorio_24h", "recordatorio_2h", "cumple", "resena_google", "inactivos"}
    if tipo not in validos:
        raise HTTPException(status_code=400, detail="Campaña desconocida")
    try:
        from app.tasks.emails import enviar_prueba_campana

        enviar_prueba_campana.delay(empresa_id, tipo, destino)
    except Exception:
        raise HTTPException(status_code=503, detail="No se pudo encolar el envío")
    return {"detalle": f"Te mandamos la prueba a {destino}. Puede tardar un minuto."}


@router.get("/suscripcion", response_model=SuscripcionOut)
def leer_suscripcion(empresa_id: EmpresaActual, db: DB) -> SuscripcionOut:
    """Estado de la suscripción del negocio (para la pantalla de Configuración)."""
    from app.models.organizacion import Empresa
    from app.services.suscripcion import estado_suscripcion

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return SuscripcionOut(**estado_suscripcion(empresa))
