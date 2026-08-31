"""Sucursales: lo que entra y sale por /sucursales (E16, paso 2)."""

from pydantic import BaseModel, Field, field_validator


class SucursalOut(BaseModel):
    id: int
    nombre: str
    direccion: str | None = None
    telefono: str | None = None
    activa: bool
    # Cuánta gente trabaja acá. Es lo que el dueño necesita ver antes de
    # desactivar un local: si tiene profesionales, hay que moverlos primero.
    profesionales: int = 0
    # El local original de la empresa, el que se creó con el alta. No se puede
    # desactivar mientras sea el único activo.
    es_principal: bool = False

    model_config = {"from_attributes": True}


def _nombre_limpio(cls, v: str | None) -> str | None:
    """Recorta el nombre y rechaza el que queda vacío.

    `min_length=1` no alcanza: un nombre de puros espacios lo pasa, y después
    el .strip() lo dejaba en None contra una columna NOT NULL. Eso es un 500
    donde correspondía un 422 con el campo señalado.
    """
    if v is None:
        return None
    v = v.strip()
    if not v:
        raise ValueError("El local necesita un nombre.")
    return v


def _texto_opcional(cls, v: str | None) -> str | None:
    """Dirección y teléfono SÍ se pueden vaciar: vacío significa "no la sé"."""
    if v is None:
        return None
    return v.strip() or None


class SucursalCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)

    _v_nombre = field_validator("nombre")(classmethod(_nombre_limpio))
    _v_texto = field_validator("direccion", "telefono")(classmethod(_texto_opcional))


class SucursalEditar(BaseModel):
    """Todo opcional: el form manda solo lo que cambió."""

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    activa: bool | None = None

    _v_nombre = field_validator("nombre")(classmethod(_nombre_limpio))
    _v_texto = field_validator("direccion", "telefono")(classmethod(_texto_opcional))


class SucursalesOut(BaseModel):
    """La lista más el cupo, que es lo que la pantalla necesita para saber si
    muestra el botón de "Nuevo local" o el aviso de que hay que cambiar de plan."""

    sucursales: list[SucursalOut]
    tope: int
    usadas: int
    plan_etiqueta: str
