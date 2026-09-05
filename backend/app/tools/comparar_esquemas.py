"""Compara DOS bases reales, no la memoria de nadie.

    python -m app.tools.comparar_esquemas base_a base_b

Existe para poder APLASTAR migraciones sin fe: se construye una base con el
historial viejo, otra con el archivo nuevo, y esto dice si son el mismo
esquema. La primera vez que se usó (43 migraciones -> 1) encontró 13
diferencias entre los modelos y las migraciones que nadie sabía que existían.

Un squash es correcto solo si el esquema que produce es INDISTINGUIBLE del que
producían las migraciones que reemplaza. La única forma de saberlo es
preguntarle a Postgres por las dos y comparar, campo por campo.
"""
import sys
from sqlalchemy import create_engine, text

import os

URL = os.environ.get(
    "COMPARAR_URL", "postgresql+psycopg://turnos360:turnos360@localhost:5432/{}"
)

CONSULTAS = {
    "columnas": """
        SELECT table_name, column_name, data_type, is_nullable,
               coalesce(column_default,''), coalesce(character_maximum_length,-1),
               coalesce(numeric_precision,-1), coalesce(numeric_scale,-1)
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name <> 'alembic_version'
        ORDER BY 1,2
    """,
    "indices": """
        SELECT tablename, indexname, indexdef FROM pg_indexes
        WHERE schemaname='public' AND tablename <> 'alembic_version'
        ORDER BY 1,2
    """,
    "constraints": """
        SELECT c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname='public' AND t.relname <> 'alembic_version'
        ORDER BY 1,2
    """,
}

def leer(db):
    e = create_engine(URL.format(db))
    out = {}
    with e.connect() as c:
        for nombre, q in CONSULTAS.items():
            out[nombre] = {tuple(str(x) for x in fila) for fila in c.execute(text(q))}
    return out

BASE_A = sys.argv[1] if len(sys.argv) > 1 else "t360_antes"
BASE_B = sys.argv[2] if len(sys.argv) > 2 else "t360_despues"

a, b = leer(BASE_A), leer(BASE_B)
fallos = 0
for nombre in CONSULTAS:
    solo_a = a[nombre] - b[nombre]
    solo_b = b[nombre] - a[nombre]
    if solo_a or solo_b:
        fallos += 1
        print(f"\n### {nombre.upper()}: {len(solo_a)} solo en {BASE_A}, {len(solo_b)} solo en {BASE_B}")
        for f in sorted(solo_a)[:15]:
            print(f"   SOLO-{BASE_A} ", f)
        for f in sorted(solo_b)[:15]:
            print(f"   SOLO-{BASE_B} ", f)
    else:
        print(f"{nombre}: idénticos ({len(a[nombre])} filas)")

print()
sys.exit(1 if fallos else 0)
