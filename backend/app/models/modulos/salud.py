"""Pack salud / nutrición (E13).

Tres tablas, todas colgando del cliente (que en este rubro se llama "paciente"):

- FichaClinica:    la anamnesis de primera consulta (1 por paciente). Datos
                   cualitativos + cobertura (obra social). Lo tabular de la
                   entrevista (horario de comidas, frecuencia de consumo) va en
                   JSONB porque no se grafica, solo se muestra en la ficha.
- EntradaClinica:  cada control/consulta de seguimiento (N por paciente). Es la
                   evolución: cómo se sintió, apetito, descanso, prescripción.
- MedicionAntropometrica: las mediciones numéricas por fecha (N por paciente).
                   Lo que SÍ se grafica en el tiempo (peso, IMC, pliegues...).
                   El detalle exhaustivo del informe ISAK va en JSONB; el PDF
                   original se guarda como Adjunto (que ya existe en el núcleo).

Regla 1: todo hereda TenantMixin → empresa_id NOT NULL + índice.
Regla 4: esto es un módulo que el pack activa; nada de `if rubro == "nutri"`.
"""

import datetime as dt
from datetime import datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.organizacion import TenantMixin


class FichaClinica(TenantMixin, Base):
    """Anamnesis de primera consulta. Una por paciente (1:1 con cliente)."""

    __tablename__ = "ficha_clinica"
    __table_args__ = (
        UniqueConstraint("empresa_id", "cliente_id", name="uq_ficha_empresa_cliente"),
        Index("ix_ficha_empresa_cliente", "empresa_id", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))

    # --- Motivo y contexto ---
    motivo_consulta: Mapped[str | None] = mapped_column(Text)
    objetivo: Mapped[str | None] = mapped_column(Text)
    ocupacion: Mapped[str | None] = mapped_column(String(200))
    horario_trabajo: Mapped[str | None] = mapped_column(String(200))
    fum: Mapped[dt.date | None] = mapped_column(Date)  # fecha última menstruación

    # --- Alimentación (lo tabular de la entrevista, en JSONB) ---
    # horario_comidas: {desayuno, colacion1, almuerzo, merienda, colacion2, cena}
    horario_comidas: Mapped[dict] = mapped_column(JSONB, default=dict)
    recordatorio_24h: Mapped[dict] = mapped_column(JSONB, default=dict)
    # frecuencia_consumo: {lacteos, huevo, carnes, hc, legumbres, verduras,
    #                      frutas, pescado, procesados, azucar, sal}
    frecuencia_consumo: Mapped[dict] = mapped_column(JSONB, default=dict)

    # --- Salud general ---
    actividad_fisica: Mapped[str | None] = mapped_column(Text)
    enfermedades: Mapped[str | None] = mapped_column(Text)
    operaciones: Mapped[str | None] = mapped_column(Text)
    medicacion: Mapped[str | None] = mapped_column(Text)
    antecedentes_familiares: Mapped[str | None] = mapped_column(Text)
    consume_alcohol_drogas: Mapped[str | None] = mapped_column(String(200))
    fuma: Mapped[str | None] = mapped_column(String(120))
    sintomas_recurrentes: Mapped[str | None] = mapped_column(Text)
    evacuacion: Mapped[str | None] = mapped_column(String(200))
    sueno: Mapped[str | None] = mapped_column(String(200))

    # --- Preferencias alimentarias ---
    alimentos_no_consume: Mapped[str | None] = mapped_column(Text)
    alimentos_no_tolera: Mapped[str | None] = mapped_column(Text)
    alimentos_gustan: Mapped[str | None] = mapped_column(Text)
    nutri_anterior: Mapped[str | None] = mapped_column(Text)

    # --- Cobertura (campos sí; lógica de convenios NO, eso es de clínica) ---
    obra_social: Mapped[str | None] = mapped_column(String(120))
    plan_obra_social: Mapped[str | None] = mapped_column(String(120))
    nro_afiliado: Mapped[str | None] = mapped_column(String(60))

    # Colchón de flexibilidad para campos que sume otro profesional del rubro.
    datos_extra: Mapped[dict] = mapped_column(JSONB, default=dict)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntradaClinica(TenantMixin, Base):
    """Un control / consulta de seguimiento. La evolución del paciente."""

    __tablename__ = "entrada_clinica"
    __table_args__ = (
        Index("ix_entrada_empresa_cliente_fecha", "empresa_id", "cliente_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turno.id"))  # de qué turno salió
    fecha: Mapped[dt.date] = mapped_column(Date)
    tipo: Mapped[str] = mapped_column(String(40), default="control")  # primera_consulta/control/antropometria

    como_se_sintio: Mapped[str | None] = mapped_column(Text)
    noto_diferencia: Mapped[str | None] = mapped_column(Text)
    apetito: Mapped[str | None] = mapped_column(Text)
    entrenamiento: Mapped[str | None] = mapped_column(Text)
    descanso: Mapped[str | None] = mapped_column(Text)
    estres: Mapped[str | None] = mapped_column(Text)
    resumen_antropometria: Mapped[str | None] = mapped_column(Text)
    prescripcion: Mapped[str | None] = mapped_column(Text)
    proximo_turno: Mapped[dt.date | None] = mapped_column(Date)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MedicionAntropometrica(TenantMixin, Base):
    """Mediciones numéricas por fecha. Lo que se grafica en el tiempo."""

    __tablename__ = "medicion_antropometrica"
    __table_args__ = (
        Index("ix_medicion_empresa_cliente_fecha", "empresa_id", "cliente_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    entrada_id: Mapped[int | None] = mapped_column(ForeignKey("entrada_clinica.id"))
    fecha: Mapped[dt.date] = mapped_column(Date)
    evaluador: Mapped[str | None] = mapped_column(String(120))
    origen: Mapped[str] = mapped_column(String(40), default="manual")  # manual / isakmetry

    # --- Básicas ---
    peso_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    talla_cm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    imc: Mapped[float | None] = mapped_column(Numeric(5, 2))
    talla_sentado_cm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    envergadura_cm: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # --- Pliegues (mm) ---
    pl_triceps: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_subescapular: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_biceps: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_cresta_iliaca: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_supraespinal: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_abdominal: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_muslo: Mapped[float | None] = mapped_column(Numeric(5, 1))
    pl_pierna: Mapped[float | None] = mapped_column(Numeric(5, 1))
    sumatoria_pliegues: Mapped[float | None] = mapped_column(Numeric(6, 1))

    # --- Perímetros (cm) ---
    per_cintura: Mapped[float | None] = mapped_column(Numeric(6, 2))
    per_cadera: Mapped[float | None] = mapped_column(Numeric(6, 2))
    per_brazo: Mapped[float | None] = mapped_column(Numeric(6, 2))
    per_muslo: Mapped[float | None] = mapped_column(Numeric(6, 2))
    per_pierna: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # --- Composición corporal ---
    masa_grasa_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    masa_grasa_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    masa_muscular_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    masa_osea_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # Todo el detalle extra del informe ISAK (índices, somatotipo, z-scores, diámetros).
    datos_isak: Mapped[dict] = mapped_column(JSONB, default=dict)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )