"""Datos de demostración para capturas y para probar el sistema con volumen.

Genera ~2 meses de operación realista sobre una empresa YA EXISTENTE: clientes,
turnos, cobros y movimientos de caja, con las fechas repartidas hacia atrás.

Por qué existe: cargar turnos a mano deja todos los cobros con la fecha de hoy,
porque Pago.fecha y MovimientoFinanciero.fecha usan func.now(). Eso está bien
para operar —la plata entró cuando la cobraste— pero para una captura deja
"Mes pasado" vacío y la curva de facturación en una sola línea recta.

Acá las fechas se escriben explícitamente, así que quedan repartidas.

    docker compose --env-file .env -f infra/docker-compose.yml \
      exec backend python -m app.seeds_demo --empresa 1

Para borrar lo generado y volver a empezar:

    ... python -m app.seeds_demo --empresa 1 --limpiar
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
import sys

from sqlalchemy import select, func

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Cliente, Empresa, Recurso, Servicio, Turno
from app.models.enums import EstadoCaja, EstadoTurno, TipoMovimiento
from app.models.finanzas import Caja, MetodoPago, MovimientoFinanciero, Pago

# Marca que permite reconocer y borrar SOLO lo que generó este script.
MARCA = "[demo]"

NOMBRES = [
    ("Martín", "Gómez"), ("Lucas", "Fernández"), ("Nicolás", "Rodríguez"),
    ("Matías", "López"), ("Juan", "Martínez"), ("Facundo", "Pérez"),
    ("Santiago", "Sánchez"), ("Agustín", "Romero"), ("Tomás", "Díaz"),
    ("Franco", "Álvarez"), ("Bruno", "Torres"), ("Iván", "Ruiz"),
    ("Joaquín", "Ramírez"), ("Emiliano", "Flores"), ("Gonzalo", "Acosta"),
    ("Camila", "Benítez"), ("Sofía", "Medina"), ("Valentina", "Herrera"),
    ("Julieta", "Aguirre"), ("Micaela", "Rojas"), ("Brenda", "Molina"),
    ("Carla", "Silva"), ("Rocío", "Castro"), ("Ayelén", "Ortiz"),
    ("Thiago", "Vega"), ("Bautista", "Núñez"), ("Ramiro", "Cabrera"),
    ("Lautaro", "Ledesma"), ("Ignacio", "Peralta"), ("Diego", "Sosa"),
]

# Los canales pesan distinto a propósito: un reparto parejo se ve inventado.
# Instagram y "paso por la puerta" mandan en una barbería de barrio.
# Los valores TIENEN que coincidir con el catálogo del formulario de cliente
# (campos-cliente.tsx). "reserva_online" no existe: la clave correcta es "web".
CANALES = (
    ["instagram"] * 10 + ["paso_por_la_puerta"] * 7 + [None] * 6
    + ["web"] * 5 + ["google"] * 3 + ["referido"] * 3 + ["tiktok"] * 2
)

OBSERVACIONES = [
    "Le gusta el degradé bajo. Viene cada 15 días.",
    "Prefiere que no le toquen el largo de arriba.",
    "Siempre pide turno a la mañana temprano.",
    "Alérgico a la loción con alcohol.",
    "Viene con el hijo, sacar dos turnos seguidos.",
    "",
    "",
    "",
]


def _log(msg: str) -> None:
    print(f"  {msg}")


def limpiar(db, empresa_id: int) -> None:
    """Borra únicamente lo que generó este script.

    El reconocimiento va por la marca en `notas` (turnos) y `observaciones`
    (clientes). Nunca se borra por rango de fechas: eso se llevaría puestos los
    datos reales del negocio si alguien lo corriera sobre una base en uso.
    """
    turnos = list(
        db.scalars(
            select(Turno).where(
                Turno.empresa_id == empresa_id, Turno.notas.like(f"{MARCA}%")
            )
        )
    )
    ids = [t.id for t in turnos]
    if ids:
        pagos = list(db.scalars(select(Pago).where(Pago.turno_id.in_(ids))))
        movs = [p.movimiento_id for p in pagos if p.movimiento_id]
        for p in pagos:
            db.delete(p)
        db.flush()
        if movs:
            for m in db.scalars(
                select(MovimientoFinanciero).where(MovimientoFinanciero.id.in_(movs))
            ):
                db.delete(m)
        for t in turnos:
            db.delete(t)
    clientes = list(
        db.scalars(
            select(Cliente).where(
                Cliente.empresa_id == empresa_id,
                Cliente.observaciones.like(f"%{MARCA}"),
            )
        )
    )
    for c in clientes:
        db.delete(c)
    db.commit()
    _log(f"borrados: {len(turnos)} turnos, {len(clientes)} clientes")


def generar(db, empresa_id: int, dias: int, por_dia: tuple[int, int]) -> None:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        sys.exit(f"No existe la empresa {empresa_id}.")

    servicios = list(
        db.scalars(
            select(Servicio).where(
                Servicio.empresa_id == empresa_id, Servicio.activo.is_(True)
            )
        )
    )
    recursos = list(
        db.scalars(
            select(Recurso).where(
                Recurso.empresa_id == empresa_id, Recurso.activo.is_(True)
            )
        )
    )
    metodos = list(
        db.scalars(
            select(MetodoPago).where(
                MetodoPago.empresa_id == empresa_id, MetodoPago.activo.is_(True)
            )
        )
    )
    if not servicios or not recursos or not metodos:
        sys.exit(
            "La empresa necesita al menos un servicio, un recurso y un método "
            "de pago cargados antes de generar la demo."
        )

    _log(f"empresa: {empresa.nombre}")
    _log(f"{len(servicios)} servicios · {len(recursos)} recursos · {len(metodos)} métodos")

    # --- Clientes -----------------------------------------------------------
    clientes = []
    for nombre, apellido in NOMBRES:
        c = Cliente(
            empresa_id=empresa_id,
            nombre=nombre,
            apellido=apellido,
            telefono=f"261{random.randint(3000000, 7999999)}",
            email=f"{nombre.lower()}.{apellido.lower()}@example.com".replace("á", "a")
            .replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u"),
            canal_adquisicion=random.choice(CANALES),
            acepta_marketing=random.random() < 0.6,
            observaciones=f"{random.choice(OBSERVACIONES)} {MARCA}".strip(),
            activo=True,
        )
        db.add(c)
        clientes.append(c)
    db.flush()
    _log(f"{len(clientes)} clientes creados")

    # --- Caja para colgar los movimientos -----------------------------------
    caja = db.scalar(
        select(Caja).where(
            Caja.empresa_id == empresa_id, Caja.estado == EstadoCaja.ABIERTA
        )
    )
    if caja is None:
        caja = Caja(
            empresa_id=empresa_id,
            fecha_apertura=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias),
            saldo_inicial=0,
            estado=EstadoCaja.ABIERTA,
        )
        db.add(caja)
        db.flush()

    hoy = dt.date.today()
    creados = cobrados = 0
    total = 0.0

    for d in range(dias, -1, -1):
        dia = hoy - dt.timedelta(days=d)
        if dia.weekday() == 6:  # domingo cerrado
            continue

        # Curva creciente suave: el negocio arranca flojo y se llena. Un
        # volumen plano en la captura se lee como dato inventado.
        avance = 1 - (d / max(dias, 1))
        base = por_dia[0] + (por_dia[1] - por_dia[0]) * avance
        cantidad = max(1, round(random.gauss(base, 1.4)))
        if dia.weekday() == 5:  # sábado se llena
            cantidad = round(cantidad * 1.5)

        horas = list(range(9, 20))
        random.shuffle(horas)
        for i in range(cantidad):
            if i >= len(horas):
                break
            hora = horas[i]
            minuto = random.choice([0, 30])
            servicio = random.choice(servicios)
            recurso = random.choice(recursos)
            cliente = random.choice(clientes)
            inicio = dt.datetime.combine(dia, dt.time(hora, minuto))
            fin = inicio + dt.timedelta(minutes=servicio.duracion_min or 30)
            precio = float(servicio.precio or 0)

            # Distribución de estados. El 7% de ausentes no es decorativo: sin
            # ausencias la tarjeta de ausentismo queda en 0% y el semáforo no
            # se puede mostrar.
            if dia < hoy:
                r = random.random()
                estado = (
                    EstadoTurno.AUSENTE if r < 0.07
                    else EstadoTurno.CANCELADO if r < 0.11
                    else EstadoTurno.FINALIZADO
                )
            else:
                estado = random.choice(
                    [EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO, EstadoTurno.CONFIRMADO]
                )

            turno = Turno(
                empresa_id=empresa_id,
                cliente_id=cliente.id,
                recurso_id=recurso.id,
                servicio_id=servicio.id,
                estado=estado,
                fecha_inicio=inicio,
                fecha_fin=fin,
                importe_previsto=precio,
                notas=f"{MARCA} generado para demostración",
                creado_en=inicio - dt.timedelta(days=random.randint(1, 6)),
            )
            db.add(turno)
            db.flush()
            creados += 1

            if estado != EstadoTurno.FINALIZADO:
                continue

            # Adicionales ocasionales: sin esto todos los tickets son idénticos
            # y el "ticket promedio" queda clavado en el precio de lista.
            monto = precio + (random.choice([1500, 2000, 3000]) if random.random() < 0.22 else 0)
            metodo = random.choice(metodos)
            comision = round(monto * float(metodo.comision_pct or 0) / 100, 2)
            # La fecha se fija a mano: es todo el punto de este script.
            cuando = fin.replace(tzinfo=dt.timezone.utc)

            mov = MovimientoFinanciero(
                empresa_id=empresa_id,
                caja_id=caja.id,
                fecha=cuando,
                tipo=TipoMovimiento.INGRESO,
                concepto=servicio.nombre,
                monto=monto,
                metodo_pago_id=metodo.id,
            )
            db.add(mov)
            db.flush()
            db.add(
                Pago(
                    empresa_id=empresa_id,
                    turno_id=turno.id,
                    cliente_id=cliente.id,
                    metodo_pago_id=metodo.id,
                    monto=monto,
                    comision_aplicada=comision,
                    movimiento_id=mov.id,
                    fecha=cuando,
                )
            )
            turno.cobrado = True
            cobrados += 1
            total += monto

    db.commit()
    _log(f"{creados} turnos · {cobrados} cobrados · ${total:,.0f}".replace(",", "."))


def main() -> None:
    ap = argparse.ArgumentParser(description="Datos de demostración")
    ap.add_argument("--empresa", type=int, required=True, help="id de la empresa")
    ap.add_argument("--dias", type=int, default=75, help="días hacia atrás")
    ap.add_argument("--limpiar", action="store_true", help="borrar la demo anterior")
    ap.add_argument("--forzar", action="store_true", help="permitir en producción")
    args = ap.parse_args()

    # En producción hay turnos de gente real: un script que escribe decenas de
    # turnos falsos en la agenda de un negocio que está operando arruina su
    # caja y su historial, y no hay forma prolija de deshacerlo.
    if settings.es_produccion and not args.forzar:
        sys.exit(
            "Estás en PRODUCCIÓN. Este script escribe turnos y cobros falsos.\n"
            "Si de verdad querés hacerlo (por ejemplo, en una empresa de "
            "demostración), agregá --forzar."
        )

    random.seed(42)  # mismo resultado en cada corrida: las capturas se repiten
    with SessionLocal() as db:
        if args.limpiar:
            limpiar(db, args.empresa)
            return
        # Aviso si la empresa ya tiene movimiento propio.
        previos = db.scalar(
            select(func.count(Turno.id)).where(
                Turno.empresa_id == args.empresa, Turno.notas.not_like(f"{MARCA}%")
            )
        )
        if previos:
            _log(f"OJO: la empresa ya tiene {previos} turnos propios. Se suman a esos.")
        generar(db, args.empresa, args.dias, por_dia=(4, 9))
    print("\nListo. Recargá el panel.")


if __name__ == "__main__":
    main()
