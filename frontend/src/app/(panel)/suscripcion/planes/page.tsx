"use client";

/**
 * Mi suscripción · Planes.
 *
 * La grilla y los precios salen del servidor (core/planes.py). Esta pantalla
 * solo ordena y rotula: tu plan, mejoras, planes inferiores y el personalizado.
 * Las reglas de cuándo se aplica cada cambio las resuelve el circuito de pago
 * (./cambiar), que es el mismo de siempre.
 */

import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Check, Clock, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { WA_LINK_ENTERPRISE } from "@/lib/contacto";
import type { PlanDeLaGrilla } from "@/lib/empresa-api";
import { Cargando, SYNE, fechaLarga, miPrecioActual, pesos, useSuscripcion } from "../_suscripcion";

export default function SuscripcionPlanes() {
  const router = useRouter();
  const { datos, cargando } = useSuscripcion();
  if (cargando || !datos) return <Cargando />;

  const cancelada = datos.estado === "cancelada";
  const suspendida = datos.estado === "suspendida";
  const enPrueba = datos.estado === "prueba" || datos.estado === "prueba_vencida";
  const miPrecio = miPrecioActual(datos);
  const irAlCircuito = (plan: string) => router.push(`/suscripcion/cambiar?plan=${plan}`);

  if (suspendida || datos.grilla.length === 0) {
    return (
      <p className="rounded-2xl border bg-card p-6 text-sm text-muted-foreground">
        {suspendida
          ? "Tu cuenta está suspendida: escribinos para reactivarla y después vas a poder cambiar de plan."
          : "No hay planes disponibles para cambiar en este momento."}
      </p>
    );
  }

  function tipo(p: PlanDeLaGrilla): "mio" | "sube" | "baja" | "convenir" {
    if (p.a_convenir) return "convenir";
    if (p.codigo === datos!.plan_codigo && !enPrueba) return "mio";
    return p.precio > (miPrecio ?? 0) || enPrueba ? "sube" : "baja";
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <Regla icono={<ArrowUp className="h-4 w-4" />} titulo="Mejorar el plan">
          Se paga al momento y suma 30 días con el plan nuevo.
        </Regla>
        <Regla icono={<ArrowDown className="h-4 w-4" />} titulo="Bajar de plan">
          Se aplica al terminar el período que ya pagaste. Hasta ahí seguís con todo.
        </Regla>
      </div>

      {datos.plan_programado && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-amber-400/50 bg-amber-50 p-4 text-sm dark:border-amber-700/50 dark:bg-amber-950/40">
          <Clock className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
          <p className="min-w-0 flex-1 text-amber-900 dark:text-amber-200">
            Seguís en <b>{datos.plan_etiqueta}</b>
            {datos.vence ? ` hasta el ${fechaLarga(datos.vence)}` : ""} y ahí pasás a{" "}
            <b>{datos.plan_programado_etiqueta}</b>.
          </p>
          <Button size="sm" variant="outline" onClick={() => irAlCircuito(datos.plan_codigo)}>
            Seguir en {datos.plan_etiqueta}
          </Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {datos.grilla.map((p) => {
          const t = tipo(p);
          return (
            <article
              key={p.codigo}
              className={`relative flex flex-col rounded-2xl border bg-card p-5 ${
                t === "mio" ? "border-primary ring-1 ring-primary/40" : ""
              }`}
            >
              <Etiqueta tipo={t} enPrueba={enPrueba} />
              <h2 className="text-base font-bold" style={SYNE}>
                {p.etiqueta}
              </h2>
              <p className="mt-2 text-2xl font-extrabold tabular-nums" style={SYNE}>
                {p.a_convenir ? "A convenir" : pesos(p.precio)}
                {!p.a_convenir && <span className="ml-1 text-xs font-normal text-muted-foreground">/mes</span>}
              </p>
              <p className="mt-1 text-sm font-medium">{p.resumen}</p>
              <p className="mt-2 flex-1 text-sm text-muted-foreground">{p.para_quien}</p>

              <div className="mt-4">
                {t === "convenir" ? (
                  <a
                    href={WA_LINK_ENTERPRISE}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors hover:bg-muted"
                  >
                    Hablemos <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                  </a>
                ) : t === "mio" && !datos.plan_programado ? (
                  <p className="flex items-center justify-center gap-1.5 py-2 text-sm text-muted-foreground">
                    <Check className="h-4 w-4" aria-hidden /> Es el que tenés
                  </p>
                ) : cancelada ? (
                  <p className="py-2 text-center text-sm text-muted-foreground">Reactivá para cambiar</p>
                ) : (
                  <Button className="w-full" variant={t === "sube" ? "default" : "outline"} onClick={() => irAlCircuito(p.codigo)}>
                    {t === "mio"
                      ? `Seguir en ${p.etiqueta}`
                      : enPrueba
                        ? `Elegir ${p.etiqueta}`
                        : t === "sube"
                          ? `Pasar a ${p.etiqueta}`
                          : `Bajar a ${p.etiqueta}`}
                  </Button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function Etiqueta({ tipo, enPrueba }: { tipo: string; enPrueba: boolean }) {
  const texto =
    tipo === "mio" ? "Tu plan" : tipo === "convenir" ? "Personalizado" : enPrueba ? null : tipo === "sube" ? "Mejora" : "Plan inferior";
  if (!texto) return null;
  const clase =
    tipo === "mio"
      ? "bg-primary text-primary-foreground"
      : tipo === "sube"
        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300"
        : "bg-muted text-muted-foreground";
  return (
    <span className={`absolute -top-2.5 left-5 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider ${clase}`}>
      {texto}
    </span>
  );
}

function Regla({ icono, titulo, children }: { icono: React.ReactNode; titulo: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 rounded-2xl border bg-card p-4">
      <span className="mt-0.5 text-muted-foreground">{icono}</span>
      <div>
        <p className="font-semibold">{titulo}</p>
        <p className="text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}
