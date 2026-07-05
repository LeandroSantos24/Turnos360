"""Schema de la configuración de la empresa actual (preset del rubro).

Lo consume el frontend al iniciar sesión para saber:
- qué módulos mostrar (preset["modulos"], ej. ficha_clinica),
- cómo nombrar las cosas (preset["terminologia"], ej. cliente -> paciente).
"""

from pydantic import BaseModel


class EmpresaActualOut(BaseModel):
    id: int
    nombre: str
    slug: str
    rubro_codigo: str
    rubro_nombre: str
    # El preset del rubro (terminologia, modulos, campos_cliente...), ya con
    # los overrides de la empresa aplicados si los hubiera.
    preset: dict


class LandingConfig(BaseModel):
    """Contenido editable de la landing pública del negocio (pantalla "Mi página").

    Mismo shape para leer (GET) y guardar (PUT): el form tiene todos los campos
    y los manda todos. Todo opcional -> el dueño completa de a poco.

    - horarios_atencion: SOLO para mostrar (no calcula huecos). Estructura libre;
      la define el frontend (ej. {"lun": [["09:00","13:00"],["17:00","21:00"]], ...}).
    - redes: dict libre. Claves conocidas: instagram, facebook, tiktok, linkedin,
      sitio_web. Sumar una red nueva = agregar clave, sin migración.
    - color_marca: hex del acento, ej. "#00d4aa".
    """

    descripcion: str | None = None
    direccion: str | None = None
    telefono_publico: str | None = None
    email_publico: str | None = None
    logo_url: str | None = None
    color_marca: str | None = None
    horarios_atencion: dict | None = None
    redes: dict = {}
    # Galería de la landing: lista de URLs de fotos (máx. razonable: 12).
    galeria: list[str] = []