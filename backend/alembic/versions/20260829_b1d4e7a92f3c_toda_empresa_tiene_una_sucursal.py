"""Toda empresa tiene una sucursal: backfill, NOT NULL y FK compuesta.

Paso 1 de multisucursal (E16).

`sucursal_id` existe como columna en recurso, usuario, turno y caja desde la
migración inicial de junio, pero es nullable y SIEMPRE vale NULL: ningún código
la escribe y ninguno la lee.

Construir multisucursal encima de eso significaría arrastrar un
`OR sucursal_id IS NULL` en cada consulta de agenda, caja y disponibilidad para
no perder los datos viejos: dos caminos de código para siempre, y el segundo
—el que casi nunca corre— es donde se esconden los bugs.

Esta migración cierra esa puerta antes de abrirla:

1. Cada empresa que no tenga sucursal recibe una, llamada como el negocio.
2. Las cuatro tablas apuntan a la sucursal de SU empresa.
3. Las columnas pasan a NOT NULL.
4. La FK simple a sucursal.id se reemplaza por una COMPUESTA
   (empresa_id, sucursal_id), para que la base rechace apuntar a la sucursal
   de otra empresa. Regla 1 puesta donde no se puede olvidar.

Es reversible: el downgrade vuelve las columnas a nullable y repone la FK
simple. No borra las sucursales creadas — borrarlas dejaría datos colgando y
no es lo que nadie quiere de un rollback.

Revision ID: b1d4e7a92f3c
Revises: f22c3d3bb82a
"""

from alembic import op
import sqlalchemy as sa

revision = "b1d4e7a92f3c"
down_revision = "f22c3d3bb82a"
branch_labels = None
depends_on = None


# Las cuatro tablas que ya tenían la columna, con el nombre de su FK vieja.
TABLAS = ["recurso", "usuario", "turno", "caja"]


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Una sucursal por empresa que no tenga ninguna ────────────────
    # El nombre sale del negocio. Se recorta a 120 por el largo de la columna.
    conn.execute(
        sa.text(
            """
            INSERT INTO sucursal (empresa_id, nombre, direccion, activa)
            SELECT e.id, LEFT(e.nombre, 120), e.direccion, true
              FROM empresa e
             WHERE NOT EXISTS (
                   SELECT 1 FROM sucursal s WHERE s.empresa_id = e.id
             )
            """
        )
    )

    # ── 2. Backfill: cada fila a la sucursal MÁS VIEJA de su empresa ────
    # Solo se tocan los NULL. Si algo ya tenía sucursal cargada, se respeta.
    for tabla in TABLAS:
        conn.execute(
            sa.text(
                f"""
                UPDATE {tabla} t
                   SET sucursal_id = (
                       SELECT s.id FROM sucursal s
                        WHERE s.empresa_id = t.empresa_id
                        ORDER BY s.id
                        LIMIT 1
                   )
                 WHERE t.sucursal_id IS NULL
                """
            )
        )

    # ── 3. Red de seguridad ─────────────────────────────────────────────
    # Si quedó un NULL, el SET NOT NULL de abajo iba a fallar igual, pero con
    # un error de Postgres que no dice qué tabla ni por qué. Mejor fallar acá
    # con el motivo escrito.
    for tabla in TABLAS:
        faltan = conn.execute(
            sa.text(f"SELECT count(*) FROM {tabla} WHERE sucursal_id IS NULL")
        ).scalar_one()
        if faltan:
            raise RuntimeError(
                f"Quedaron {faltan} filas de '{tabla}' sin sucursal. Casi seguro "
                f"son filas cuyo empresa_id no existe en la tabla empresa. "
                f"Revisalas antes de volver a correr la migración."
            )

    # ── 4. UNIQUE (empresa_id, id) en sucursal ──────────────────────────
    # Redundante como identidad, imprescindible como destino de la FK compuesta:
    # Postgres exige que las columnas referenciadas tengan una unique en ese
    # orden exacto.
    op.create_unique_constraint(
        "uq_sucursal_empresa", "sucursal", ["empresa_id", "id"]
    )

    # ── 5. NOT NULL + cambio de FK simple por compuesta ─────────────────
    for tabla in TABLAS:
        op.alter_column(tabla, "sucursal_id", nullable=False)

        # La FK vieja se llama distinto en cada tabla y la puso Postgres sola.
        # Se busca por catálogo en vez de adivinar el nombre.
        vieja = conn.execute(
            sa.text(
                """
                SELECT con.conname
                  FROM pg_constraint con
                  JOIN pg_class rel ON rel.oid = con.conrelid
                  JOIN pg_attribute att
                    ON att.attrelid = rel.oid AND att.attnum = con.conkey[1]
                 WHERE con.contype = 'f'
                   AND rel.relname = :tabla
                   AND att.attname = 'sucursal_id'
                   AND array_length(con.conkey, 1) = 1
                """
            ),
            {"tabla": tabla},
        ).scalar()
        if vieja:
            op.drop_constraint(vieja, tabla, type_="foreignkey")

        op.create_foreign_key(
            f"fk_{tabla}_sucursal",
            tabla,
            "sucursal",
            ["empresa_id", "sucursal_id"],
            ["empresa_id", "id"],
        )

    # ── 6. Teléfono propio del local ────────────────────────────────────
    op.add_column("sucursal", sa.Column("telefono", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("sucursal", "telefono")

    for tabla in TABLAS:
        op.drop_constraint(f"fk_{tabla}_sucursal", tabla, type_="foreignkey")
        op.create_foreign_key(
            f"fk_{tabla}_sucursal_simple", tabla, "sucursal", ["sucursal_id"], ["id"]
        )
        op.alter_column(tabla, "sucursal_id", nullable=True)

    op.drop_constraint("uq_sucursal_empresa", "sucursal", type_="unique")
    # Las sucursales creadas se quedan: borrarlas dejaría a las cuatro tablas
    # apuntando a filas que ya no existen.
