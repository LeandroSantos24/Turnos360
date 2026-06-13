"""Enums del dominio (núcleo arriba, módulos opcionales abajo)."""

import enum


class TipoRecurso(str, enum.Enum):
    PERSONA = "persona"
    BOX = "box"
    EQUIPO = "equipo"


class TipoTurno(str, enum.Enum):
    """D-04: las 5 formas, modeladas desde el día uno."""

    SIMPLE = "simple"
    RECURRENTE = "recurrente"
    SERIE = "serie"
    ORDEN_LLEGADA = "orden_llegada"
    ORDEN_TRABAJO = "orden_trabajo"


class EstadoTurno(str, enum.Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    EN_CURSO = "en_curso"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"
    AUSENTE = "ausente"


class RolUsuario(str, enum.Enum):
    DUENO = "dueno"
    ADMIN = "admin"
    RECEPCION = "recepcion"
    PROFESIONAL = "profesional"


class TipoExcepcion(str, enum.Enum):
    FERIADO = "feriado"
    LICENCIA = "licencia"
    VACACIONES = "vacaciones"
    BLOQUEO = "bloqueo"


class TipoMovimiento(str, enum.Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"


class EstadoCaja(str, enum.Enum):
    ABIERTA = "abierta"
    CERRADA = "cerrada"


class CanalMensaje(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class DireccionMensaje(str, enum.Enum):
    SALIENTE = "saliente"
    ENTRANTE = "entrante"


class EstadoMensaje(str, enum.Enum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    ENTREGADO = "entregado"
    LEIDO = "leido"
    FALLIDO = "fallido"


class ModalidadComision(str, enum.Enum):
    PORCENTAJE = "porcentaje"
    CANON_CONSULTA = "canon_consulta"
    ALQUILER = "alquiler"


# ===== Enums de módulos opcionales (se usan al activar cada pack) =====


class EstadoGiftCard(str, enum.Enum):
    ACTIVA = "activa"
    CANJEADA = "canjeada"
    VENCIDA = "vencida"


class EstadoMembresia(str, enum.Enum):
    ACTIVA = "activa"
    SUSPENDIDA = "suspendida"
    VENCIDA = "vencida"
    PENDIENTE_PAGO = "pendiente_pago"


class TipoPromocion(str, enum.Enum):
    CUPON = "cupon"
    DESCUENTO = "descuento"
    COMBO = "combo"
    PAQUETE = "paquete"
    CUMPLEANOS = "cumpleanos"
    FECHA_ESPECIAL = "fecha_especial"


class TipoItemOrden(str, enum.Enum):
    REPUESTO = "repuesto"
    MATERIAL = "material"
    MANO_OBRA = "mano_obra"


class EstadoOrdenTrabajo(str, enum.Enum):
    PRESUPUESTADO = "presupuestado"
    APROBADO = "aprobado"
    EN_PROCESO = "en_proceso"
    PAUSADO = "pausado"
    TERMINADO = "terminado"
    ENTREGADO = "entregado"


class EstadoSuscripcion(str, enum.Enum):
    ACTIVA = "activa"
    VENCIDA = "vencida"
    SUSPENDIDA = "suspendida"
    CANCELADA = "cancelada"