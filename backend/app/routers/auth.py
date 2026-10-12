"""Endpoints de autenticación: login y refresh (E2)."""


from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from jwt.exceptions import InvalidTokenError
from sqlalchemy import func, select

from app.api.deps import DB, UsuarioActual, verificar_empresa_activa
from app.core.seguridad import (
    SCOPE_EMPRESA,
    decodificar_token,
)
from app.core.rate_limit import limiter
import datetime as dt
import hashlib
import logging
import secrets

from app.core.crypto import hash_clave, hash_senuelo, necesita_rehash, verificar_clave
from app.models import Empresa, Sucursal, Usuario
from app.services import sesiones
from app.schemas.auth import (
    CambiarPasswordRequest,
    CerrarSesionesRequest,
    LoginRequest,
    OlvidePasswordRequest,
    PerfilActualizar,
    RefreshRequest,
    RestablecerPasswordRequest,
    SesionRenovada,
    TokenResponse,
    UsuarioMe,
)

router = APIRouter(prefix="/auth", tags=["auth"])

log = logging.getLogger(__name__)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, datos: LoginRequest, db: DB) -> TokenResponse:
    """Valida email + clave y devuelve un par de tokens (access + refresh).

    El login NO filtra por empresa: el email es único dentro de cada empresa,
    pero el usuario aún no nos dijo quién es. Buscamos por email y, si la clave
    coincide, el empresa_id queda fijado en los tokens que emitimos.
    """
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email o contraseña incorrectos",
    )

    # 1. Buscar el usuario por email.
    #    Sin distinguir mayúsculas: para una persona Juan@Gmail.com y
    #    juan@gmail.com son la misma dirección.
    #    one_or_none() y no scalar(): si alguna vez hubiera un duplicado,
    #    que explote ruidosamente en vez de devolver una fila al azar, que
    #    es lo que hacía antes y por lo que alguien podía terminar logueado
    #    en la empresa equivocada.
    usuario = db.scalars(
        select(Usuario).where(func.lower(Usuario.email) == datos.email.lower())
    ).one_or_none()

    # 2. Verificar que exista, esté activo y la clave coincida con el hash.
    #    Verificamos la clave SIEMPRE (aunque el usuario no exista) para no
    #    revelar por el tiempo de respuesta si un email está registrado o no.
    hash_guardado = usuario.hash_clave if usuario else hash_senuelo()
    clave_ok = verificar_clave(datos.clave, hash_guardado)

    # Una cuenta invitada que todavía no eligió su contraseña no entra (su
    # hash es de una clave al azar que nadie conoce, pero no se confía en eso).
    if usuario is None or not usuario.activo or usuario.activacion_pendiente or not clave_ok:
        raise credenciales_invalidas

    # 2b. Si la clave estaba guardada con menos iteraciones de las que
    #     usamos hoy, se rehashea AHORA — que es el único momento en que
    #     tenemos la clave en texto plano. Sin esto, subir el costo del
    #     hash no protege a nadie que ya tenga cuenta.
    #
    #     Nunca puede voltear el login: si falla, el usuario entra igual
    #     con su hash viejo y se reintenta la próxima vez.
    #
    #     Va dentro de un SAVEPOINT (begin_nested) y no de un rollback
    #     pelado: si algo falla, se deshace SOLO este cambio. Un
    #     db.rollback() acá se llevaría puesto cualquier otro trabajo
    #     pendiente en la misma sesión — hoy no hay ninguno, pero el día
    #     que alguien agregue una escritura arriba, esto la borraría sin
    #     que nadie lo note.
    if necesita_rehash(usuario.hash_clave):
        try:
            with db.begin_nested():
                usuario.hash_clave = hash_clave(datos.clave)
            db.commit()
        except Exception:
            log.exception("no pude rehashear la clave", extra={"usuario_id": usuario.id})

    # 3. La empresa no debe estar pausada por el super-admin.
    #    Va DESPUÉS de validar la clave a propósito: solo un usuario legítimo
    #    (que ya probó email + contraseña) se entera de que el servicio está
    #    pausado. A un atacante le seguimos respondiendo "credenciales inválidas"
    #    y no le revelamos nada sobre la empresa.
    empresa = db.get(Empresa, usuario.empresa_id)
    verificar_empresa_activa(empresa)

    # 4. Sesión nueva en el servidor + tokens con el empresa_id y rol fijados
    #    adentro. Registra también el último ingreso.
    access, refresh = sesiones.ingresar(db, usuario, request)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, datos: RefreshRequest, db: DB) -> TokenResponse:
    """Recibe un refresh token válido y emite un par nuevo de tokens."""
    token_invalido = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido o vencido",
    )

    # 1. Validar el refresh token (firma, vencimiento, tipo 'refresh')
    try:
        payload = decodificar_token(
            datos.refresh_token,
            tipo_esperado="refresh",
            scope_esperado=SCOPE_EMPRESA,
        )
        usuario_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise token_invalido

    # 2. El usuario debe seguir existiendo y activo
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise token_invalido

    # 2.5. El refresh no debe ser de una sesión revocada (cambio de contraseña).
    #      Es el punto clave: sin esto, un refresh robado sobrevive al cambio
    #      de clave durante 7 días y se renueva solo, indefinidamente.
    if int(payload.get("tv", 0)) != int(usuario.token_version or 0):
        raise token_invalido

    # 3. La empresa no debe estar pausada: si no, no minteamos tokens nuevos.
    #    Sin esto, un usuario de una empresa pausada podría seguir refrescando
    #    su sesión para siempre (aunque cada access token resultante igual
    #    moriría en get_current_usuario, mejor cortarlo de raíz acá).
    empresa = db.get(Empresa, usuario.empresa_id)
    verificar_empresa_activa(empresa)

    # 4. La sesión del servidor tiene que seguir abierta y este refresh ser
    #    el último que se emitió para ella (rota en cada renovación).
    access, refresh = sesiones.renovar(db, usuario, payload, request)
    return TokenResponse(access_token=access, refresh_token=refresh)


