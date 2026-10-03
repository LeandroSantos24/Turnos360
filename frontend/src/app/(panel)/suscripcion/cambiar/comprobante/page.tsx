"use client";

/**
 * PASO 5 — Informar la transferencia.
 *
 * "Ya transferí", con el número de operación y, si quiere, la captura del
 * comprobante. El pago queda EN REVISIÓN hasta que lo confirmemos contra el
 * banco: acá no se mueve ni el plan ni el vencimiento.
 *
 * Se manda el PLAN que se está comprando, no el monto que corresponde: el
 * monto esperado lo calcula el servidor (precio pactado o de lista). Lo que
 * escribe la persona es solo lo que dice que transfirió, y se compara.
 *
 * Si el equipo pidió un dato («info_solicitada»), esta misma pantalla sirve
 * para responder: muestra el pedido y reenvía el aviso, que vuelve a la
 * bandeja de revisión.
 */

import { Suspense, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Clock, MessageSquareWarning, Paperclip, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfirmar } from "@/components/confirmar";
import { avisarPagoSuscripcion } from "@/lib/empresa-api";
import { subirComprobante } from "@/lib/subidas-api";
import {
  Cargando,
  PasoLayout,
  SYNE,
  montoDe,
  pesos,
  planDeLaUrl,
  useSuscripcion,
} from "../../_suscripcion";

const TIPOS = ["image/jpeg", "image/png", "image/webp"];

function Comprobante() {
  const router = useRouter();
  const params = useSearchParams();
  const codigo = params.get("plan");
  const { datos, avisoPendiente, avisoEstado, mensajeAdmin, cargando } = useSuscripcion();
  const confirmar = useConfirmar();
  const [referencia, setReferencia] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [avisando, setAvisando] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  if (cargando || !datos) return <Cargando />;

  const destino = planDeLaUrl(datos, codigo);
  const respondiendo = avisoEstado === "info_solicitada";
  const monto = respondiendo ? datos.aviso?.monto ?? montoDe(datos, destino) : montoDe(datos, destino);

  function elegir(f: File | null) {
    if (!f) return;
    if (!TIPOS.includes(f.type)) {
      toast.error("Adjuntá una imagen (JPG, PNG o WEBP). Si tenés un PDF, sacale una captura.");
      return;
    }
    setArchivo(f);
  }

  async function avisar() {
    const ok = await confirmar({
      titulo: respondiendo ? "¿Enviar tu respuesta?" : "¿Confirmás que transferiste?",
      descripcion: respondiendo
        ? "Lo volvemos a revisar con lo que nos mandás."
        : `Vamos a buscar en el banco una transferencia de ${pesos(monto)}${
            destino ? ` por el plan ${destino.etiqueta}` : ""
          }. Tu pago queda en revisión hasta que la encontremos.`,
      textoAccion: respondiendo ? "Sí, enviar" : "Sí, ya transferí",
      textoCancelar: "Volver",
    });
    if (!ok) return;

    setAvisando(true);
    try {
      let comprobante: string | null = null;
      if (archivo) comprobante = (await subirComprobante(archivo)).id;
      const r = await avisarPagoSuscripcion({
        monto,
        referencia: referencia.trim() || null,
        plan: respondiendo ? null : codigo,
        comprobante,
      });
      router.push(
        `/suscripcion/cambiar/listo?avisado=1&detalle=${encodeURIComponent(r.detalle)}${
          codigo ? `&plan=${codigo}` : ""
        }`,
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo registrar el aviso");
      setAvisando(false);
    }
  }

  // Ya avisó y lo estamos revisando: avisar de nuevo no suma nada.
  if (avisoPendiente) {
    return (
      <PasoLayout paso={4} titulo="Ya nos avisaste">
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <div className="flex gap-3 rounded-xl border border-sky-500/40 bg-sky-500/10 p-3.5">
            <Clock className="mt-0.5 h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" />
            <div className="text-sm">
              <p className="font-medium">Tu pago está en revisión</p>
              <p className="mt-0.5 text-muted-foreground">
                Lo confirmamos dentro de las próximas 24 horas hábiles y vas a ver el vencimiento
                actualizado. Mientras tanto tu cuenta sigue funcionando normalmente.
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
      titulo={respondiendo ? "Respondé nuestro pedido" : "Avisanos que transferiste"}
      bajada="Con esto lo buscamos en el banco y registramos el pago."
    >
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        {respondiendo && (
          <div className="mb-4 flex gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3.5 text-sm">
            <MessageSquareWarning className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <div>
              <p className="font-medium">Te pedimos:</p>
              <p className="mt-0.5 text-muted-foreground">{mensajeAdmin}</p>
            </div>
          </div>
        )}

        <div className="rounded-xl border p-3.5">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Transferencia de</p>
          <p className="text-2xl font-bold tabular-nums" style={SYNE}>
            {pesos(monto)}
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {respondiendo ? datos.aviso?.plan_etiqueta : destino?.etiqueta ?? datos.plan_etiqueta}
            {" · concepto "}
            {datos.referencia_transferencia}
          </p>
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium" htmlFor="referencia">
            N.º de operación
          </label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Opcional, pero con esto lo encontramos mucho más rápido.
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

        <div className="mt-4">
          <p className="text-sm font-medium">Comprobante</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Opcional. Una captura de la transferencia. Solo la ve el equipo de Turnos360.
          </p>
          <input
            ref={input}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => elegir(e.target.files?.[0] ?? null)}
          />
          {archivo ? (
            <div className="mt-2 flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
              <Paperclip className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">{archivo.name}</span>
              <button type="button" aria-label="Quitar comprobante" onClick={() => setArchivo(null)}>
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
          ) : (
            <Button variant="outline" size="sm" className="mt-2" onClick={() => input.current?.click()}>
              <Paperclip className="mr-1.5 h-4 w-4" />
              Adjuntar imagen
            </Button>
          )}
        </div>

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={() => router.back()} disabled={avisando}>
            Volver
          </Button>
          <Button onClick={avisar} disabled={avisando}>
            {avisando ? "Enviando…" : respondiendo ? "Enviar respuesta" : "Informar pago"}
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
