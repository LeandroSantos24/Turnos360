"""Schemas del equipo del negocio."""

from pydantic import BaseModel, ConfigDict

from app.models.enums import RolUsuario


class MiembroEquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    rol: RolUsuario
    activo: bool
    # False cuando el email no sirve para recibir un link (está vacío, o es
    # un "barbero1" de los que se cargan cuando el empleado no quiere dar el
    # suyo). La UI lo usa para avisar quién NO puede recuperar su contraseña
    # por sus propios medios y depende del dueño.
    email_recuperable: bool
    # El recurso (silla) que opera, si es un profesional vinculado.
    recurso: str | None = None


class LinkRestablecerOut(BaseModel):
    """El link de un solo uso que el dueño le pasa al empleado."""

    url: str
    usuario: str
    vence_en_minutos: int