def _usuario_me(db, usuario: Usuario) -> UsuarioMe:
    """El usuario con el nombre de su negocio y de su local.

    El local se busca DENTRO de la empresa del usuario: un sucursal_id que no
    fuera de su negocio (no debería pasar) no filtra el nombre de otro.
    """
    empresa = db.get(Empresa, usuario.empresa_id)
    sucursal = db.scalar(
        select(Sucursal).where(
            Sucursal.id == usuario.sucursal_id,
            Sucursal.empresa_id == usuario.empresa_id,
        )
    )
    datos = UsuarioMe.model_validate(usuario)
    datos.empresa_nombre = empresa.nombre if empresa else None
    datos.sucursal_nombre = sucursal.nombre if sucursal else None
    return datos


def _sesion_nueva(db, request: Request, usuario: Usuario, detalle: str) -> SesionRenovada:
    """Después de cerrar todas: una sesión nueva para el dispositivo que lo pidió."""
    sesion = sesiones.crear(db, usuario, request)
    access, refresh = sesiones.tokens(usuario, sesion)
    db.commit()
    return SesionRenovada(access_token=access, refresh_token=refresh, detalle=detalle)


@router.get("/me", response_model=UsuarioMe)
def me(usuario: UsuarioActual, db: DB) -> UsuarioMe:
    """Devuelve los datos del usuario autenticado.

    Ruta protegida: sin un access token válido en el header, FastAPI corta
    con 401 antes de entrar acá (lo hace el guardián get_current_usuario).
    """
    return _usuario_me(db, usuario)


@router.patch("/me", response_model=UsuarioMe)
@limiter.limit("20/minute")
def actualizar_perfil(
    request: Request, datos: PerfilActualizar, usuario: UsuarioActual, db: DB
) -> UsuarioMe:
    """Cambia los datos propios que la persona puede tocar sola: el nombre.

    El schema es una lista cerrada (PerfilActualizar): aunque alguien mande
    rol, email o empresa_id en el JSON, Pydantic los descarta.
    """
    nombre = " ".join(datos.nombre.split())
    if len(nombre) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escribí tu nombre (al menos 2 letras).",
        )
    usuario.nombre = nombre
    db.commit()
    db.refresh(usuario)
    return _usuario_me(db, usuario)

