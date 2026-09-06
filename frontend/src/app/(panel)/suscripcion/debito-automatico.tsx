"use client";

/**
 * El débito automático, que es la parte que convierte esta pantalla en un
 * «pagás y listo».
 *
 * EL PROBLEMA QUE RESUELVE
 * ────────────────────────
 * Antes, todos los caminos para pagar terminaban en trabajo humano: o el
 * dueño transfería y avisaba, y alguien de Turnos360 iba a buscar el
 * movimiento al banco; o pagaba un link de Mercado Pago, y se tenía que
 * acordar de hacerlo todos los meses. En los dos casos hay un mes en que
 * alguien se olvida, y la primera señal es una agenda apagada.
 *
 * Leandro lo planteó mirando a Netflix y Spotify: «pagás suscripción y
 * listo». Eso es esto: la tarjeta se pone una vez y no se vuelve a pensar en
 * la cuota.
 *
 * POR QUÉ ESTE BLOQUE VA ARRIBA DE «CÓMO PAGAR»
 * ─────────────────────────────────────────────
 * Porque es la opción que queremos que elija, y porque es la que le saca
 * trabajo a él. La transferencia sigue estando —hay negocios que prefieren no
 * dar una tarjeta, y hay que respetarlo— pero abajo, como alternativa.
 *
 * LO QUE ESTE COMPONENTE NUNCA MUESTRA
 * ────────────────────────────────────
 * Nada de la tarjeta. Ni los últimos cuatro dígitos, ni el banco. No los
 * tenemos: la tarjeta vive en Mercado Pago. Para cambiarla se cancela y se
 * vuelve a activar, que son dos clicks y cero datos sensibles de nuestro lado.
 */

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

import {
  activarDebitoAutomatico,
  cancelarDebitoAutomatico,
  type MiSuscripcion,
} from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

