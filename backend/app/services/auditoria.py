"""Registro de auditoría.

La tabla `log_auditoria` existía desde la primera migración —con sus índices y
todo— y NO SE ESCRIBÍA UNA SOLA FILA en todo el backend. El comentario del
modelo prometía que en salud se registraba cada lectura de ficha; era una
intención, no código.

Este módulo es el primer uso real. Arranca con lo más sensible que hay:
que un dueño le genere a otra persona un link para cambiarle la contraseña.
Sin registro, esa acción sería invisible para siempre.

Regla de oro: auditar NUNCA puede voltear la operación que se está
auditando. Si falla el registro, se loguea y se sigue.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import LogAuditoria

log = logging.getLogger(__name__)


def registrar(
    db: Session,
    *,
    accion: str,
    empresa_id: int | None = None,
    usuario_id: int | None = None,
    tabla: str | None = None,
    registro_id: int | None = None,
    detalle: dict | None = None,
    ip: str | None = None,
) -> None:
    """Deja constancia de una acción sensible.

    NO hace commit: se suma a la transacción de quien llama, para que el
    registro y la acción entren o no entren juntos. Un log que sobrevive a
    una operación que se revirtió miente.
    """
    try:
        db.add(
            LogAuditoria(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                accion=accion[:30],
                tabla=tabla[:60] if tabla else None,
                registro_id=registro_id,
                detalle=detalle,
                ip=ip[:45] if ip else None,
            )
        )
    except Exception:
        # Auditar no puede voltear la operación auditada.
        log.exception("No se pudo registrar en la auditoría (accion=%s)", accion)
