"""La marca de Turnos360: el logo que se puede cambiar sin un deploy.

POR QUÉ EXISTE
──────────────
Lo pidió Leandro: «dejame cargarlo con una URL desde mi panel admin, así en
Navidad le pongo un gorrito y en Pascua huevos». Hoy eso es reemplazar
`frontend/public/marca/logo-turnos360.webp` y desplegar, que para un chiste
estacional de una semana no lo hace nadie.

EL ARCHIVO DEL REPO NO SE VA — ES EL RESPALDO
─────────────────────────────────────────────
La URL PISA al archivo local, no lo reemplaza. Los dos motivos:

  1. Si la URL falla —Cloudinary caído, la imagen borrada, un typo—, la
     landing y el panel se quedarían sin logo. El primer render usa el archivo
     local, así que eso no puede pasar.
  2. Y de paso: NO es más liviano, aunque lo parezca. El .webp local sale del
     mismo origen que la página, ya está en la caché del navegador y pesa
     16 KB. Una URL externa suma un DNS, un TLS y una dependencia de un
     tercero en el primer pintado de la página de ventas. Lo que se gana acá
     no es peso: es poder cambiarlo sin desplegar, que era el pedido.

CÓMO SE USA DEL LADO DEL NAVEGADOR
──────────────────────────────────
El frontend pinta el archivo local de entrada y consulta este endpoint; si hay
override, cambia el `src`. Si la imagen del override no carga, el `onError`
vuelve al local. Nunca hay un hueco donde va el logo.
"""

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.models import AjusteGlobal

log = logging.getLogger("turnos360.marca")

# La clave del ajuste. Una constante y no un string suelto: se escribe en el
# servicio, en el router y en los tests, y un typo devolvería "sin override"
# en silencio — que se ve exactamente igual que "todavía no lo configuró".
CLAVE_LOGO = "logo_url"


def logo_url(db: Session) -> str | None:
    """La URL del logo cargada por el super-admin, o None si no hay.

    Nunca levanta: esto lo consulta la landing, que es la página de ventas.
    Un error de base no puede dejarla sin renderizar por un logo.
    """
    try:
        fila = db.get(AjusteGlobal, CLAVE_LOGO)
    except Exception:
        log.exception("No se pudo leer el logo de la marca")
        return None
    valor = (fila.valor or "").strip() if fila else ""
    return valor or None


def guardar_logo(db: Session, url: str | None, quien: str | None) -> str | None:
    """Guarda (o borra, con None/vacío) la URL del logo. Devuelve lo que quedó.

    Vacío BORRA el override y vuelve al archivo del repo. Es la forma de
    deshacer el gorrito de Navidad el 2 de enero, y tiene que ser tan fácil
    como ponerlo.
    """
    limpia = (url or "").strip()
    fila = db.get(AjusteGlobal, CLAVE_LOGO)
    if fila is None:
        fila = AjusteGlobal(clave=CLAVE_LOGO)
        db.add(fila)
    fila.valor = limpia
    fila.actualizado_en = dt.datetime.now(dt.timezone.utc)
    fila.actualizado_por = quien
    db.commit()
    log.info("Logo de la marca actualizado", extra={"por": quien, "vacio": not limpia})
    return limpia or None
