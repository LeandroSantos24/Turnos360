"""LogAuditoria: la tabla nace en E1 (diseñá para todo); el middleware llega en E9.
En salud registra también cada LECTURA de ficha (Regla 5)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"
    __table_args__ = (
        Index("ix_log_empresa_fecha", "empresa_id", "fecha"),
        Index("ix_log_tabla_registro", "tabla", "registro_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # nullable: acciones del super_admin no pertenecen a una empresa
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(30))  # crear, modificar, eliminar, LEER
    tabla: Mapped[str | None] = mapped_column(String(60))
    registro_id: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())