# ============================================================
# Recuperación y cambio de contraseña
# ============================================================

@router.post("/reenviar-verificacion")
@limiter.limit("3/hour")
def reenviar_verificacion(
    request: Request, usuario: UsuarioActual, db: DB
) -> dict:
    """Manda de nuevo el email de verificación, para quien no lo recibió.

    3 por hora: alcanza de sobra para el que lo mandó a spam, y no sirve como
    forma de usarnos para bombardear una casilla ajena.
    """
    from app.services import registro as svc_registro

    token = svc_registro.reenviar(db, usuario)
    if token is None:
        return {"ok": True, "detalle": "Tu email ya está verificado."}

    # encolar() y no .delay(): si no hay worker escuchando la cola, el mensaje
    # se quedaría ahí para siempre y esta función igual contestaría «te lo
    # mandamos». Justamente acá, donde la persona está mirando la pantalla
    # esperando el mail, esa mentira es lo peor que puede pasar.
    from app.core.cola import Resultado, encolar
    from app.tasks.emails import enviar_verificacion_email

    resultado = encolar(enviar_verificacion_email, usuario.id, token)
    if resultado is Resultado.FALLO:
        log.error("No se pudo mandar el reenvío de verificación (usuario %s)", usuario.id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No pudimos mandar el email ahora. Probá en un rato.",
        )

    return {
        "ok": True,
        "detalle": f"Te lo mandamos a {usuario.email}. Revisá también el spam.",
    }


@router.post("/olvide-password")
@limiter.limit("3/minute")
def olvide_password(request: Request, datos: OlvidePasswordRequest, db: DB) -> dict:
    """Pide el email y manda un link de restablecimiento (si la cuenta existe).

    SIEMPRE responde lo mismo: no revelamos si un email está registrado o no.
    El token viaja por email; acá solo guardamos su hash, con 60 min de vida.
    """
    # Una cuenta invitada sin activar no recibe link de restablecimiento:
    # se activa con su invitación (que el admin puede reenviar). La respuesta
    # es la misma de siempre, así que no revela nada.
    usuario = db.scalars(
        select(Usuario).where(
            func.lower(Usuario.email) == datos.email.lower(),
            Usuario.activo.is_(True),
            Usuario.activacion_pendiente.is_(False),
        )
    ).one_or_none()
    if usuario is not None:
        token = secrets.token_urlsafe(32)
        usuario.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        usuario.reset_token_expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            minutes=60
        )
        db.commit()
        # encolar(): sin worker, el link de restablecimiento se quedaba en la
        # cola y la persona esperaba un mail que no iba a llegar. Como acá la
        # respuesta es siempre la misma (no revelamos si el email existe), este
        # es el único lugar donde el problema se puede ver.
        from app.core.cola import Resultado, encolar
        from app.tasks.emails import enviar_reset_password

        if encolar(enviar_reset_password, usuario.id, token) is Resultado.FALLO:
            log.error(
                "No se pudo mandar el email de restablecimiento (usuario %s)",
                usuario.id,
            )
    return {"detalle": "Si el email está registrado, te enviamos un link para restablecer la contraseña."}


@router.post("/restablecer-password")
@limiter.limit("5/minute")
def restablecer_password(
    request: Request, datos: RestablecerPasswordRequest, db: DB
) -> dict:
    """Cambia la clave usando el token del email. Un solo uso, expira en 60 min."""
    token_hash = hashlib.sha256(datos.token.encode()).hexdigest()
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.reset_token_hash == token_hash,
            Usuario.reset_token_expira > dt.datetime.now(dt.timezone.utc),
            Usuario.activo.is_(True),
            Usuario.activacion_pendiente.is_(False),
        )
    )
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El link no es válido o ya venció. Pedí uno nuevo desde el login.",
        )
    usuario.hash_clave = hash_clave(datos.clave_nueva)
    usuario.reset_token_hash = None
    usuario.reset_token_expira = None
    # Corta TODAS las sesiones abiertas. Este flujo es justo el que usa alguien
    # que sospecha que le entraron a la cuenta: si no revocara, el atacante
    # seguiría adentro con su refresh token por hasta 7 días.
    sesiones.revocar_todas(db, usuario, "Restableció la contraseña", "usuario")
    db.commit()
    return {"detalle": "Contraseña actualizada. Ya podés entrar con la nueva."}


