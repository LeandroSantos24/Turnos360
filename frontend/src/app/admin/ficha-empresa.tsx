"use client";

/**
 * La ficha de un negocio: cómo está, de un vistazo.
 *
 * QUÉ REEMPLAZA
 * ─────────────
 * El listado daba nombre, rubro, slug, usuarios y vencimiento. Con eso se sabe
 * que una empresa existe, y poco más. Para cualquier pregunta real —¿está
 * pagando?, ¿lo usa?, ¿le queda chico el plan?, ¿le entra gente a la página?—
 * había que cruzar tres pantallas o entrar a la base.
 *
 * CÓMO ESTÁ ORDENADA
 * ──────────────────
 * De arriba abajo, por urgencia: primero lo que exige una acción HOY (un aviso
 * de transferencia esperando, una cuota vencida), después la plata, después el
 * uso, y al final los datos de contacto que casi nunca se miran. Quien abre
 * esto viene con una pregunta; el orden es el de las preguntas más frecuentes.
 *
 * SOBRE LOS COLORES
 * ─────────────────
 * Verde, ámbar y rojo son ESTADOS y usan la paleta de estado del resto del
 * panel — no son series de un gráfico. Cada uno va con su palabra escrita al
 * lado, nunca solo con el color: quien no distingue el ámbar del verde lee
 * igual, y en blanco y negro también.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Clock } from "lucide-react";

import { FichaEmpresa, fichaEmpresa } from "@/lib/admin-api";

const PESOS = (n: number | null | undefined) =>
  n == null ? "—" : `$${Number(n).toLocaleString("es-AR")}`;

const FECHA = (iso: string | null) =>
  !iso ? "—" : new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("es-AR");

const TONO: Record<string, string> = {
  verde: "text-emerald-700 dark:text-emerald-400",
  amarillo: "text-amber-700 dark:text-amber-400",
  rojo: "text-red-700 dark:text-red-400",
  azul: "text-sky-700 dark:text-sky-400",
  gris: "text-muted-foreground",
};
const PUNTO: Record<string, string> = {
  verde: "bg-emerald-500",
  amarillo: "bg-amber-500",
  rojo: "bg-red-500",
  azul: "bg-sky-500",
  gris: "bg-muted-foreground/40",
};

/** Un número grande con su etiqueta. Sin gráfico: es un dato, no una serie. */
function Dato({
  titulo,
  valor,
  pie,
  tono,
}: {
  titulo: string;
  valor: string;
  pie?: string;
  tono?: string;
}) {
  return (
    <div className="rounded-xl border bg-background p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{titulo}</p>
      <p className={`mt-1 text-xl font-bold tabular-nums ${tono ?? ""}`}>{valor}</p>
      {pie && <p className="mt-0.5 text-xs text-muted-foreground">{pie}</p>}
    </div>
  );
}

/**
 * Cuánto de lo que compró está usando.
 *
 * La barra es lo que convierte «2» en una respuesta: 2 de 3 está al límite y
 * 2 de 10 sobra. Sin el tope al lado, el número obliga a recordar de memoria
 * la grilla de planes.
 */
