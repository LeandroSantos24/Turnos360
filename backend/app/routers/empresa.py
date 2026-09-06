"""Endpoints de la empresa actual: preset del rubro + landing pública editable."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import DB, EmpresaActual, UsuarioActual, gate_dueno
from app.core.rate_limit import limiter
from app.schemas.empresa import AvisoPagoIn, CambioPlanIn, MiSuscripcionOut, SuscripcionOut, AutomatizacionesConfig, EmpresaActualOut, LandingConfig, ReglasReservaConfig, SeguimientoConfig, SenasConfigIn, SenasConfigOut
from app.services import empresa as svc
from app.services import mercadopago as mp
from app.services import mp_debito
from app.services import mp_suscripcion as mp_sus

log = logging.getLogger("turnos360.empresa")

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
    # encolar(): «Enviarme una prueba» existe para que el dueño VEA el mail
    # antes de dejar la campaña andando. Si se encola sin worker, ve un cartel
    # verde y ningún mail, y la conclusión que saca es que las campañas no
    # funcionan.
    from app.core.cola import Resultado, encolar
    from app.tasks.emails import enviar_prueba_campana

    resultado = encolar(enviar_prueba_campana, empresa_id, tipo, destino)
    if resultado is Resultado.FALLO:
        raise HTTPException(status_code=503, detail="No se pudo mandar la prueba")
    if resultado is Resultado.EN_LINEA:
        return {"detalle": f"Te mandamos la prueba a {destino}."}
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


@router.post("/suscripcion/pagar-mp", dependencies=[Depends(gate_dueno)])
@limiter.limit("10/minute")
def pagar_suscripcion_mp(
    request: Request,
    empresa_id: EmpresaActual,
    db: DB,
    plan: str | None = None,
) -> dict:
    """Arranca el pago de la cuota —o del plan elegido— por Mercado Pago.

    Devuelve la URL a la que hay que mandar al dueño. El pago se acredita solo
    cuando Mercado Pago avisa por el webhook y nosotros verificamos el pago
    contra su API: acá no se toca ni el plan ni el vencimiento. Eso es lo que
    hace que un checkout abandonado no deje a nadie con un plan que no pagó.

    `plan` viaja hasta el webhook dentro del external_reference. Sin él, un
    upgrade cobraría el precio nuevo y dejaría a la empresa en el plan viejo.
    """
    from app.core import planes
    from app.models.organizacion import Empresa

    if not mp_sus.esta_activo():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El pago con Mercado Pago todavía no está habilitado. "
            "Podés pagar por transferencia con los datos de esta pantalla.",
        )
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    # Se valida ACÁ y no en el webhook. Enterprise no tiene precio de lista,
    # así que un link de pago para Enterprise cobraría el precio de entrada y
    # activaría cupos ilimitados: es la única forma de que este endpoint
    # regale un plan, y por eso se corta antes de generar nada.
    if plan is not None:
        elegido = planes.plan_de(plan)
        if not planes.se_vende_solo(elegido):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Ese plan no se contrata online. Escribinos y lo armamos con vos.",
            )
        plan = elegido.value

    url = mp_sus.crear_preferencia(empresa, plan)
    if not url:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No se pudo generar el link de pago. Probá de nuevo en un rato o "
            "pagá por transferencia.",
        )
    return {"url": url}


@router.post("/suscripcion/debito-automatico", dependencies=[Depends(gate_dueno)])
@limiter.limit("10/minute")
def activar_debito_automatico(
    request: Request,
    empresa_id: EmpresaActual,
    usuario: UsuarioActual,
    db: DB,
    plan: str,
) -> dict:
    """Activa el débito automático: la cuota se cobra sola todos los meses.

    Devuelve la URL del checkout de Mercado Pago donde el dueño carga la
    tarjeta. La tarjeta no pasa por acá en ningún momento — ver el docstring
    de services/mp_debito.py.

    ACÁ NO SE ACTIVA NINGÚN PLAN. La empresa queda igual que antes hasta que
    Mercado Pago cobre el primer mes y avise por el webhook. Un checkout
    abandonado no puede dejar a nadie con un plan que nadie pagó, y es el
    mismo criterio que ya usa el pago suelto.
    """
    from app.core import planes
    from app.models.organizacion import Empresa

    if not mp_debito.esta_activo():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El débito automático todavía no está habilitado. Podés pagar "
            "por transferencia o con el link de Mercado Pago.",
        )

    elegido = planes.plan_de(plan)
    if not planes.se_vende_solo(elegido):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese plan no se contrata online. Escribinos y lo armamos con vos.",
        )

    if mp_debito.vigente(db, empresa_id) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya tenés un débito automático. Si querés cambiar de plan o de "
            "tarjeta, cancelalo primero desde esta misma pantalla.",
        )

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    # A qué mail le cobra Mercado Pago. Es el del dueño que está pidiendo el
    # débito: es su tarjeta y son sus avisos de cada cobro. El email público
    # del negocio no sirve —suele atenderlo recepción— y esto es plata.
    email = (usuario.email or "").strip()
    if not email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Necesitamos tu email para activar el débito automático. "
            "Cargalo en tu perfil y volvé a intentar.",
        )

    url = mp_debito.crear(db, empresa, elegido.value, email)
    if not url:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No se pudo activar el débito automático. Probá de nuevo en un "
            "rato, o pagá por transferencia mientras tanto.",
        )
    return {"url": url}


@router.post(
    "/suscripcion/debito-automatico/sincronizar", dependencies=[Depends(gate_dueno)]
)
@limiter.limit("20/minute")
def sincronizar_debito_automatico(
    request: Request, empresa_id: EmpresaActual, db: DB
) -> dict:
    """Le pregunta a Mercado Pago cómo quedó la suscripción, ahora.

    LO LLAMA LA PANTALLA CUANDO EL DUEÑO VUELVE DEL CHECKOUT.

    Sin esto, el que acaba de poner la tarjeta vuelve al panel y ve «te falta
    poner la tarjeta»: nuestra fila sigue en `pending` hasta que llegue el
    webhook, que puede tardar. La persona acaba de hacer exactamente lo que le
    pedimos y la pantalla le dice que no lo hizo — es el peor momento posible
    para no creerle.

    No reemplaza al webhook: es el atajo para el único instante en que sabemos
    que algo cambió y todavía no nos avisaron. Si Mercado Pago no responde, la
    fila queda como estaba y la pantalla muestra lo de antes.
    """
    fila = mp_debito.vigente(db, empresa_id)
    if fila is None:
        return {"estado": None}
    actualizada = mp_debito.sincronizar(db, fila.preapproval_id)
    return {"estado": actualizada.estado if actualizada else fila.estado}


@router.delete("/suscripcion/debito-automatico", dependencies=[Depends(gate_dueno)])
@limiter.limit("10/minute")
def cancelar_debito_automatico(
    request: Request,
    empresa_id: EmpresaActual,
    usuario: UsuarioActual,
    db: DB,
) -> dict:
    """Corta el débito automático. El servicio sigue hasta el fin del mes pago.

    No toca `suscripcion_vence`: lo que ya se cobró, se usa. Cortar en el acto
    algo que está pagado se siente como un robo, aunque el botón diga
    «cancelar».
    """
    if not mp_debito.cancelar(db, empresa_id, quien=usuario.email or "dueño"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No pudimos cancelar el débito automático. Probá de nuevo en un "
            "rato; si sigue igual, escribinos y lo cortamos nosotros.",
        )
    return {"ok": True}


@router.post("/suscripcion/cambiar-plan", dependencies=[Depends(gate_dueno)])
@limiter.limit("10/minute")
def cambiar_plan(
    request: Request,
    datos: CambioPlanIn,
    empresa_id: EmpresaActual,
    usuario: UsuarioActual,
    db: DB,
) -> dict:
    """Cambia de plan sin que intervenga nadie de Turnos360.

    SUBIR se paga: este endpoint NO activa el plan, devuelve el link de pago.
    El plan se activa cuando la plata entra de verdad, por el webhook. Si
    activara acá, cualquiera subiría a Multi, cerraría el checkout y se
    quedaría con el plan gratis.

    BAJAR se anota: el ciclo actual ya está pagado y se usa entero. Al vencer,
    el barrido diario aplica la baja.
    """
    from app.core import planes
    from app.models.organizacion import Empresa
    from app.services import cobranza

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    destino = planes.plan_de(datos.plan)
    if not planes.se_vende_solo(destino):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese plan no se contrata online. Escribinos y lo armamos con vos.",
        )

    movimiento = cobranza.cambio_de_plan(empresa, destino.value)

    if movimiento == "mismo":
        # Puede ser el que quiere CANCELAR una baja: eligió de nuevo el plan
        # que ya tiene. Es la forma más natural de arrepentirse y no hace
        # falta un botón aparte.
        if empresa.plan_programado:
            cobranza.cancelar_baja_programada(db, empresa, hecho_por=usuario.email)
            db.commit()
            return {
                "accion": "cancelada",
                "detalle": f"Listo, seguís en {planes.limites_de(empresa.plan).etiqueta}.",
            }
        return {"accion": "ninguna", "detalle": "Ya estás en ese plan."}

    if movimiento == "baja":
        cuando = cobranza.programar_baja(db, empresa, destino.value, hecho_por=usuario.email)
        db.commit()
        if cuando is None:
            return {
                "accion": "aplicada",
                "detalle": f"Pasaste a {planes.limites_de(destino.value).etiqueta}.",
            }
        return {
            "accion": "programada",
            "desde": cuando.isoformat(),
            "detalle": (
                f"El mes que ya pagaste lo usás entero: seguís en "
                f"{planes.limites_de(empresa.plan).etiqueta} hasta el "
                f"{cuando.strftime('%d/%m/%Y')} y ahí pasás a "
                f"{planes.limites_de(destino.value).etiqueta}."
            ),
        }

    # Sube: hay que pagar.
    if not mp_sus.esta_activo():
        return {
            "accion": "pagar_transferencia",
            "detalle": (
                f"Para pasar a {planes.limites_de(destino.value).etiqueta} "
                "transferí el importe con los datos de esta pantalla y avisanos "
                "acá mismo. Lo activamos apenas lo veamos en el banco."
            ),
        }

    url = mp_sus.crear_preferencia(empresa, destino.value)
    if not url:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No se pudo generar el link de pago. Probá de nuevo en un rato o "
            "pagá por transferencia.",
        )
    return {"accion": "pagar", "url": url}


@router.post("/suscripcion/aviso-pago", dependencies=[Depends(gate_dueno)])
@limiter.limit("10/minute")
def avisar_pago(
    request: Request,
    datos: AvisoPagoIn,
    empresa_id: EmpresaActual,
    usuario: UsuarioActual,
    db: DB,
) -> dict:
    """El dueño avisa que transfirió. Queda pendiente de confirmación.

    NO mueve el vencimiento: una transferencia tarda en verse en la cuenta y
    dar por cobrado lo que alguien dice que pagó convierte la cobranza en un
    número de buena fe. Lo confirma Leandro contra el banco.
    """
    from app.models.organizacion import Empresa
    from app.services import cobranza

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")

    cobranza.registrar_aviso(
        db,
        empresa,
        metodo="transferencia",
        monto=datos.monto,
        referencia=datos.referencia,
        avisado_por=usuario.email,
    )

    # Este es el aviso MÁS urgente de los dos: es el único que necesita que
    # alguien haga algo (verificarlo contra el banco). El de Mercado Pago se
    # acredita solo; este se queda esperando.
    try:
        from app.core.cola import encolar
        from app.tasks.emails import avisar_pago_recibido

        encolar(
            avisar_pago_recibido,
            empresa_id,
            float(datos.monto or 0),
            "transferencia",
            referencia=datos.referencia,
            confirmado=False,
        )
    except Exception:
        log.exception("No se pudo avisar la transferencia (empresa %s)", empresa_id)

    return {
        "detalle": (
            "¡Gracias! Tu pago quedó en proceso. Lo confirmamos dentro de las "
            "próximas 24 horas hábiles y vas a ver el vencimiento actualizado "
            "en esta misma pantalla."
        )
    }


@router.get("/suscripcion/aviso-pago", dependencies=[Depends(gate_dueno)])
def leer_aviso_pago(empresa_id: EmpresaActual, db: DB) -> dict:
    """¿Hay un aviso de pago esperando confirmación? Para no repetir el cartel."""
    from app.services import cobranza

    aviso = cobranza.aviso_pendiente(db, empresa_id)
    if aviso is None:
        return {"pendiente": False}
    return {
        "pendiente": True,
        "creado_en": aviso.creado_en.isoformat() if aviso.creado_en else None,
        "monto": float(aviso.monto) if aviso.monto is not None else None,
    }


@router.get("/suscripcion", response_model=SuscripcionOut)
def leer_suscripcion(empresa_id: EmpresaActual, db: DB) -> SuscripcionOut:
    """Estado de la suscripción del negocio (para la pantalla de Configuración)."""
    from app.models.organizacion import Empresa
    from app.services.suscripcion import estado_suscripcion

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return SuscripcionOut(**estado_suscripcion(empresa))
