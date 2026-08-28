"use client";

/**
 * Movimientos de la suscripción de una empresa: qué le pasó al vencimiento.
 *
 * Existe por un caso concreto: "Renovar 30 días" y "+10 días" son botones
 * chicos, al lado de otros, y hasta ahora no dejaban ningún rastro. Si se
 * apretaba uno por error, no había forma de enterarse después ni de saber cuál
 * era la fecha anterior — o sea que tampoco había forma de volver atrás.
 *
 * Acá se ve la película completa y se puede deshacer cada movimiento. Deshacer
 * no borra: marca el original como revertido y anota una reversión, así el
 * historial cuenta lo que pasó de verdad.
 */

import { useCallback, useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";

import {
  AjusteSuscripcion,
  historialAjustes,
  revertirAjuste,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";

const TIPO: Record<AjusteSuscripcion["tipo"], { txt: string; cls: string }> = {
  pago: { txt: "Cuota cobrada", cls: "bg-emerald-400/15 text-emerald-600 dark:text-emerald-400" },
  renovacion: { txt: "Renovación manual", cls: "bg-sky-400/15 text-sky-600 dark:text-sky-400" },
  prorroga: { txt: "Prórroga", cls: "bg-amber-400/15 text-amber-600 dark:text-amber-400" },
  manual: { txt: "Fecha a mano", cls: "bg-muted text-muted-foreground" },
  reversion: { txt: "Deshecho", cls: "bg-destructive/10 text-destructive" },
};

function fecha(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function MovimientosSuscripcion({
  empresaId,
  nombre,
  onCambio,
}: {
  empresaId: number;
  nombre: string;
  onCambio?: () => void;
}) {
  const confirmar = useConfirmar();
  const [movs, setMovs] = useState<AjusteSuscripcion[]>([]);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setMovs(await historialAjustes(empresaId));
    } catch {
      // Un historial que no carga no puede romper la pantalla de la empresa.
      setMovs([]);
    } finally {
      setCargando(false);
    }
  }, [empresaId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function deshacer(a: AjusteSuscripcion) {
    if (
      !(await confirmar({
        titulo: "¿Deshacer este movimiento?",
        descripcion:
          `El vencimiento de ${nombre} vuelve al ${fecha(a.vence_antes)}.` +
          (a.tipo === "pago"
            ? " La cuota que se había registrado queda anulada."
            : ""),
        textoAccion: "Sí, deshacer",
        destructivo: true,
      }))
    )
      return;
    try {
      const r = await revertirAjuste(empresaId, a.id);
      toast.success(`Listo · vence ${r.vence ? fecha(r.vence) : "sin fecha"}`);
      cargar();
      onCambio?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo deshacer");
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">Movimientos de la suscripción</h2>
        <p className="text-sm text-muted-foreground">
          Cada vez que se movió el vencimiento, quién lo hizo y cómo volver atrás.
        </p>
      </div>

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando movimientos…</p>
      ) : movs.length === 0 ? (
        <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Todavía no se movió el vencimiento de esta empresa.
        </div>
      ) : (
        <div className="space-y-2">
          {movs.map((a) => {
            const chip = TIPO[a.tipo] ?? TIPO.manual;
            return (
              <div
                key={a.id}
                className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 ${
                  a.revertido ? "bg-muted/40" : "bg-card"
                }`}
              >
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${chip.cls}`}>
                      {chip.txt}
                    </span>
                    <span className="text-sm tabular-nums">
                      {fecha(a.vence_antes)} → {fecha(a.vence_despues)}
                    </span>
                    {a.revertido && (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        deshecho
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {a.detalle ?? "—"} · {fechaHora(a.creado_en)}
                    {a.hecho_por ? ` · ${a.hecho_por}` : ""}
                  </p>
                </div>
                {a.reversible && (
                  <Button variant="outline" size="sm" onClick={() => deshacer(a)}>
                    <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                    Deshacer
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
