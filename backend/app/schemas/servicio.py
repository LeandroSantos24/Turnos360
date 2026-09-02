"""Schemas de Servicio: lo que cada negocio ofrece y reserva (E2)."""

from pydantic import BaseModel, Field


class SucursalDeServicio(BaseModel):
    """En qué local se ofrece un servicio, y a cuánto.

    `precio` en None = "el del servicio". Es lo que permite subir el precio
    general una sola vez sin tener que recorrer local por local.
    """

    sucursal_id: int
    precio: float | None = Field(default=None, ge=0)


class ServicioBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    duracion_min: int = Field(gt=0, le=600, description="Minutos de atención activa")
    buffer_min: int = Field(default=0, ge=0, le=240, description="Tiempo muerto posterior")
    paso_turno_min: int = Field(default=15, gt=0, le=240, description="Cada cuánto se ofrecen turnos")
    grupo_agenda: str | None = Field(default=None, max_length=40, description="Carril de agenda: servicios del mismo grupo se bloquean entre sí")
    precio: float | None = Field(default=None, ge=0)
    agendable: bool = Field(default=True, description="Si ocupa turno (corte) o es solo para vender (perfilado, productos)")


class ServicioCrear(ServicioBase):
    recurso_ids: list[int] = Field(default_factory=list, description="Recursos que prestan este servicio")
    # None = "en todos los locales abiertos", que es lo que pasa siempre en un
    # negocio de un solo local: el formulario ni pregunta.
    sucursales: list[SucursalDeServicio] | None = Field(
        default=None, description="Locales donde se ofrece. None = todos."
    )


class ServicioEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    duracion_min: int | None = Field(default=None, gt=0, le=600)
    buffer_min: int | None = Field(default=None, ge=0, le=240)
    paso_turno_min: int | None = Field(default=None, gt=0, le=240)
    grupo_agenda: str | None = Field(default=None, max_length=40)
    precio: float | None = Field(default=None, ge=0)
    agendable: bool | None = None
    activo: bool | None = None
    recurso_ids: list[int] | None = Field(default=None, description="Si viene, reemplaza el set de recursos")
    sucursales: list[SucursalDeServicio] | None = Field(
        default=None, description="Si viene, reemplaza los locales donde se ofrece"
    )


class ServicioOut(ServicioBase):
    id: int
    empresa_id: int
    activo: bool
    recurso_ids: list[int] = Field(default_factory=list)
    # Siempre trae al menos uno: un servicio ofrecido en ningún lado no
    # existiría para nadie. La pantalla lo muestra solo con varios locales.
    sucursales: list[SucursalDeServicio] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @classmethod
    def desde_modelo(cls, servicio, sucursales=None) -> "ServicioOut":
        """Arma el Out incluyendo recursos y locales."""
        base = cls.model_validate(servicio)
        base.recurso_ids = [r.id for r in servicio.recursos]
        base.sucursales = [
            SucursalDeServicio(sucursal_id=f.sucursal_id, precio=f.precio)
            for f in (sucursales or [])
        ]
        return base


class ServiciosPagina(BaseModel):
    total: int
    items: list[ServicioOut]