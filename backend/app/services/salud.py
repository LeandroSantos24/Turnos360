"""Lógica de negocio del pack salud / nutrición (E13).

Regla 1 hecha código: toda función recibe empresa_id y filtra por él SIEMPRE.
La ficha es 1:1 con el paciente; guardar_ficha hace upsert (crea o actualiza).
Antes de tocar la ficha, se valida que el paciente sea de ESTA empresa.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Adjunto, EntradaClinica, FichaClinica, MedicionAntropometrica
from app.schemas.salud import AdjuntoCrear, EntradaCrear, FichaGuardar, MedicionCrear
from app.services import cliente as svc_cliente


def obtener_ficha(db: Session, empresa_id: int, cliente_id: int) -> FichaClinica | None:
    """Trae la ficha de un paciente, solo si es de ESTA empresa."""
    return db.scalar(
        select(FichaClinica).where(
            FichaClinica.cliente_id == cliente_id,
            FichaClinica.empresa_id == empresa_id,
        )
    )


def guardar_ficha(
    db: Session, empresa_id: int, cliente_id: int, datos: FichaGuardar
) -> FichaClinica | None:
    """Crea o actualiza la ficha del paciente (upsert).

    Devuelve None si el paciente no existe o es de otra empresa (el router
    lo traduce a 404). Solo se tocan los campos que el usuario envió.
    """
    # El paciente debe pertenecer a esta empresa (doble validación de aislamiento).
    if svc_cliente.obtener(db, empresa_id, cliente_id) is None:
        return None

    ficha = obtener_ficha(db, empresa_id, cliente_id)
    cambios = datos.model_dump(exclude_unset=True)

    if ficha is None:
        ficha = FichaClinica(empresa_id=empresa_id, cliente_id=cliente_id, **cambios)
        db.add(ficha)
    else:
        for campo, valor in cambios.items():
            setattr(ficha, campo, valor)

    db.commit()
    db.refresh(ficha)
    return ficha

# ============================================================
# Evolución (EntradaClinica)
# ============================================================


def listar_entradas(db: Session, empresa_id: int, cliente_id: int) -> list[EntradaClinica]:
    """Controles del paciente, del más reciente al más viejo."""
    return list(
        db.scalars(
            select(EntradaClinica)
            .where(
                EntradaClinica.empresa_id == empresa_id,
                EntradaClinica.cliente_id == cliente_id,
            )
            .order_by(EntradaClinica.fecha.desc(), EntradaClinica.id.desc())
        )
    )


def crear_entrada(
    db: Session, empresa_id: int, cliente_id: int, datos: EntradaCrear
) -> EntradaClinica | None:
    """Alta de un control. None si el paciente no es de esta empresa (→ 404)."""
    if svc_cliente.obtener(db, empresa_id, cliente_id) is None:
        return None
    entrada = EntradaClinica(
        empresa_id=empresa_id, cliente_id=cliente_id, **datos.model_dump()
    )
    db.add(entrada)
    db.commit()
    db.refresh(entrada)
    return entrada


def borrar_entrada(db: Session, empresa_id: int, cliente_id: int, entrada_id: int) -> bool:
    entrada = db.scalar(
        select(EntradaClinica).where(
            EntradaClinica.id == entrada_id,
            EntradaClinica.empresa_id == empresa_id,
            EntradaClinica.cliente_id == cliente_id,
        )
    )
    if entrada is None:
        return False
    db.delete(entrada)
    db.commit()
    return True


# ============================================================
# Mediciones antropométricas
# ============================================================

_PLIEGUES = (
    "pl_triceps", "pl_subescapular", "pl_biceps", "pl_cresta_iliaca",
    "pl_supraespinal", "pl_abdominal", "pl_muslo", "pl_pierna",
)


def listar_mediciones(
    db: Session, empresa_id: int, cliente_id: int
) -> list[MedicionAntropometrica]:
    """Mediciones del paciente en orden cronológico (listas para graficar)."""
    return list(
        db.scalars(
            select(MedicionAntropometrica)
            .where(
                MedicionAntropometrica.empresa_id == empresa_id,
                MedicionAntropometrica.cliente_id == cliente_id,
            )
            .order_by(MedicionAntropometrica.fecha.asc(), MedicionAntropometrica.id.asc())
        )
    )


def _ultima_talla(db: Session, empresa_id: int, cliente_id: int) -> float | None:
    """La talla más reciente registrada (se mide una vez y casi no cambia)."""
    valor = db.scalar(
        select(MedicionAntropometrica.talla_cm)
        .where(
            MedicionAntropometrica.empresa_id == empresa_id,
            MedicionAntropometrica.cliente_id == cliente_id,
            MedicionAntropometrica.talla_cm.is_not(None),
        )
        .order_by(MedicionAntropometrica.fecha.desc(), MedicionAntropometrica.id.desc())
        .limit(1)
    )
    return float(valor) if valor is not None else None


def crear_medicion(
    db: Session, empresa_id: int, cliente_id: int, datos: MedicionCrear
) -> MedicionAntropometrica | None:
    """Alta de una medición. Calcula IMC y sumatoria de pliegues si no vinieron.

    - IMC = peso / (talla_m)²; usa la talla de ESTA medición o la última conocida.
    - Sumatoria de pliegues = suma de los pliegues presentes en esta toma.
    None si el paciente no es de esta empresa (→ 404).
    """
    if svc_cliente.obtener(db, empresa_id, cliente_id) is None:
        return None

    valores = datos.model_dump()

    if valores.get("imc") is None and valores.get("peso_kg"):
        talla = valores.get("talla_cm") or _ultima_talla(db, empresa_id, cliente_id)
        if talla:
            metros = float(talla) / 100
            valores["imc"] = round(float(valores["peso_kg"]) / (metros * metros), 2)

    if valores.get("sumatoria_pliegues") is None:
        pliegues = [float(valores[p]) for p in _PLIEGUES if valores.get(p) is not None]
        if pliegues:
            valores["sumatoria_pliegues"] = round(sum(pliegues), 1)

    medicion = MedicionAntropometrica(empresa_id=empresa_id, cliente_id=cliente_id, **valores)
    db.add(medicion)
    db.commit()
    db.refresh(medicion)
    return medicion


def borrar_medicion(db: Session, empresa_id: int, cliente_id: int, medicion_id: int) -> bool:
    medicion = db.scalar(
        select(MedicionAntropometrica).where(
            MedicionAntropometrica.id == medicion_id,
            MedicionAntropometrica.empresa_id == empresa_id,
            MedicionAntropometrica.cliente_id == cliente_id,
        )
    )
    if medicion is None:
        return False
    db.delete(medicion)
    db.commit()
    return True


# ============================================================
# Adjuntos del paciente (por URL en esta etapa)
# ============================================================


def listar_adjuntos(db: Session, empresa_id: int, cliente_id: int) -> list[Adjunto]:
    return list(
        db.scalars(
            select(Adjunto)
            .where(Adjunto.empresa_id == empresa_id, Adjunto.cliente_id == cliente_id)
            .order_by(Adjunto.fecha.desc(), Adjunto.id.desc())
        )
    )


def crear_adjunto(
    db: Session, empresa_id: int, cliente_id: int, datos: AdjuntoCrear
) -> Adjunto | None:
    """Alta de un adjunto por URL. None si el paciente no es de esta empresa (→ 404).

    Se exige http(s) para que "abrir" funcione siempre desde el panel.
    """
    if svc_cliente.obtener(db, empresa_id, cliente_id) is None:
        return None
    if not datos.ruta.lower().startswith(("http://", "https://")):
        raise ValueError("La ruta debe ser una URL http(s)")
    adjunto = Adjunto(empresa_id=empresa_id, cliente_id=cliente_id, **datos.model_dump())
    db.add(adjunto)
    db.commit()
    db.refresh(adjunto)
    return adjunto


def borrar_adjunto(db: Session, empresa_id: int, cliente_id: int, adjunto_id: int) -> bool:
    adjunto = db.scalar(
        select(Adjunto).where(
            Adjunto.id == adjunto_id,
            Adjunto.empresa_id == empresa_id,
            Adjunto.cliente_id == cliente_id,
        )
    )
    if adjunto is None:
        return False
    db.delete(adjunto)
    db.commit()
    return True