function Cupo({
  etiqueta,
  usados,
  tope,
}: {
  etiqueta: string;
  usados: number;
  tope: number | null;
}) {
  const sinTope = tope == null;
  const pct = sinTope ? 0 : Math.min(100, (usados / Math.max(tope, 1)) * 100);
  // Al 100 % no puede sumar uno más: eso es una venta esperando, no un error.
  const lleno = !sinTope && usados >= tope;

  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted-foreground">{etiqueta}</span>
        <span className="tabular-nums font-medium">
          {usados}
          {sinTope ? " · sin tope" : ` de ${tope}`}
          {lleno && (
            <span className="ml-1.5 text-xs font-normal text-amber-700 dark:text-amber-400">
              al límite
            </span>
          )}
        </span>
      </div>
      {!sinTope && (
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${lleno ? "bg-amber-500" : "bg-primary"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}

/**
 * Las visitas de los últimos 30 días.
 *
 * Barras y no una línea: son cuentas de días sueltos, no una magnitud continua
 * — una línea sugiere que entre el martes y el miércoles hubo valores
 * intermedios, y no los hay.
 *
 * Sin ejes ni grilla: acá la pregunta no es «cuántas exactamente el día 12»
 * sino «¿esto sube o baja?». El total va escrito arriba, que es el número que
 * alguien se llevaría anotado. Cada barra tiene su día y su cuenta en el
 * `title` para el que quiera el detalle.
 */
function Visitas({ serie, total }: { serie: { dia: string; visitas: number }[]; total: number }) {
  const max = Math.max(1, ...serie.map((d) => d.visitas));
  const sinNada = total === 0;

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-muted-foreground">Visitas a la página</span>
        <span className="text-sm tabular-nums font-medium">
          {total} en 30 días
        </span>
      </div>

      {sinNada ? (
        <p className="mt-2 rounded-lg border border-dashed p-2.5 text-xs text-muted-foreground">
          Todavía nadie abrió su página. Si el negocio dice que no le entran
          turnos, empezá por acá: el problema no está en la agenda.
        </p>
      ) : (
        <div className="mt-2 flex h-12 items-end gap-[2px]">
          {serie.map((d) => (
            <div
              key={d.dia}
              title={`${FECHA(d.dia)}: ${d.visitas} ${d.visitas === 1 ? "visita" : "visitas"}`}
              className="flex-1 rounded-sm bg-primary/70"
              // Mínimo 2px: un día con una visita tiene que verse distinto de
              // uno con cero, que es justo la comparación que importa.
              style={{ height: `${Math.max(d.visitas === 0 ? 0 : 8, (d.visitas / max) * 100)}%` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function Ficha({ empresaId }: { empresaId: number }) {
  const [f, setF] = useState<FichaEmpresa | null>(null);
  const [error, setError] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setF(await fichaEmpresa(empresaId));
    } catch {
      setError(true);
    }
  }, [empresaId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (error) {
    return <p className="p-4 text-sm text-destructive">No se pudo cargar la ficha.</p>;
  }
  if (!f) {
    return <p className="p-4 text-sm text-muted-foreground">Cargando…</p>;
  }

  const s = f.suscripcion;

  return (
    <div className="space-y-4 border-t bg-muted/20 p-4">
      {/* LO QUE EXIGE UNA ACCIÓN HOY, arriba de todo. */}
      {f.cobranza.aviso_pendiente && (
        <div className="flex gap-3 rounded-xl border border-sky-500/40 bg-sky-500/10 p-3">
          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" />
          <div className="text-sm">
            <p className="font-medium">Dice que ya transfirió</p>
            <p className="mt-0.5 text-muted-foreground">
              {PESOS(f.cobranza.aviso_pendiente.monto)}
              {f.cobranza.aviso_pendiente.referencia
                ? ` · ${f.cobranza.aviso_pendiente.referencia}`
                : ""}
              . Confirmalo en Cobranza.
            </p>
          </div>
        </div>
      )}

      {s.color === "rojo" && (
        <div className="flex gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
          <p className="text-sm">
            <span className="font-medium">Vencida.</span>{" "}
            <span className="text-muted-foreground">{s.detalle}</span>
          </p>
        </div>
      )}

      {/* Los cuatro números que contestan «¿cómo está?». */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Dato
          titulo="Estado"
          valor={s.detalle}
          tono={TONO[s.color]}
          pie={s.vence ? `Vence ${FECHA(s.vence)}` : "Sin vencimiento"}
        />
        <Dato
          titulo="Plan"
          valor={f.plan.etiqueta}
          pie={`${PESOS(f.plan.precio)}${f.plan.precio_pactado ? " · pactado" : " por mes"}`}
        />
        <Dato
          titulo="Cobrado"
          valor={PESOS(f.cobranza.total_cobrado)}
          pie={
            f.cobranza.ultimo_pago
              ? `Último: ${FECHA(f.cobranza.ultimo_pago.fecha)}`
              : "Todavía no pagó"
          }
        />
        <Dato
          titulo="Turnos"
          valor={String(f.actividad.turnos_30d)}
          pie="Últimos 30 días"
          tono={f.actividad.turnos_30d === 0 ? TONO.amarillo : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Uso: si le queda chico el plan, es una venta. */}
        <div className="space-y-3 rounded-xl border bg-background p-3.5">
          <p className="text-sm font-medium">Cuánto usa de lo que compró</p>
          <Cupo
            etiqueta="Profesionales"
            usados={f.uso.profesionales.usados}
            tope={f.uso.profesionales.tope}
          />
          <Cupo
            etiqueta="Cuentas"
            usados={f.uso.usuarios.usados}
            tope={f.uso.usuarios.tope}
          />
          <Cupo
            etiqueta="Locales"
            usados={f.uso.sucursales.usados}
            tope={f.uso.sucursales.tope}
          />
          <p className="pt-1 text-xs text-muted-foreground">
            {f.uso.clientes} clientes · {f.uso.servicios} servicios
          </p>
        </div>

        {/* Actividad: si no lo usa, se va a ir. */}
        <div className="space-y-3 rounded-xl border bg-background p-3.5">
          <p className="text-sm font-medium">Si lo está usando</p>
          <Visitas
            serie={f.actividad.visitas_por_dia}
            total={f.actividad.visitas_30d}
          />
          <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-muted-foreground">
            <span>
              Último turno:{" "}
              {f.actividad.ultimo_turno ? FECHA(f.actividad.ultimo_turno) : "ninguno"}
            </span>
            <span>
              Cliente desde: {FECHA(f.creada_en)}
              {f.antiguedad_dias != null && ` (${f.antiguedad_dias} días)`}
            </span>
          </div>
        </div>
      </div>

      {/* Contacto: lo que menos se mira, al final. */}
      {(f.contacto.nombre || f.contacto.email || f.contacto.telefono) && (
        <div className="rounded-xl border bg-background p-3.5 text-sm">
          <p className="font-medium">Contacto</p>
          <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
            {f.contacto.nombre && <span>{f.contacto.nombre}</span>}
            {f.contacto.email && <span>{f.contacto.email}</span>}
            {f.contacto.telefono && <span>{f.contacto.telefono}</span>}
            {f.contacto.cuit && <span>CUIT {f.contacto.cuit}</span>}
          </p>
        </div>
      )}

      {f.notas_admin && (
        <div className="rounded-xl border bg-background p-3.5 text-sm">
          <p className="font-medium">Notas</p>
          <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
            {f.notas_admin}
          </p>
        </div>
      )}

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className={`h-2 w-2 rounded-full ${PUNTO[s.color]}`} />
        {s.detalle}
        {s.en_prorroga && " · está dentro de los días de gracia"}
      </p>
    </div>
  );
}
