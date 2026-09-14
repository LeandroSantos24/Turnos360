"use client";

/**
 * PASO 2 — Resumen de la suscripción.
 *
 * Lo que se está por contratar, con el número grande y sin sorpresas, antes de
 * que se toque nada que cobre.
 *
 * QUIÉN DECIDE SI ESTO SE PAGA O NO
 * ─────────────────────────────────
 * El backend. `cambiarPlan` devuelve una `accion` y esta pantalla obedece:
 *
 *   programada / aplicada / cancelada / ninguna  ->  paso 6, no se paga nada
 *   pagar / pagar_transferencia                  ->  paso 3, elegir cómo pagar
 *
 * Para BAJAR de plan se llama al endpoint acá mismo, porque bajar es gratis y
 * el circuito termina en el paso 6. Para SUBIR no se llama: se va derecho al
 * paso 3 y ahí cada medio de pago llama a lo suyo. Si se llamara igual, el
 * backend generaría una preferencia de Mercado Pago que quizás nadie use, y
 * además elegiría el medio de pago por el dueño —que es justo lo que el paso 3
 * viene a devolverle.
 *
 * La comparación por precio para saber si sube o baja es la MISMA que ya hacía
 * la grilla para decidir si el botón dice "Pasar a" o "Bajar a". Si se
 * equivoca, no pasa nada grave: el paso 3 llama a un endpoint que valida, y si
 * `cambiarPlan` contesta que hay que pagar, esta pantalla igual redirige al
 * paso 3. El servidor sigue siendo el que manda.
 */

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowRight, TrendingDown, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cambiarPlan } from "@/lib/empresa-api";
import {
  Cargando,
  PasoLayout,
  SYNE,
  miPrecioActual,
  pesos,
  planDeLaUrl,
  useSuscripcion,
} from "../_suscripcion";

function Resumen() {
  const router = useRouter();
  const params = useSearchParams();
  const codigo = params.get("plan");
  const { datos, cargando } = useSuscripcion();
  const [confirmando, setConfirmando] = useState(false);

  if (cargando || !datos) return <Cargando />;

  const destino = planDeLaUrl(datos, codigo);
  if (!destino) {
    return (
      <PasoLayout paso={1} titulo="Ese plan no existe">
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <p className="text-sm text-muted-foreground">
            El plan que viene en el link no está en la grilla. Volvé y elegilo
            de nuevo.
          </p>
          <Button className="mt-4" onClick={() => router.push("/suscripcion")}>
            Ver los planes
          </Button>
        </section>
      </PasoLayout>
    );
  }

  const miPrecio = miPrecioActual(datos);
  const sube = destino.precio > miPrecio;
  const esElMismo = destino.codigo === datos.plan_codigo;

  async function confirmar() {
    if (!destino) return;

    // Sube: el paso 3 se encarga. Acá no se llama a nada.
    if (sube && !esElMismo) {
      router.push(`/suscripcion/cambiar/pago?plan=${destino.codigo}`);
      return;
    }

    // Baja (o cancela una baja anotada): es gratis y lo resuelve el backend.
    setConfirmando(true);
    try {
      const r = await cambiarPlan(destino.codigo);

      if (r.accion === "pagar" || r.accion === "pagar_transferencia") {
        // No era una baja después de todo. El servidor manda.
        router.push(`/suscripcion/cambiar/pago?plan=${destino.codigo}`);
        return;
      }

      const detalle = encodeURIComponent(r.detalle ?? "Listo.");
      router.push(
        `/suscripcion/cambiar/listo?plan=${destino.codigo}&detalle=${detalle}`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo cambiar el plan");
      setConfirmando(false);
    }
  }

  return (
    <PasoLayout
      paso={1}
      titulo="Revisá el cambio"
      bajada="Esto es lo que vas a tener y lo que vas a pagar. Todavía no se cobró nada."
    >
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        {/* De dónde a dónde. El plan de hoy queda a la izquierda para que el
            cambio se lea como un movimiento y no como un dato suelto. */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl border bg-muted/40 px-3.5 py-2.5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Hoy
            </p>
            <p className="text-sm font-semibold">
              {datos.plan_etiqueta ?? "Sin plan"}
            </p>
          </div>
          <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="rounded-xl border border-primary/40 bg-primary/5 px-3.5 py-2.5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Pasás a
            </p>
            <p className="text-sm font-semibold">{destino.etiqueta}</p>
          </div>
          <span
            className={`ml-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
              sube
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
            }`}
          >
            {sube ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5" />
            )}
            {esElMismo ? "El que ya tenés" : sube ? "Subís de plan" : "Bajás de plan"}
          </span>
        </div>

        {/* El monto, grande. Es el dato por el que la persona entró acá. */}
        <div className="mt-5 rounded-xl border p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {sube ? "Vas a pagar" : "Tu cuota pasa a ser"}
          </p>
          <p className="text-3xl font-bold tabular-nums" style={SYNE}>
            {destino.a_convenir ? "A convenir" : pesos(destino.precio)}
            {!destino.a_convenir && (
              <span className="ml-1.5 text-base font-medium text-muted-foreground">
                por mes
              </span>
            )}
          </p>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {destino.resumen}
          </p>
        </div>

        {/* Qué cambia de verdad: los cupos. Es lo que hace que el número de
            arriba tenga sentido. */}
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border bg-muted/30 p-3.5">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Profesionales
            </dt>
            <dd className="mt-0.5 text-sm font-semibold">
              {destino.profesionales === null
                ? "Sin tope"
                : `Hasta ${destino.profesionales}`}
            </dd>
          </div>
          <div className="rounded-xl border bg-muted/30 p-3.5">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Usuarios
            </dt>
            <dd className="mt-0.5 text-sm font-semibold">
              {destino.usuarios === null ? "Sin tope" : `Hasta ${destino.usuarios}`}
            </dd>
          </div>
          <div className="rounded-xl border bg-muted/30 p-3.5">
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Locales
            </dt>
            <dd className="mt-0.5 text-sm font-semibold">{destino.sucursales}</dd>
          </div>
        </dl>

        {/* BAJAR NO CORTA NADA HOY, y decirlo acá evita el llamado de "me
            bajé y perdí el mes que ya pagué". */}
        {!sube && !esElMismo && (
          <p className="mt-4 rounded-xl border border-amber-400/50 bg-amber-50 p-3.5 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
            El mes que ya pagaste lo usás entero: seguís en{" "}
            <b>{datos.plan_etiqueta}</b>
            {datos.vence ? ` hasta el ${datos.vence}` : ""} y recién ahí pasás a{" "}
            <b>{destino.etiqueta}</b>.
          </p>
        )}

        {/* Cuando ya tiene ese plan, el botón sirve para deshacer una baja
            anotada. Es la forma natural de arrepentirse. */}
        {esElMismo && datos.plan_programado && (
          <p className="mt-4 rounded-xl border bg-muted/40 p-3.5 text-sm text-muted-foreground">
            Tenés anotada una baja a{" "}
            <b>{datos.plan_programado_etiqueta}</b>. Si confirmás acá, la
            cancelás y seguís en {datos.plan_etiqueta}.
          </p>
        )}

        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="outline"
            onClick={() => router.push("/suscripcion")}
            disabled={confirmando}
          >
            Cancelar
          </Button>
          <Button onClick={confirmar} disabled={confirmando || (esElMismo && !datos.plan_programado)}>
            {confirmando
              ? "Un momento…"
              : sube && !esElMismo
                ? "Continuar"
                : "Confirmar"}
          </Button>
        </div>
      </section>
    </PasoLayout>
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
