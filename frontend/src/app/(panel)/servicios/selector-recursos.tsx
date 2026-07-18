"use client";

/**
 * Selector de qué recursos (barberos/profesionales) prestan un servicio.
 * Chips tildables. Es el vínculo que la vidriera necesita para calcular huecos:
 * sin al menos un recurso, el servicio no se puede reservar online.
 */

import { useEffect, useState } from "react";
import { Check } from "lucide-react";

import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { Label } from "@/components/ui/label";

export function SelectorRecursos({
  seleccionados,
  onCambio,
}: {
  seleccionados: number[];
  onCambio: (ids: number[]) => void;
}) {
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    listarRecursos()
      .then((r) => setRecursos(r.items.filter((x) => x.activo)))
      .catch(() => setRecursos([]))
      .finally(() => setCargando(false));
  }, []);

  function toggle(id: number) {
    onCambio(
      seleccionados.includes(id)
        ? seleccionados.filter((x) => x !== id)
        : [...seleccionados, id],
    );
  }

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">¿Quién lo hace?</Label>
      <p className="-mt-1 text-xs text-muted-foreground">
        Marcá los profesionales que prestan este servicio. Es necesario para que
        se pueda reservar online.
      </p>
      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : recursos.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Todavía no hay recursos. Creá los profesionales en la pantalla Recursos.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {recursos.map((r) => {
            const on = seleccionados.includes(r.id);
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => toggle(r.id)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
                  on
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-input text-muted-foreground hover:text-foreground"
                }`}
              >
                {on && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
                {r.nombre}
              </button>
            );
          })}
        </div>
      )}
      {!cargando && recursos.length > 0 && seleccionados.length === 0 && (
        <p className="text-xs font-medium text-orange-600 dark:text-orange-400">
          ⚠ Sin nadie asignado, este servicio no se podrá reservar desde la página.
        </p>
      )}
    </div>
  );
}
