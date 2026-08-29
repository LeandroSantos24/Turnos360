"""Schemas del equipo del negocio."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


# Roles que el DUEÑO puede asignar desde su panel.
#
# No incluye "dueno" ni "admin" a propósito: son los dos roles que pueden tocar
# la facturación y la configuración del negocio. Que el dueño se los pueda dar
# a alguien desde una pantalla, sin ningún paso extra, convierte cualquier
# sesión olvidada en un mostrador en una toma de control del negocio. Si hace
# falta un segundo dueño, lo carga el super-admin.
ROLES_ASIGNABLES = (RolUsuario.RECEPCION, RolUsuario.PROFESIONAL)


class MiembroCrear(BaseModel):
    """Alta de un empleado, hecha por el dueño desde su panel."""

    nombre: str = Field(min_length=2, max_length=120)
    # EmailStr y normalizado, igual que en el alta del super-admin: un email
    # sin arroba deja a esa persona sin poder recuperar su clave nunca.
    email: EmailStr
    clave: str = Field(min_length=8, max_length=100)
    rol: RolUsuario = RolUsuario.PROFESIONAL

    @field_validator("email", mode="after")
    @classmethod
    def _normalizar_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("rol", mode="after")
    @classmethod
    def _rol_permitido(cls, v: RolUsuario) -> RolUsuario:
        if v not in ROLES_ASIGNABLES:
            raise ValueError(
                "Desde tu panel podés cargar recepción o profesional. Para "
                "sumar otro dueño, escribinos."
            )
        return v


class MiembroEditar(BaseModel):
    """Editar un empleado. Solo lo que venga: el resto queda como está."""

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    rol: RolUsuario | None = None
    activo: bool | None = None

    @field_validator("email", mode="after")
    @classmethod
    def _normalizar_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else v

    @field_validator("rol", mode="after")
    @classmethod
    def _rol_permitido(cls, v: RolUsuario | None) -> RolUsuario | None:
        if v is not None and v not in ROLES_ASIGNABLES:
            raise ValueError(
                "Desde tu panel podés asignar recepción o profesional."
            )
        return v