@router.post("/cambiar-password", response_model=SesionRenovada)
@limiter.limit("10/minute")
def cambiar_password(
    request: Request, datos: CambiarPasswordRequest, usuario: UsuarioActual, db: DB
) -> SesionRenovada:
    """Cambio de clave estando logueado: pide la actual y setea la nueva.

    Corta todas las sesiones (token_version + 1) y devuelve un par nuevo para
    este dispositivo. Antes no devolvía nada: el panel decía «Contraseña
    actualizada» y al siguiente clic echaba a la persona al login.
    """
    if not verificar_clave(datos.clave_actual, usuario.hash_clave):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta",
        )
    if datos.clave_nueva == datos.clave_actual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña nueva tiene que ser distinta de la actual",
        )
    usuario.hash_clave = hash_clave(datos.clave_nueva)
    usuario.reset_token_hash = None
    usuario.reset_token_expira = None
    sesiones.revocar_todas(db, usuario, "Cambió la contraseña", "usuario")
    return _sesion_nueva(
        db, request, usuario,
        "Contraseña actualizada. Se cerró la sesión en tus otros dispositivos.",
    )


@router.post("/cerrar-otras-sesiones", response_model=SesionRenovada)
@limiter.limit("5/minute")
def cerrar_otras_sesiones(
    request: Request, datos: CerrarSesionesRequest, usuario: UsuarioActual, db: DB
) -> SesionRenovada:
    """Saca de la cuenta a cualquier otro dispositivo, sin cambiar la clave.

    Pide la contraseña: con solo un token robado, alguien podría usar esto
    para echar al dueño de verdad y quedarse con la única sesión válida.

    Cierra todas (también los tokens viejos sin sesión, vía token_version)
    y abre una nueva para este dispositivo.
    """
    if not verificar_clave(datos.clave_actual, usuario.hash_clave):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña no es correcta",
        )
    sesiones.revocar_todas(db, usuario, "Cerró las otras sesiones", "usuario")
    return _sesion_nueva(
        db, request, usuario, "Listo: se cerró la sesión en todos tus otros dispositivos."
    )


@router.post("/logout")
@limiter.limit("30/minute")
def logout(request: Request, usuario: UsuarioActual, db: DB) -> dict:
    """Cierra la sesión de este dispositivo en el servidor.

    Antes «Salir» solo borraba los tokens del navegador: el refresh seguía
    sirviendo 7 días para quien lo tuviera copiado.
    """
    sesiones.cerrar_actual(db, usuario, getattr(request.state, "token_payload", {}) or {})
    return {"ok": True}


# ============================================================
# Activación de cuentas invitadas (alta desde el super-admin)
# ============================================================

class _TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class _ActivarIn(_TokenIn):
    clave: str = Field(min_length=8, max_length=100)


@router.post("/invitacion")
@limiter.limit("10/minute")
def ver_invitacion(request: Request, datos: _TokenIn, db: DB) -> dict:
    """A quién invitaron (nombre de pila, negocio y email enmascarado).

    POST y no GET: el token va en el cuerpo y no queda en los logs de acceso.
    Cualquier link que no sirve (no existe, venció, ya se usó, se revocó)
    recibe la MISMA respuesta: no se puede usar para averiguar nada.
    """
    from app.services import invitaciones

    return invitaciones.ver(db, datos.token)


@router.post("/activar")
@limiter.limit("5/minute")
def activar_cuenta(request: Request, datos: _ActivarIn, db: DB) -> dict:
    """La persona invitada elige su contraseña. El link sirve una sola vez."""
    from app.services import invitaciones

    return invitaciones.activar(db, datos.token, datos.clave)
