"use client";

/**
 * PASO 2 — Resumen del cambio de plan.
 *
 * TODO LO QUE SE MUESTRA LO CALCULA EL SERVIDOR (`GET /empresa/suscripcion/
 * cambio-plan`): cuánto se paga hoy, desde cuándo aplica, el nuevo
 * vencimiento, qué gana, qué pierde y —si baja— qué tiene que reducir. La
 * pantalla no compara precios ni suma días.
 *
 * DOBLE CONFIRMACIÓN: «Continuar» abre el modal «¿Confirmás el cambio de
 * plan?» con el resumen en una línea. Recién al aceptarlo:
 *   · si SUBE  -> paso 3 (elegir cómo pagar). El plan se activa cuando entra
 *                 la plata, nunca antes.
 *   · si BAJA  -> se llama al servidor con `confirmo: true` y queda
 *                 programada para el fin del período pago.
 */

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { AlertTriangle, ArrowRight, Check, Minus, TrendingDown, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useConfirmar } from "@/components/confirmar";
import { cambiarPlan, verCambioPlan, type VistaCambioPlan } from "@/lib/empresa-api";
import { Cargando, PasoLayout, SYNE, fechaLarga, pesos, useSuscripcion } from "../_suscripcion";

function Resumen() {
  const router = useRouter();
  const params = useSearchParams();
  const codigo = params.get("plan");
  const { datos, cargando } = useSuscripcion();
  const confirmar = useConfirmar();
  const [vista, setVista] = useState<VistaCambioPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);

  useEffect(() => {
    if (!codigo) return;
    let vivo = true;
    verCambioPlan(codigo)
      .then((v) => vivo && setVista(v))
      .catch((e) => vivo && setError(e instanceof Error ? e.message : "No se pudo calcular el cambio"));
    return () => {
      vivo = false;
    };
  }, [codigo]);

  if (!codigo || error) {
    return (
      <PasoLayout paso={1} titulo="Ese plan no está disponible">
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <p className="text-sm text-muted-foreground">
            {error ?? "El plan que viene en el link no existe."} Volvé y elegilo de nuevo.
          </p>
          <Button className="mt-4" onClick={() => router.push("/suscripcion")}>
            Ver los planes
          </Button>
        </section>
      </PasoLayout>
    );
  }
  if (cargando || !datos || !vista) return <Cargando />;

  const sube = vista.movimiento === "sube";
  const baja = vista.movimiento === "baja";
  const mismo = vista.movimiento === "mismo";
  const enPrueba = datos.estado === "prueba" || datos.estado === "prueba_vencida";

  async function continuar() {
    if (!vista) return;
    const ok = await confirmar({
      titulo: "¿Confirmás el cambio de plan?",
      descripcion: sube
        ? `Vas a pagar ${pesos(vista.a_pagar_hoy)} y pasás a ${vista.plan_nuevo_etiqueta} apenas se acredite el pago. Tu vencimiento queda el ${fechaLarga(vista.vence_nuevo)}.`
        : baja
          ? vista.inmediato
            ? `Pasás a ${vista.plan_nuevo_etiqueta} ahora. Tu cuota queda en ${pesos(vista.precio_nuevo)} por mes.`
            : `Seguís en ${vista.plan_actual_etiqueta} hasta el ${fechaLarga(vista.aplica_desde)} y desde ese día pasás a ${vista.plan_nuevo_etiqueta} (${pesos(vista.precio_nuevo)} por mes). Hoy no se cobra nada.`
          : `Se cancela la baja a ${datos?.plan_programado_etiqueta} y seguís en ${vista.plan_actual_etiqueta}.`,
      textoAccion: sube ? "Sí, ir a pagar" : "Sí, confirmar el cambio",
      textoCancelar: "Volver",
    });
    if (!ok) return;

    if (sube) {
      router.push(`/suscripcion/cambiar/pago?plan=${vista.plan_nuevo}`);
      return;
    }
    setConfirmando(true);
    try {
      const r = await cambiarPlan(vista.plan_nuevo);
      if (r.accion === "pagar" || r.accion === "pagar_transferencia") {
        router.push(`/suscripcion/cambiar/pago?plan=${vista.plan_nuevo}`);
        return;
      }
      router.push(
        `/suscripcion/cambiar/listo?plan=${vista.plan_nuevo}&detalle=${encodeURIComponent(r.detalle ?? "Listo.")}`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo cambiar el plan");
      setConfirmando(false);
    }
  }

  // Bajar con algo incompatible y sin ciclo pago (se aplicaría ya): el
  // servidor lo rechaza, así que ni se ofrece el botón.
  const bloqueado = baja && vista.inmediato && vista.incompatibilidades.length > 0;

  return (
    <PasoLayout
      paso={1}
      titulo={enPrueba ? "Revisá tu plan" : "Revisá el cambio"}
      bajada="Esto es lo que vas a tener y lo que vas a pagar. Todavía no se cobró nada."
    >
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl border bg-muted/40 px-3.5 py-2.5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Hoy</p>
            <p className="text-sm font-semibold">{enPrueba ? "Prueba" : vista.plan_actual_etiqueta}</p>
          </div>
          <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="rounded-xl border border-primary/40 bg-primary/5 px-3.5 py-2.5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Pasás a</p>
            <p className="text-sm font-semibold">{vista.plan_nuevo_etiqueta}</p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold sm:ml-auto ${
              sube
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                : baja
                  ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            {sube ? <TrendingUp className="h-3.5 w-3.5" /> : baja ? <TrendingDown className="h-3.5 w-3.5" /> : null}
            {mismo ? "El que ya tenés" : sube ? "Subís de plan" : "Bajás de plan"}
          </span>
        </div>

        {/* Los números del cambio */}
        <dl className="mt-5 grid gap-3 sm:grid-cols-2">
          <Celda etiqueta="Pagás hoy" grande>
            {pesos(vista.a_pagar_hoy ?? 0)}
          </Celda>
          <Celda etiqueta="Nueva cuota mensual" grande>
            {pesos(vista.precio_nuevo)}
            {vista.diferencia_mensual !== null && vista.diferencia_mensual !== 0 && !enPrueba && (
              <span className="ml-2 text-sm font-medium text-muted-foreground">
                ({vista.diferencia_mensual > 0 ? "+" : "−"}
                {pesos(Math.abs(vista.diferencia_mensual))}/mes)
              </span>
            )}
          </Celda>
          <Celda etiqueta="Se aplica">
            {vista.inmediato ? "Apenas se acredite el pago" : `El ${fechaLarga(vista.aplica_desde)}`}
          </Celda>
          <Celda etiqueta={sube ? "Nuevo vencimiento" : "Vencimiento"}>
            {fechaLarga(vista.vence_nuevo)}
            {sube && vista.vence_actual && (
              <span className="block text-xs font-normal text-muted-foreground">
                Hoy vence el {fechaLarga(vista.vence_actual)}: se suman 30 días.
              </span>
            )}
          </Celda>
        </dl>

        {/* Ganás / perdés */}
        {(vista.ganas.length > 0 || vista.perdes.length > 0) && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {vista.ganas.length > 0 && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
                  Sumás
                </p>
                <ul className="mt-1.5 space-y-1 text-sm">
                  {vista.ganas.map((g) => (
                    <li key={g} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />{g}</li>
                  ))}
                </ul>
              </div>
            )}
            {vista.perdes.length > 0 && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                  Dejás de tener
                </p>
                <ul className="mt-1.5 space-y-1 text-sm">
                  {vista.perdes.map((g) => (
                    <li key={g} className="flex gap-2"><Minus className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />{g}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Cupos: hoy vs. con el plan nuevo */}
        <div className="mt-4 overflow-hidden rounded-xl border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Cupo</th>
                <th className="px-3 py-2 text-right font-medium">Usás</th>
                <th className="px-3 py-2 text-right font-medium">Plan nuevo</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(["profesionales", "usuarios", "sucursales"] as const).map((k) => {
                const tope = vista.topes_nuevos[k];
                const pasa = tope !== null && vista.uso[k] > tope;
                return (
                  <tr key={k} className={pasa ? "bg-red-500/5" : undefined}>
                    <td className="px-3 py-2">
                      {{ profesionales: "Profesionales", usuarios: "Usuarios con acceso", sucursales: "Sucursales" }[k]}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{vista.uso[k]}</td>
                    <td className={`px-3 py-2 text-right tabular-nums ${pasa ? "font-semibold text-red-700 dark:text-red-400" : ""}`}>
                      {tope === null ? "Sin tope" : tope}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {vista.incompatibilidades.length > 0 && (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/5 p-3.5 text-sm">
            <p className="flex items-center gap-2 font-semibold text-red-700 dark:text-red-400">
              <AlertTriangle className="h-4 w-4" />
              Antes de bajar tenés que reducir esto
            </p>
            <ul className="mt-1.5 space-y-1">
              {vista.incompatibilidades.map((i) => (
                <li key={i.recurso}>{i.mensaje}</li>
              ))}
            </ul>
            <p className="mt-2 text-muted-foreground">
              {vista.inmediato
                ? "Desactivá lo que sobra y volvé a intentar."
                : `La baja se programa igual, pero no se aplica el ${fechaLarga(vista.aplica_desde)} si todavía usás más de lo que permite: seguís en ${vista.plan_actual_etiqueta} hasta que lo reduzcas.`}
            </p>
          </div>
        )}

        {baja && !vista.inmediato && (
          <p className="mt-4 rounded-xl border border-amber-400/50 bg-amber-50 p-3.5 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
            El período que ya pagaste lo usás entero: seguís en <b>{vista.plan_actual_etiqueta}</b> hasta
            el {fechaLarga(vista.aplica_desde)} y recién ahí pasás a <b>{vista.plan_nuevo_etiqueta}</b>.
          </p>
        )}

        {mismo && datos.plan_programado && (
          <p className="mt-4 rounded-xl border bg-muted/40 p-3.5 text-sm text-muted-foreground">
            Tenés anotada una baja a <b>{datos.plan_programado_etiqueta}</b>. Si confirmás, la cancelás
            y seguís en {vista.plan_actual_etiqueta}.
          </p>
        )}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => router.push("/suscripcion")} disabled={confirmando}>
            Cancelar
          </Button>
          <Button
            onClick={continuar}
            disabled={confirmando || bloqueado || (mismo && !datos.plan_programado)}
          >
            {confirmando ? "Un momento…" : "Continuar"}
          </Button>
        </div>
      </section>
    </PasoLayout>
  );
}

function Celda({ etiqueta, grande, children }: { etiqueta: string; grande?: boolean; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border p-3.5">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{etiqueta}</dt>
      <dd className={grande ? "mt-0.5 text-2xl font-bold tabular-nums" : "mt-0.5 text-sm font-semibold"} style={grande ? SYNE : undefined}>
        {children}
      </dd>
    </div>
  );
}

export default function Page() {
  // Suspense porque useSearchParams lo exige para poder prerenderizar.
  return (
    <Suspense fallback={<Cargando />}>
      <Resumen />
    </Suspense>
  );
}
