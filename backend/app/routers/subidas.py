"""Las imágenes que sube el negocio: fotos del equipo, logo, portada.

POR QUÉ ESTO EXISTE
───────────────────
Hasta acá TODAS las imágenes eran una URL para pegar a mano: la foto de cada
profesional, el logo, la portada. Leandro lo encontró probando el alta —«no me
deja cargar la foto de los peluqueros»— y tenía razón: no es que estuviera
roto, es que no había forma de subir un archivo. Un dueño de barbería no tiene
sus fotos publicadas en ningún lado con una URL a mano; las tiene en el celular.

RE-CODIFICAR ES LA DEFENSA, NO VALIDAR
──────────────────────────────────────
Acá entra un archivo mandado por alguien de afuera y después se sirve por HTTP.
Mirar la extensión no sirve (se cambia) y el `content-type` tampoco (lo elige
quien sube). Ni siquiera alcanza con leer los primeros bytes: existen archivos
POLÍGLOTOS, válidos como imagen Y como otra cosa —un HTML con JavaScript, un
PHP— que pasan cualquier chequeo de cabecera y se ejecutan si el navegador los
interpreta.

Lo que sí resuelve el problema es no guardar nunca el archivo que llegó: se
abre con Pillow, se verifica que sea una imagen de verdad, y se ESCRIBE UNA
NUEVA a partir de los píxeles. Lo que no era píxel no sobrevive.

De regalo, re-codificar tira los metadatos EXIF, que en una foto de celular
traen la ubicación GPS de dónde se sacó. Publicar la foto del equipo no puede
significar publicar la dirección de la casa de un empleado.

EL NOMBRE LO PONEMOS NOSOTROS
─────────────────────────────
El nombre que manda el cliente no se usa para nada. `../../etc/passwd` es un
nombre de archivo válido, y bastaría con concatenarlo a una ruta para escribir
fuera de la carpeta. Se genera un uuid y listo.
"""

import logging
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.core.config import settings
from fastapi import Depends

log = logging.getLogger("turnos360.subidas")

router = APIRouter(prefix="/subidas", tags=["subidas"])

# Los formatos que aceptamos ENTRAR. La salida siempre es webp.
FORMATOS = {"JPEG", "PNG", "WEBP", "GIF", "BMP"}

# A cuánto se reduce cada imagen según PARA QUÉ es.
#
# El tamaño lo decide el servidor y no el navegador: si viniera del cliente,
# bastaría con mandar otro número para guardar imágenes de 8000 px y llenar el
# disco. Y son distintos porque los usos son distintos — un avatar se muestra
# en 44 px y una foto de la galería se abre a pantalla completa.
#
# El RECORTE lo hace el navegador antes de subir (el dueño elige el encuadre
# con el dedo), así que acá solo llega lo que él ya decidió que se vea.
LADOS = {
    "avatar": 512,     # la foto de un profesional
    "logo": 512,       # el logo del negocio
    "portada": 1600,   # la foto grande de arriba de la vidriera
    "galeria": 1600,   # las fotos del local: se ven grandes, van sin recortar
}


def _carpeta_de(empresa_id: int) -> Path:
    """Cada negocio en su carpeta: hace obvio a quién pertenece cada archivo
    y deja borrar todo lo de una empresa de una sola vez si se da de baja."""
    carpeta = Path(settings.uploads_dir) / str(empresa_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


@router.post("/imagen", dependencies=[Depends(gate_dueno)])
async def subir_imagen(
    empresa_id: EmpresaActual,
    db: DB,
    archivo: UploadFile = File(...),
    proposito: str = Form(default="galeria"),
) -> dict:
    """Recibe una imagen, la re-escribe como webp y devuelve su URL pública.

    `proposito` dice para qué es (avatar, logo, portada, galeria) y con eso el
    servidor elige a cuánto reducirla. Es el servidor el que decide, no el
    navegador: un tamaño que viniera del cliente sería un número que cualquiera
    puede cambiar para guardar imágenes gigantes y llenar el disco.
    """
    if proposito not in LADOS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No sé para qué es «{proposito}».",
        )
    tope = settings.upload_max_mb * 1024 * 1024

    # Se lee con tope: sin esto, un archivo enorme se carga entero en memoria
    # antes de que nadie pueda rechazarlo, y con dos o tres alcanza para
    # voltear el proceso.
    crudo = await archivo.read(tope + 1)
    if len(crudo) > tope:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"La imagen no puede pesar más de {settings.upload_max_mb} MB. "
            "Probá con una más chica o sacale una captura.",
        )
    if not crudo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")

    try:
        img = Image.open(BytesIO(crudo))
        # `verify()` recorre la estructura y detecta un archivo corrupto o que
        # solo pretende ser una imagen. Deja el objeto inutilizable, así que
        # después hay que volver a abrirlo — es el uso previsto de Pillow.
        img.verify()
        if img.format not in FORMATOS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Ese formato no lo podemos usar. Mandá un JPG, PNG o WEBP.",
            )
        img = Image.open(BytesIO(crudo))
        img.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese archivo no es una imagen que podamos leer.",
        ) from None

    # Un PNG con transparencia sobre fondo blanco: el webp la soporta, pero el
    # modo P o LA rompe al guardar. RGB es el denominador común.
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    # Achicar según el uso. Una foto de celular son 12 megapíxeles; un avatar
    # se muestra en 44 y hasta la galería se ve bien con 1600.
    lado = LADOS[proposito]
    if max(img.size) > lado:
        img.thumbnail((lado, lado), Image.LANCZOS)

    nombre = f"{uuid.uuid4().hex}.webp"
    destino = _carpeta_de(empresa_id) / nombre
    # La imagen NUEVA, hecha de los píxeles de la que llegó. El archivo
    # original no se guarda en ningún momento.
    img.save(destino, format="WEBP", quality=82, method=4)

    url = f"/uploads/{empresa_id}/{nombre}"
    log.info(
        "imagen subida",
        extra={
            "empresa_id": empresa_id,
            "archivo": nombre,
            "bytes": len(crudo),
            "proposito": proposito,
        },
    )
    return {"url": url}