function pesos(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toLocaleString("es-AR")}`;
}

function fecha(iso: string | null): string {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}

export function DebitoAutomatico({
  datos,
  onCambio,
}: {
  datos: MiSuscripcion;
  /** Se llama después de cancelar, para recargar la pantalla. */
  onCambio: () => void | Promise<void>;
}) {
  const [yendo, setYendo] = useState(false);
  const [confirmandoBaja, setConfirmandoBaja] = useState(false);
  const [cancelando, setCancelando] = useState(false);

  // Sin token de Mercado Pago en el entorno no hay débito automático. No se
  // muestra un botón que devuelve 503: es peor que no mostrarlo.
  if (!datos.debito_disponible) return null;

  const deb = datos.debito;

  async function activar(plan: string) {
    setYendo(true);
    try {
      const { url } = await activarDebitoAutomatico(plan);
      // Misma pestaña: el dueño vuelve solo por la back_url y así no se pierde
      // entre ventanas en el celular.
      window.location.href = url;
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "No se pudo activar el débito automático",
      );
      setYendo(false);
    }
  }

  async function cancelar() {
    setCancelando(true);
    try {
      await cancelarDebitoAutomatico();
      toast.success("Listo. No te vamos a cobrar más automáticamente.");
      setConfirmandoBaja(false);
      await onCambio();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo cancelar");
    } finally {
      setCancelando(false);
    }
  }

  // ── Ya lo tiene ────────────────────────────────────────────────────────
  if (deb) {
    const fallando = deb.cobros_fallidos > 0;
    const faltaTarjeta = deb.estado === "pending";

    return (
      <section
        className={`rounded-2xl border p-5 md:p-6 ${
          fallando
            ? "border-red-500/40 bg-red-500/5"
            : faltaTarjeta
              ? "border-amber-500/40 bg-amber-500/5"
              : "border-emerald-500/30 bg-emerald-500/5"
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-base font-bold" style={SYNE}>
              {fallando ? (
                <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
              ) : faltaTarjeta ? (
                <CreditCard className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              ) : (
                <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              )}
              {deb.etiqueta}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{deb.detalle}</p>
          </div>

          {deb.monto !== null && (
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Se cobra
              </p>
              <p className="text-2xl font-extrabold tabular-nums" style={SYNE}>
                {pesos(deb.monto)}
              </p>
              <p className="text-xs text-muted-foreground">
                por mes{deb.plan_etiqueta ? ` · plan ${deb.plan_etiqueta}` : ""}
              </p>
            </div>
          )}
        </div>

        {/* EL COBRO QUE REBOTÓ VA ARRIBA DE TODO.
            Mercado Pago reintenta solo, pero puede tardar más que los días de
            gracia. Si la única salida fuera esperar, un negocio con la tarjeta
            vencida se quedaría sin agenda esperando algo que no controla. */}
        {fallando && (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-background p-3.5 text-sm">
            <p className="font-medium">
              El último cobro no se pudo hacer
              {deb.cobros_fallidos > 1 ? ` (van ${deb.cobros_fallidos})` : ""}.
            </p>
            {deb.ultimo_error && (
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                {deb.ultimo_error}
              </p>
            )}
            <p className="mt-2 text-muted-foreground">
              Mercado Pago va a volver a intentarlo por su cuenta. Si querés no
              esperar, podés pagar este mes a mano acá abajo, o cancelar el
              débito y activarlo de nuevo con otra tarjeta.
            </p>
          </div>
        )}

        {faltaTarjeta && (
          <p className="mt-4 rounded-xl border border-amber-500/30 bg-background p-3.5 text-sm text-muted-foreground">
            Te falta terminar de cargar la tarjeta en Mercado Pago. Hasta que
            lo hagas no te cobramos nada — y la suscripción no está activa.
          </p>
        )}

        {!fallando && !faltaTarjeta && deb.proximo_cobro && (
          <p className="mt-4 text-sm">
            El próximo cobro es el <strong>{fecha(deb.proximo_cobro)}</strong>.
            Te va a llegar el aviso de Mercado Pago, como con cualquier
            suscripción.
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirmandoBaja(true)}
          >
            Cancelar el débito automático
          </Button>
          {deb.desde && (
            <span className="text-xs text-muted-foreground">
              Activo desde el {fecha(deb.desde)}
            </span>
          )}
        </div>

        <Dialog
          open={confirmandoBaja}
          onOpenChange={(o) => !o && setConfirmandoBaja(false)}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>¿Cancelamos el débito automático?</DialogTitle>
              {/* Lo primero que quiere saber cualquiera al tocar «cancelar»
                  es si se le apaga algo AHORA. Decirlo antes de que lo
                  pregunte es la diferencia entre cancelar tranquilo y no
                  cancelar por las dudas. */}
              <DialogDescription>
                <b>No perdés nada de lo que ya pagaste.</b> Tu cuenta sigue
                funcionando hasta el{" "}
                <b>{fecha(datos.vence)}</b>, que es el mes que ya está cobrado.
                Lo único que dejamos de hacer es cobrarte solos: desde ahí en
                adelante tenés que pagar vos cada mes.
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setConfirmandoBaja(false)}>
                Dejarlo como está
              </Button>
              <Button
                variant="destructive"
                onClick={cancelar}
                disabled={cancelando}
              >
                {cancelando ? (
                  <>
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Un momento…
                  </>
                ) : (
                  "Sí, cancelar"
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </section>
    );
  }

  // ── Todavía no lo tiene: la oferta ─────────────────────────────────────
  //
  // Qué plan se ofrece: el que ya tiene si está pagando, y el de entrada si
  // está en prueba. Nunca uno más caro que el suyo — un botón que dice
  // "activá el débito" y te sube de plan sin avisar es una trampa.
  const suyo = datos.grilla.find((p) => p.codigo === datos.plan_codigo);
  const aOfrecer =
    suyo && !suyo.a_convenir
      ? suyo
      : datos.grilla.find((p) => !p.a_convenir);

  if (!aOfrecer) return null;

  return (
    <section className="rounded-2xl border border-primary/30 bg-primary/[0.04] p-5 md:p-6">
      <p className="flex items-center gap-2 text-base font-bold" style={SYNE}>
        <RefreshCw className="h-5 w-5" />
        Activá el débito automático
      </p>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Ponés la tarjeta una vez y la cuota se cobra sola todos los meses. No
        tenés que acordarte de nada, ni transferir, ni mandarnos comprobantes.
      </p>

      <ul className="mt-4 space-y-1.5 text-sm">
        <li className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          {/* Es la objeción real, y hay que contestarla antes de que la
              piense: la tarjeta no la guardamos nosotros. */}
          La tarjeta la cargás en Mercado Pago. Nosotros no la vemos ni la
          guardamos.
        </li>
        <li className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          Lo cancelás cuando quieras desde esta misma pantalla, en un click.
        </li>
        <li className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          Si cancelás, seguís usando el mes que ya pagaste.
        </li>
      </ul>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button size="lg" onClick={() => activar(aOfrecer.codigo)} disabled={yendo}>
          {yendo ? (
            <>
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Abriendo Mercado
              Pago…
            </>
          ) : (
            <>
              <CreditCard className="mr-1.5 h-4 w-4" />
              Activar por {pesos(datos.cuota ?? aOfrecer.precio)} por mes
            </>
          )}
        </Button>
        <span className="text-sm text-muted-foreground">
          Plan {aOfrecer.etiqueta}
        </span>
      </div>
    </section>
  );
}
