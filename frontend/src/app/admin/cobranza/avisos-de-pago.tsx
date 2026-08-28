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
 */

import { useCallback, useEffect, useState } from "react";
import { Clock, X } from "lucide-react";
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

export function AvisosDePago({
  onCobrar,
}: {
  /** Abre el diálogo de cobro de esa empresa, con el aviso a la vista. */
  onCobrar?: (empresaId: number) => void;
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
  }, [cargar]);

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

  return (
    <div className="rounded-2xl border border-sky-500/40 bg-sky-500/5 p-4">
      <p className="flex items-center gap-2 font-medium">
        <Clock className="h-4 w-4 text-sky-600 dark:text-sky-400" />
        {avisos.length} {avisos.length === 1 ? "negocio dice" : "negocios dicen"} que
        ya {avisos.length === 1 ? "transfirió" : "transfirieron"}
      </p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Buscalos en el banco y registrá la cuota. Al registrarla, el aviso sale
        solo de esta lista.
      </p>
      <div className="mt-3 space-y-2">
        {avisos.map((a) => (
          <div
            key={a.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background p-3"
          >
            <div className="min-w-0">
              <p className="font-medium">{a.empresa_nombre}</p>
              <p className="text-sm text-muted-foreground">
                {a.monto != null
                  ? `$${a.monto.toLocaleString("es-AR")}`
                  : "sin monto"}{" "}
                · {a.metodo} · {cuando(a.creado_en)}
                {a.referencia ? ` · ${a.referencia}` : ""}
              </p>
            </div>
            <div className="flex gap-1.5">
              {onCobrar && (
                <Button size="sm" onClick={() => onCobrar(a.empresa_id)}>
                  Registrar cobro
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => descartar(a)}>
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
