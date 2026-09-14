"use client";

/**
 * PASO 3 — Cómo querés pagar.
 *
 * Las tres formas juntas y el dueño elige. Antes no elegía: si Mercado Pago
 * estaba configurado, `cambiarPlan` devolvía el link del checkout y la pantalla
 * lo mandaba derecho ahí, aunque la transferencia estuviera disponible y fuera
 * lo que la persona prefería. El que no quería dar la tarjeta se quedaba sin
 * camino.
 *
 * El orden no es casual: el débito automático va primero porque es el que le
 * saca trabajo a los dos lados —ni cobrar ni acordarse de pagar— y es el que
 * queremos que elija. La transferencia queda al final, pero SIEMPRE está.
 *
 * Cada opción llama a lo suyo y sale de acá:
 *   débito       -> activarDebitoAutomatico(plan)  -> checkout de MP
 *   Mercado Pago -> pagarSuscripcionMP(plan)       -> checkout de MP
 *   transferencia-> paso 4, con los datos y el monto
 */

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Banknote, CreditCard, ExternalLink, Repeat } from "lucide-react";

import { Button } from "@/components/ui/button";
import { activarDebitoAutomatico, pagarSuscripcionMP } from "@/lib/empresa-api";
import {
  Cargando,
  PasoLayout,
  SYNE,
  pesos,
  planDeLaUrl,
  useSuscripcion,
} from "../../_suscripcion";

function Opcion({
  icono,
  titulo,
  detalle,
  accion,
  recomendada,
  onClick,
  deshabilitado,
}: {
  icono: React.ReactNode;
  titulo: string;
  detalle: string;
  accion: string;
  recomendada?: boolean;
  onClick: () => void;
  deshabilitado?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={deshabilitado}
      className={`flex w-full items-start gap-3.5 rounded-xl border p-4 text-left transition-colors hover:bg-muted/50 disabled:opacity-60 ${
        recomendada ? "border-primary/40 bg-primary/5" : ""
      }`}
    >
      <span className="mt-0.5 shrink-0 text-muted-foreground">{icono}</span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold">{titulo}</span>
          {recomendada && (
            <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-semibold text-primary">
              La más cómoda
            </span>
          )}
        </span>
        <span className="mt-0.5 block text-sm text-muted-foreground">
          {detalle}
        </span>
      </span>
      <span className="mt-0.5 shrink-0 text-xs font-semibold text-primary">
        {accion}
      </span>
    </button>
  );
}

function ElegirPago() {
  const router = useRouter();
  const params = useSearchParams();
  const codigo = params.get("plan");
  const { datos, cargando } = useSuscripcion();
  const [yendo, setYendo] = useState<string | null>(null);

  if (cargando || !datos) return <Cargando />;

  const destino = planDeLaUrl(datos, codigo);
  const monto = destino?.precio ?? datos.cuota;
  const c = datos.cobro;
  const hayTransferencia = Boolean(c.cbu || c.alias);
  const hayMercadoPago = Boolean(c.mp_checkout || c.mp_link);
  const hayDebito = datos.debito_disponible && !datos.debito;

  async function irAMercadoPago() {
    setYendo("mp");
    try {
      const { url } = await pagarSuscripcionMP(codigo ?? undefined);
      // Misma pestaña: el dueño vuelve solo por las back_urls y así no se
      // pierde entre ventanas en el celular.
      window.location.href = url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo abrir Mercado Pago");
      setYendo(null);
    }
  }

  async function irADebito() {
    if (!codigo) return;
    setYendo("debito");
    try {
      const { url } = await activarDebitoAutomatico(codigo);
      window.location.href = url;
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "No se pudo activar el débito automático",
      );
      setYendo(null);
    }
  }

  return (
    <PasoLayout
      paso={2}
      titulo="¿Cómo querés pagar?"
      bajada={
        destino
          ? `${destino.etiqueta} · ${destino.a_convenir ? "a convenir" : `${pesos(destino.precio)} por mes`}`
          : undefined
      }
    >
      {/* El monto, otra vez y en grande. Es el dato que la persona necesita
          tener a la vista mientras decide, y el que se le pide que transfiera
          exacto dos pantallas más adelante. */}
      {monto !== null && monto !== undefined && (
        <section className="rounded-2xl border border-primary/40 bg-primary/5 p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Total a pagar
          </p>
          <p className="text-2xl font-bold tabular-nums" style={SYNE}>
            {pesos(monto)}
          </p>
        </section>
      )}

      <section className="space-y-2.5 rounded-2xl border bg-card p-5 md:p-6">
        {hayDebito && (
          <Opcion
            icono={<Repeat className="h-5 w-5" />}
            titulo="Débito automático"
            detalle="Se cobra solo todos los meses con tu tarjeta. No tenés que acordarte de nada ni volver a esta pantalla."
            accion={yendo === "debito" ? "Abriendo…" : "Activar"}
            recomendada
            onClick={irADebito}
            deshabilitado={yendo !== null}
          />
        )}

        {hayMercadoPago && (
          <Opcion
            icono={<CreditCard className="h-5 w-5" />}
            titulo="Mercado Pago"
            detalle="Pagás este mes con tarjeta, dinero en cuenta o lo que tengas cargado. Se acredita solo."
            accion={yendo === "mp" ? "Abriendo…" : "Pagar"}
            onClick={irAMercadoPago}
            deshabilitado={yendo !== null}
          />
        )}

        {hayTransferencia && (
          <Opcion
            icono={<Banknote className="h-5 w-5" />}
            titulo="Transferencia bancaria"
            detalle="Te damos el CBU y el alias. Lo confirmamos contra el banco dentro de las 24 horas hábiles."
            accion="Ver datos"
            onClick={() =>
              router.push(
                `/suscripcion/cambiar/transferencia${codigo ? `?plan=${codigo}` : ""}`,
              )
            }
            deshabilitado={yendo !== null}
          />
        )}

        {/* Sin ninguna de las tres no hay nada que ofrecer, y decirlo es mejor
            que mostrar una pantalla vacía. */}
        {!hayDebito && !hayMercadoPago && !hayTransferencia && (
          <p className="text-sm text-muted-foreground">
            Todavía no hay ninguna forma de pago configurada. Escribinos y lo
            resolvemos.
          </p>
        )}

        {/* El link permanente de Mercado Pago, como respaldo. No es una opción
            del circuito: no avisa de qué plan es ni se acredita solo. */}
        {!c.mp_checkout && c.mp_link && (
          <a
            href={c.mp_link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium"
          >
            Abrir el link de pago de siempre
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </section>

      {datos.debito && (
        <p className="text-sm text-muted-foreground">
          Ya tenés el débito automático {datos.debito.etiqueta.toLowerCase()}. Si
          pagás de otra forma, el débito sigue como está.
        </p>
      )}
    </PasoLayout>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Cargando />}>
      <ElegirPago />
    </Suspense>
  );
}
