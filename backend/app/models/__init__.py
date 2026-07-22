"""Todos los modelos del núcleo (E1). Importar este paquete registra el metadata
completo para Alembic."""

from app.db.base import Base
from app.models.agenda import (
    Especialidad,
    ExcepcionAgenda,
    HorarioRecurso,
    Recurso,
    Servicio,
    recurso_especialidad,
    servicio_recurso,
)
from app.models.auditoria import LogAuditoria
from app.models.cliente import Adjunto, Calificacion, Cliente, HistorialCliente, ListaEspera
from app.models.finanzas import (
    Caja,
    CategoriaFinanciera,
    ComisionProfesional,
    DeudaCliente,
    MetodoPago,
    MovimientoFinanciero,
    Pago,
)
from app.models.mensajeria import Mensaje, PlantillaMensaje
from app.models.organizacion import Empresa, Rubro, Sucursal, SuperAdmin, Usuario
from app.models.turno import Turno
from app.models.modulos.fidelizacion import *  # noqa: F401,F403  -> E11
from app.models.modulos.giftcards import GiftCard  # noqa: F401  -> E11
from app.models.modulos.salud import *  # noqa: F401,F403  -> E13
from app.models.items import ItemTurno
from app.models.cupon import CuponDescuento

from app.models.saas import PagoSuscripcion  # cobranza del SaaS (super-admin)

__all__ = [
    "CuponDescuento",
    "Base",
    "Rubro", "Empresa", "Sucursal", "Usuario", "SuperAdmin",
    "Especialidad", "Recurso", "HorarioRecurso", "ExcepcionAgenda", "Servicio",
    "recurso_especialidad", "servicio_recurso",
    "Cliente", "HistorialCliente", "Calificacion", "Adjunto", "ListaEspera",
    "Turno",
    "Caja", "CategoriaFinanciera", "MetodoPago", "MovimientoFinanciero",
    "Pago", "DeudaCliente", "ComisionProfesional",
    "PlantillaMensaje", "Mensaje",
    "LogAuditoria",
    "PagoSuscripcion",
    "Turno",
    "ItemTurno",
]

# ===== MÓDULOS PREPARADOS =====
# Para activar un módulo en su etapa, descomentar SU línea
# y correr: make db-revision m="EXX nombre" && make db-upgrade

# from app.models.modulos.taller import *  # noqa: F401,F403  -> E14
# from app.models.modulos.saas import *  # noqa: F401,F403  -> E16