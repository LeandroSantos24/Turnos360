"""El reloj del sistema. Una sola definición, a propósito.

LA CONVENCIÓN
-------------
El motor de agenda guarda "hora de pared etiquetada UTC": un turno de las
10:00 en Mendoza se guarda como `10:00+00:00`, sin convertir. Es una decisión
deliberada y está bien para un producto que vende en una sola zona horaria —
evita que un cambio de huso mueva turnos ya agendados.

El precio de esa decisión es que `datetime.now(timezone.utc)` NO SIRVE para
compararse contra esas fechas. En un servidor con TZ=UTC, `now(UTC)` va tres
horas adelantado respecto de lo que dice la agenda: el sistema se cree que
son las 13:00 cuando en Mendoza son las 10:00.

POR QUÉ ESTA FUNCIÓN VIVE ACÁ Y NO EN UN SERVICIO
--------------------------------------------------
Estaba definida adentro de `services/publico.py`, con guión bajo, o sea
privada de ese módulo. Las tareas de fondo no la podían importar sin que
oliera mal, y terminaron usando `datetime.now(timezone.utc)` — con el
corrimiento de tres horas puesto. Los recordatorios de "2 horas antes" salían
a las cuatro de la mañana.

Una convención que hay que recordar aplicar en cada lugar nuevo se olvida. Por
eso hay una sola función, pública, en un módulo que se llama como lo que hace.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from app.core.config import settings


def ahora_de_pared() -> dt.datetime:
    """El "ahora" en la convención del motor: hora local, etiquetada UTC.

    Es la ÚNICA forma correcta de comparar contra `turno.fecha_inicio`,
    `turno.fecha_fin` o cualquier fecha que haya pasado por el motor de
    agenda. Si estás por escribir `datetime.now(timezone.utc)` y del otro lado
    de la comparación hay una fecha de turno, esto es lo que va.
    """
    local = dt.datetime.now(ZoneInfo(settings.zona_horaria))
    return local.replace(tzinfo=dt.timezone.utc)


def hoy_de_pared() -> dt.date:
    """La fecha de hoy en la zona del negocio.

    `date.today()` usa la zona del SERVIDOR, que en producción es UTC. Entre
    las 21:00 y la medianoche de Argentina, `date.today()` ya devuelve el día
    siguiente: un listado "de hoy" mostraría el de mañana.
    """
    return dt.datetime.now(ZoneInfo(settings.zona_horaria)).date()
