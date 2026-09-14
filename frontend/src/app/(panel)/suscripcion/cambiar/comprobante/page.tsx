"use client";

/**
 * PASO 5 — El comprobante.
 *
 * "Ya transferí", con el número de operación si lo tiene a mano.
 *
 * EL MONTO QUE SE AVISA ES EL DEL PLAN QUE SE ESTÁ COMPRANDO, no el de la
 * cuota que la empresa paga hoy. Si alguien pasa de la prueba a Pro, avisa por
 * Pro. Sin esto, el aviso llegaba al panel de cobranza con el número
 * equivocado y la comparación «avisado vs esperado» marcaba diferencia en
 * todas las altas: cada una había que revisarla a mano contra el banco.
 */

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Clock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { avisarPagoSuscripcion } from "@/lib/empresa-api";
import {
  Cargando,
  PasoLayout,
  SYNE,
  pesos,
  planDeLaUrl,
  useSuscripcion,
} from "../../_suscripcion";

function Comprobante() {
  const router = useRouter();
  const params = useSearchParams();
  const codigo = params.get("plan");
  const { datos, avisoPendiente, cargando } = useSuscripcion();
  const [referencia, setReferencia] = useState("");
  const [avisando, setAvisando] = useState(false);

  if (cargando || !datos) return <Cargando />;

  const destino = planDeLaUrl(datos, codigo);
  const monto = destino?.precio ?? datos.cuota;

  async function avisar() {
    setAvisando(true);
    try {
      const r = await avisarPagoSuscripcion({
        monto,
        referencia: referencia.trim() || null,
      });
      const detalle = encodeURIComponent(r.detalle);
      router.push(
        `/suscripcion/cambiar/listo?avisado=1&detalle=${detalle}${
          codigo ? `&plan=${codigo}` : ""
        }`,
      );
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "No se pudo registrar el aviso",
      );
      setAvisando(false);
    }
  }

  // Ya avisó antes y todavía no lo confirmamos: no tiene sentido pedirle que
  // avise de nuevo, porque duplicaría el aviso en el panel de cobranza.
  if (avisoPendiente) {
    return (
      <PasoLayout paso={4} titulo="Ya nos avisaste">
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <div className="flex gap-3 rounded-xl border border-sky-500/40 bg-sky-500/10 p-3.5">
            <Clock className="mt-0.5 h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" />
            <div className="text-sm">
              <p className="font-medium">Tu pago está en proceso</p>
              <p className="mt-0.5 text-muted-foreground">
                Lo confirmamos dentro de las próximas 24 horas hábiles y vas a
                ver el vencimiento actualizado. Mientras tanto tu cuenta sigue
                funcionando normalmente.
              </p>
            </div>
          </div>
          <Button className="mt-4" onClick={() => router.push("/suscripcion")}>
            Volver a mi suscripción
          </Button>
        </section>
      </PasoLayout>
    );
  }

  return (
    <PasoLayout
      paso={4}
      titulo="Avisanos que transferiste"
      bajada="Con esto lo buscamos en el banco y registramos el pago."
    >
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <div className="rounded-xl border p-3.5">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Estás avisando por
          </p>
          <p className="text-2xl font-bold tabular-nums" style={SYNE}>
            {pesos(monto)}
          </p>
          {destino && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              {destino.etiqueta}
            </p>
          )}
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium" htmlFor="referencia">
            N.º de operación
          </label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Opcional, pero con esto lo encontramos mucho más rápido. Lo saca tu
            banco al terminar la transferencia.
          </p>
          <Input
            id="referencia"
            className="mt-2"
            placeholder="Por ejemplo: 000123456789"
            value={referencia}
            onChange={(e) => setReferencia(e.target.value)}
            maxLength={300}
          />
        </div>

        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="outline"
            onClick={() => router.back()}
            disabled={avisando}
          >
            Volver a los datos
          </Button>
          <Button onClick={avisar} disabled={avisando}>
            {avisando ? "Avisando…" : "Confirmar que transferí"}
          </Button>
        </div>
      </section>
    </PasoLayout>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Cargando />}>
      <Comprobante />
    </Suspense>
  );
}
