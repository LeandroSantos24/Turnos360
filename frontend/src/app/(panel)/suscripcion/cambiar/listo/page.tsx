"use client";

/**
 * PASO 6 — Listo.
 *
 * El cierre del circuito. Llega desde tres lados distintos y cada uno necesita
 * que le digan una cosa diferente:
 *
 *   · Bajó de plan          -> cuándo se hace efectivo (no es hoy)
 *   · Avisó una transferencia -> que está en proceso y que su cuenta sigue andando
 *   · Volvió de Mercado Pago  -> que el pago se acredita solo
 *
 * El `detalle` viene del servidor por la URL: es el mismo texto que devuelve
 * `cambiarPlan` o `avisarPagoSuscripcion`. Se muestra tal cual y no se
 * reescribe acá, porque el que sabe qué pasó de verdad es el backend.
 */

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, Clock } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Cargando,
  ESTILO_ESTADO,
  PasoLayout,
  SYNE,
  fechaLarga,
  pesos,
  useSuscripcion,
} from "../../_suscripcion";

function Listo() {
  const router = useRouter();
  const params = useSearchParams();
  const detalle = params.get("detalle");
  const avisado = params.get("avisado") === "1";
  const { datos, cargando } = useSuscripcion();

  if (cargando || !datos) return <Cargando />;

  const est = ESTILO_ESTADO[datos.estado] ?? ESTILO_ESTADO.sin_vencimiento;

  return (
    <PasoLayout
      paso={5}
      titulo={avisado ? "Recibimos tu aviso" : "Listo"}
      bajada={
        avisado
          ? "Lo confirmamos contra el banco y te corremos el vencimiento."
          : undefined
      }
    >
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <div className="flex gap-3">
          {avisado ? (
            <Clock className="mt-0.5 h-5 w-5 shrink-0 text-sky-600 dark:text-sky-400" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          )}
          <div className="min-w-0">
            {/* El texto del servidor, tal cual. */}
            <p className="text-sm">
              {detalle ?? "El cambio quedó registrado."}
            </p>
            {avisado && (
              <p className="mt-1.5 text-sm text-muted-foreground">
                Puede demorar unas horas hábiles. Mientras tanto tu cuenta sigue
                funcionando normalmente: para eso están los{" "}
                {datos.dias_prorroga} días de gracia.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* CÓMO QUEDÓ LA SUSCRIPCIÓN, leído del servidor después del cambio.
          No se arma con lo que el circuito creía que iba a pasar: se muestra
          lo que la base dice AHORA. Si algo no se aplicó, se ve acá. */}
      <section className={`rounded-2xl border p-5 md:p-6 ${est.fondo} ${est.borde}`}>
        <p className={`text-xs font-semibold uppercase tracking-wide ${est.texto}`}>
          Tu suscripción
        </p>
        <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p className="text-xl font-bold" style={SYNE}>
            {datos.plan_etiqueta ?? "Sin plan"}
          </p>
          {datos.cuota !== null && (
            <p className="text-sm text-muted-foreground">
              {pesos(datos.cuota)} por mes
            </p>
          )}
        </div>
        {datos.vence && (
          <p className="mt-1.5 text-sm text-muted-foreground">
            Vence el {fechaLarga(datos.vence)}.
          </p>
        )}
        {datos.plan_programado && (
          <p className="mt-1.5 text-sm text-muted-foreground">
            Después pasás a <b>{datos.plan_programado_etiqueta}</b>.
          </p>
        )}
      </section>

      <div className="flex justify-end">
        <Button onClick={() => router.push("/suscripcion")}>
          Volver a mi suscripción
        </Button>
      </div>
    </PasoLayout>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Cargando />}>
      <Listo />
    </Suspense>
  );
}
