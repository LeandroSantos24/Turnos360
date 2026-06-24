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