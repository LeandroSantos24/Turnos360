"use client";

/**
 * Mi suscripción · Actividad: lo que pasó con la suscripción, en orden y con
 * quién lo hizo. Sale de los eventos que registra el servidor (pagos
 * acreditados, cambios de plan, renovaciones, cancelaciones, programados).
 */

import { Activity } from "lucide-react";

import { Cargando, fechaHora, pesos, useSuscripcion } from "../_suscripcion";

export default function SuscripcionActividad() {
  const { datos, cargando } = useSuscripcion();
  if (cargando || !datos) return <Cargando />;

  if (datos.actividad.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border bg-card px-6 py-10 text-center">
        <Activity className="h-8 w-8 text-muted-foreground/60" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Todavía no hay movimientos. Cuando pagues, cambies de plan o renueves, queda registrado acá.
        </p>
      </div>
    );
  }

  return (
    <section className="rounded-2xl border bg-card p-5 md:p-6">
      <ol className="relative space-y-5 border-l pl-5">
        {datos.actividad.map((ev, i) => (
          <li key={i} className="relative">
            <span className="absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-card bg-primary" aria-hidden />
            <p className="text-sm">
              <span className="font-medium">{ev.titulo}</span>
              {ev.monto != null && <span className="font-medium tabular-nums"> · {pesos(ev.monto)}</span>}
            </p>
            {ev.detalle && <p className="text-sm text-muted-foreground">{ev.detalle}</p>}
            <p className="mt-0.5 text-xs text-muted-foreground">
              {fechaHora(ev.fecha)} · {ev.quien}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
