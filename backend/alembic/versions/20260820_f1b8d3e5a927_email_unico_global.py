"""El email de un usuario pasa a ser único en todo el sistema.

Sale de la auditoría técnica (hallazgo 3.4).

EL PROBLEMA
-----------
`usuario` tenía UNIQUE(empresa_id, email): el email era único DENTRO de cada
empresa. Pero el login busca por email sin filtrar por empresa, y
`Session.scalar()` con varias filas no falla: devuelve la primera que traiga
Postgres, sin criterio.

Con la misma persona dada de alta en dos negocios (un profesional que trabaja
en dos locales, o un dueño con dos sucursales — o sea, el mercado del
producto), pasaba esto:

  · intenta entrar al negocio B con la clave de B  -> 401 permanente, sin
    ninguna explicación y sin forma de arreglarlo desde el panel
  · intenta entrar con la clave de A               -> entra a la empresa A
    creyendo que entró a B

Y dar de alta una empresa nueva con el email de alguien que ya existía dejaba
a esa persona sin acceso, en silencio.

LA DECISIÓN
-----------
Email único global. Una persona = una cuenta = un negocio.

Se elige esto ahora, ANTES de tener producción, porque hoy la migración es
gratis: no hay un solo duplicado que resolver. Dentro de seis meses, con
decenas de negocios, la misma migración sería una tarde de decidir a mano qué
cuenta se queda con cada email.

La limitación (una persona no puede tener cuenta en dos negocios) es real
pero acotada, y sobre todo FALLA EN VOZ ALTA: al crear el usuario aparece un
error claro, en vez de dejar a alguien sin poder entrar sin que nadie sepa
por qué.

Cuando el multi-negocio deje de ser un caso raro, la salida correcta es
separar identidad de membresía (una tabla usuario_empresa con el rol). La
costura ya está: todo el panel filtra por get_current_empresa(), así que ese
día se cambia lo que devuelve esa función y los routers no se tocan.

UNICIDAD SIN DISTINGUIR MAYÚSCULAS
----------------------------------
Se normaliza a minúsculas y el índice va sobre lower(email). Sin eso,
"Juan@Gmail.com" y "juan@gmail.com" serían dos cuentas distintas para el
sistema y la misma para el ser humano, que es exactamente el tipo de
ambigüedad que esta migración viene a eliminar.

Revision ID: f1b8d3e5a927
Revises: e7a2c4b91f60
"""

import sqlalchemy as sa
from alembic import op

revision = "f1b8d3e5a927"
down_revision = "e7a2c4b91f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conexion = op.get_bind()

    # ── 1. Normalizar a minúsculas y sin espacios ──────────────────────────
    conexion.execute(sa.text("UPDATE usuario SET email = lower(btrim(email))"))

    # ── 2. Buscar duplicados ANTES de crear el índice ──────────────────────
    # Si los hay, es mejor cortar acá con un mensaje que se entienda que
    # dejar que Postgres tire un error de índice a mitad del deploy.
    duplicados = conexion.execute(
        sa.text(
            """
            SELECT u.email,
                   count(*) AS cuantos,
                   string_agg(e.nombre, ' | ' ORDER BY e.nombre) AS empresas
            FROM usuario u
            JOIN empresa e ON e.id = u.empresa_id
            GROUP BY u.email
            HAVING count(*) > 1
            ORDER BY count(*) DESC
            """
        )
    ).fetchall()

    if duplicados:
        detalle = "\n".join(
            f"      · {email} — {cuantos} cuentas en: {empresas}"
            for email, cuantos, empresas in duplicados[:20]
        )
        raise RuntimeError(
            "\n\nNo puedo hacer el email único: hay direcciones repetidas en "
            f"distintas empresas ({len(duplicados)} en total).\n\n"
            f"{detalle}\n\n"
            "    Estas personas HOY no pueden entrar a una de sus dos cuentas "
            "(el login devuelve una de las dos al azar).\n\n"
            "    Para resolverlo, por cada email repetido decidí cuál cuenta "
            "conserva la dirección y cambiale el email a la otra:\n\n"
            "        UPDATE usuario SET email = 'otra@direccion.com' "
            "WHERE id = <id de la cuenta que cambia>;\n\n"
            "    Después volvé a correr la migración.\n"
        )

    # ── 3. Fuera el unique por empresa, adentro el global ──────────────────
    op.drop_constraint("uq_usuario_empresa_id", "usuario", type_="unique")

    # Índice funcional sobre lower(email): la unicidad no distingue
    # mayúsculas. Va como índice y no como UniqueConstraint porque Postgres
    # no admite expresiones en una constraint.
    op.create_index(
        "uq_usuario_email_lower",
        "usuario",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_usuario_email_lower", table_name="usuario")
    op.create_unique_constraint("uq_usuario_empresa_id", "usuario", ["empresa_id", "email"])
