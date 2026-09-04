"use client";

/**
 * Bandeja de avisos de pago: los negocios que dijeron "ya te transferí".
 *
 * Un aviso NO es una cuota cobrada. Una transferencia tarda en verse en la
 * cuenta, y dar por pagado lo que alguien dice que pagó convierte el MRR en un
 * número de buena fe. Esto es la lista de lo que hay que ir a buscar al banco.
 *
 * Los pagos por Mercado Pago no aparecen acá: esos los confirma el webhook
 * contra la API de MP, que es una fuente de verdad y no una promesa.
 *
 * POR QUÉ CADA FILA MUESTRA DOS NÚMEROS
 * ─────────────────────────────────────
 * Antes la fila decía solo cuánto avisó el negocio. Para saber si ese monto
 * estaba bien había que acordarse del precio pactado de ESA empresa, que puede
 * no ser el de lista. Confirmar un pago era, en la práctica, confiar en la
 * memoria. Ahora al lado del monto avisado está el esperado, y si coinciden la
 * fila se pinta verde: los que coinciden se confirman de un vistazo y la
 * atención queda libre para los que no, que son los únicos que hay que pensar.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Clock, X } from "lucide-react";
import { toast } from "sonner";

import { AvisoPago, descartarAvisoPago, listarAvisosPago } from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";

function cuando(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

const PESOS = (n: number | null | undefined) =>
  n == null ? "—" : `$${Number(n).toLocaleString("es-AR")}`;

export function AvisosDePago({
  onCobrar,
  /** Se vuelve a pedir la lista cada vez que este número cambia. */
  recargar = 0,
}: {
  /** Abre el diálogo de cobro de esa empresa, con el aviso a la vista. */
  onCobrar?: (empresaId: number, aviso: AvisoPago) => void;
  recargar?: number;
}) {
  const confirmar = useConfirmar();
  const [avisos, setAvisos] = useState<AvisoPago[]>([]);

  const cargar = useCallback(async () => {
    try {
      setAvisos(await listarAvisosPago());
    } catch {
      setAvisos([]);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar, recargar]);

  async function descartar(a: AvisoPago) {
    if (
      !(await confirmar({
        titulo: `¿Descartar el aviso de ${a.empresa_nombre}?`,
        descripcion:
          "Sale de la bandeja SIN registrar ninguna cuota. Usalo cuando el " +
          "pago no aparece en el banco.",
        textoAccion: "Sí, descartar",
        destructivo: true,
      }))
    )
      return;
    try {
      await descartarAvisoPago(a.id);
      toast.success("Aviso descartado");
      cargar();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo descartar");
    }
  }

  if (avisos.length === 0) return null;

  const aRevisar = avisos.filter((a) => !a.coincide).length;

  return (
    <div className="rounded-2xl border border-sky-500/40 bg-sky-500/5 p-4">
      <p className="flex items-center gap-2 font-medium">
        <Clock className="h-4 w-4 text-sky-600 dark:text-sky-400" />
        {avisos.length} {avisos.length === 1 ? "negocio dice" : "negocios dicen"} que
        ya {avisos.length === 1 ? "transfirió" : "transfirieron"}
      </p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Buscá cada uno en el banco y registrá la cuota. Al registrarla, el aviso
        sale solo de esta lista.
        {aRevisar > 0 && (
          <>
            {" "}
            <span className="font-medium text-amber-700 dark:text-amber-400">
              {aRevisar} {aRevisar === 1 ? "no coincide" : "no coinciden"} con lo
              esperado.
            </span>
          </>
        )}
      </p>

      <div className="mt-3 space-y-2">
        {avisos.map((a) => (
          <div
            key={a.id}
            className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background p-3 ${
              a.coincide
                ? "border-emerald-500/40"
                : "border-amber-500/50 bg-amber-500/[0.04]"
            }`}
          >
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {a.empresa_nombre}
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                  {a.plan_etiqueta}
                </span>
              </p>

              {/* Los dos números, uno al lado del otro. Es toda la decisión. */}
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <span>
                  <span className="text-muted-foreground">Avisó</span>{" "}
                  <span className="font-semibold tabular-nums">{PESOS(a.monto)}</span>
                </span>
                <span>
                  <span className="text-muted-foreground">Esperado</span>{" "}
                  <span className="font-semibold tabular-nums">
                    {PESOS(a.monto_esperado)}
                  </span>
                </span>
                {a.coincide ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                    <Check className="h-3 w-3" /> Coincide
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="h-3 w-3" /> Revisar
                  </span>
                )}
              </div>

              <p className="mt-1 text-xs text-muted-foreground">
                {a.metodo} · {cuando(a.creado_en)}
                {a.avisado_por ? ` · avisó ${a.avisado_por}` : ""}
                {a.vence ? ` · vence ${a.vence}` : " · sin vencimiento"}
              </p>
              {a.referencia && (
                <p className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                  Comprobante: {a.referencia}
                </p>
              )}
            </div>

            <div className="flex gap-1.5">
              {onCobrar && (
                <Button size="sm" onClick={() => onCobrar(a.empresa_id, a)}>
                  Registrar cobro
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => descartar(a)}
                title="Descartar sin cobrar"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
