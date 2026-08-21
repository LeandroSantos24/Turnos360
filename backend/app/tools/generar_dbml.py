#!/usr/bin/env python3
"""Genera docs/turnos360.dbml a partir de los modelos de verdad.

Por qué existe
--------------
El .dbml estaba escrito a mano y se fue quedando atrás: documentaba 17 tablas
que no existen (vehiculo, orden_trabajo, plan_saas, saldo_puntos…) y le
faltaban 7 que sí (item_turno, cupon_descuento, wa_saldo, wa_movimiento…).

Un diagrama desactualizado es peor que no tener diagrama. Sin diagrama, el que
llega lee los modelos. Con uno que miente, diseña una consulta contra una
tabla que no existe y se entera media hora después.

Escrito a mano se vuelve a desactualizar el mes que viene. Generado desde
`Base.metadata`, no puede: es la misma fuente que crea las tablas.

Uso:
    python -m app.tools.generar_dbml            # escribe el archivo
    python -m app.tools.generar_dbml --check    # solo avisa si está viejo (CI)

El modo --check es el que hace que esto se sostenga: hay un test que lo corre,
así que agregar un modelo y olvidarse de regenerar el diagrama pone la suite
en rojo el mismo día, no dentro de seis meses.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401  — importarlo registra TODO el metadata
from app.db.base import Base

def _destino() -> Path:
    """Dónde vive docs/turnos360.dbml. SIN adivinar contando carpetas.

    La primera versión de esto hacía `parents[3]`, que es correcto en el repo
    (backend/app/tools -> backend -> raíz) y MAL adentro del contenedor, donde
    solo se monta backend/ en /app y sobra un nivel. Ahí escribía en /docs, un
    directorio del contenedor que no existe afuera: el comando decía "✔ 39
    tablas" y el archivo del repo no se tocaba. Un verde mentiroso.

    Ahora se busca hacia arriba el primer directorio que TENGA un docs/. Si no
    hay ninguno, devuelve None y el que llama decide qué hacer — que es mejor
    que escribir en un lugar inventado.
    """
    forzado = os.environ.get("DBML_DESTINO")
    if forzado:
        return Path(forzado)
    for base in Path(__file__).resolve().parents:
        if (base / "docs").is_dir():
            return base / "docs" / "turnos360.dbml"
    return None


DESTINO = _destino()

CABECERA = """// Turnos360 — esquema de la base
//
// GENERADO AUTOMÁTICAMENTE. No lo edites a mano: se regenera con
//     make dbml     (o: python -m app.tools.generar_dbml)
// y hay un test que falla si queda desactualizado.
//
// Para verlo: https://dbdiagram.io  ->  Import  ->  pegar este archivo.

Project turnos360 {
  database_type: 'PostgreSQL'
  Note: 'Gestión de turnos multiempresa. Toda tabla de negocio lleva empresa_id (Regla 1).'
}

"""


def _tipo(col) -> str:
    """El tipo de la columna, en la forma que entiende dbdiagram."""
    if isinstance(col.type, SAEnum):
        # Los enums nativos de Postgres se declaran aparte, más abajo.
        return col.type.name or "text"
    # Se compila contra el dialecto de Postgres a propósito: el diagrama tiene
    # que decir el tipo REAL de la base (timestamptz, jsonb, bytea), no el
    # genérico de SQLAlchemy. Es la mitad de la utilidad de tener el diagrama.
    try:
        return col.type.compile(dialect=postgresql.dialect()).lower()
    except Exception:
        return str(col.type).lower()


def _atributos(tabla, col) -> str:
    partes = []
    if col.primary_key:
        partes.append("pk")
    if col.foreign_keys:
        destino = list(col.foreign_keys)[0].target_fullname
        partes.append(f"ref: > {destino}")
    if not col.nullable and not col.primary_key:
        partes.append("not null")
    if col.unique:
        partes.append("unique")
    # `index=True` en el modelo no aparece en col.index de forma confiable
    # cuando el índice se declaró en __table_args__, así que los índices van
    # todos juntos en el bloque Indexes de la tabla.
    return f" [{', '.join(partes)}]" if partes else ""


def _bloque_indices(tabla) -> str:
    filas = []
    for indice in sorted(tabla.indexes, key=lambda i: i.name or ""):
        columnas = [c.name for c in indice.columns]
        if not columnas:
            continue
        expr = columnas[0] if len(columnas) == 1 else "(" + ", ".join(columnas) + ")"
        atributos = ["name: '%s'" % indice.name] if indice.name else []
        if indice.unique:
            atributos.append("unique")
        filas.append(f"    {expr} [{', '.join(atributos)}]" if atributos else f"    {expr}")
    if not filas:
        return ""
    return "\n  Indexes {\n" + "\n".join(filas) + "\n  }\n"


def _enums() -> str:
    """Los enums nativos, declarados una sola vez."""
    vistos = {}
    for tabla in Base.metadata.tables.values():
        for col in tabla.columns:
            if isinstance(col.type, SAEnum) and col.type.name:
                vistos[col.type.name] = list(col.type.enums)
    if not vistos:
        return ""
    salida = ["// ── Enums ──────────────────────────────────────────────────"]
    for nombre in sorted(vistos):
        valores = "\n".join(f'  "{v}"' for v in vistos[nombre])
        salida.append(f"Enum {nombre} {{\n{valores}\n}}\n")
    return "\n".join(salida) + "\n"


def generar() -> str:
    partes = [CABECERA, _enums()]
    partes.append("// ── Tablas ─────────────────────────────────────────────────\n")
    for nombre in sorted(Base.metadata.tables):
        tabla = Base.metadata.tables[nombre]
        lineas = [f"Table {nombre} {{"]
        for col in tabla.columns:
            lineas.append(f"  {col.name} {_tipo(col)}{_atributos(tabla, col)}")
        indices = _bloque_indices(tabla)
        if indices:
            lineas.append(indices.rstrip("\n"))
        if tabla.comment:
            lineas.append(f"  Note: '{tabla.comment}'")
        lineas.append("}\n")
        partes.append("\n".join(lineas))
    return "\n".join(partes)


def main() -> int:
    contenido = generar()

    # --stdout: escupe el diagrama y no toca ningún archivo. Es lo que usa
    # `make dbml`, que redirige la salida del contenedor al archivo del repo.
    # Así funciona monten lo que monten.
    if "--stdout" in sys.argv:
        sys.stdout.write(contenido)
        return 0

    solo_chequear = "--check" in sys.argv

    if DESTINO is None:
        print("✘ No encuentro la carpeta docs/ desde acá.")
        print("  Si estás adentro del contenedor, el repo no está montado entero.")
        print("  Corré desde la raíz del repo:  make dbml")
        return 1

    if solo_chequear:
        if not DESTINO.exists():
            print(f"✘ No existe {DESTINO}. Corré:  make dbml")
            return 1
        if DESTINO.read_text(encoding="utf-8") != contenido:
            print("✘ docs/turnos360.dbml está desactualizado respecto de los modelos.")
            print("  Regeneralo con:  make dbml")
            return 1
        print("✔ El diagrama está al día.")
        return 0

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(contenido, encoding="utf-8")
    print(f"✔ {DESTINO}  ({len(Base.metadata.tables)} tablas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
