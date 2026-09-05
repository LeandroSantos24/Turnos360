"use client";

/**
 * El historial de avisos de transferencia: los que se confirmaron y los que no.
 *
 * POR QUÉ NO ALCANZA CON LA BANDEJA
 * ─────────────────────────────────
 * La bandeja de arriba es una lista de PENDIENTES: lo que hay que ir a buscar
 * al banco. En cuanto un aviso se resuelve —se cobró, o se rechazó— sale de
 * ahí, y hasta ahora salía para siempre: el estado y el motivo quedaban
 * guardados pero no había pantalla que los mostrara. O sea que la función
 * estaba a medias, porque el momento en que hace falta es justo el que no
 * estaba cubierto: el negocio escribe a la semana siguiente diciendo que pagó
 * y hay que poder contestarle qué pasó con ese aviso.
 *
 * Va cerrado por defecto y detrás de un click: es material de consulta, no
 * trabajo pendiente, y compitiendo por atención con la bandeja la haría más
 * difícil de leer.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, ChevronDown, ChevronRight, History } from "lucide-react";

import { AvisoPago, listarAvisosPago } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";

const PESOS = (n: number | null | undefined) =>
  n == null ? "—" : `$${Number(n).toLocaleString("es-AR")}`;

function cuando(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", year: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export function HistorialAvisos({ recargar = 0 }: { recargar?: number }) {
  const [abierto, setAbierto] = useState(false);
  const [avisos, setAvisos] = useState<AvisoPago[]>([]);
  const [cargando, setCargando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      // Se piden TODOS y se filtran los pendientes acá: esos ya están arriba
      // en la bandeja, y repetirlos haría dudar de si son dos cosas distintas.
      const todos = await listarAvisosPago(false);
      setAvisos(todos.filter((a) => a.estado !== "pendiente"));
    } catch {
      setAvisos([]);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    if (abierto) cargar();
  }, [abierto, cargar, recargar]);

  return (
    <div className="rounded-2xl border bg-card">
      <button
        onClick={() => setAbierto((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium hover:bg-muted/40"
      >
        {abierto ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <History className="h-4 w-4 text-muted-foreground" />
        Historial de avisos
        <span className="ml-1 font-normal text-muted-foreground">
          — los que ya se resolvieron
        </span>
      </button>

      {abierto && (
        <div className="border-t px-4 py-3">
          {cargando && (
            <p className="text-sm text-muted-foreground">Cargando…</p>
          )}

          {!cargando && avisos.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Todavía no resolviste ningún aviso.
            </p>
          )}

          {!cargando && avisos.length > 0 && (
            <ul className="divide-y">
              {avisos.map((a) => {
                const ok = a.estado === "confirmada";
                return (
                  <li key={a.id} className="flex flex-wrap items-start justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-sm font-medium">
                        {/* Ícono Y palabra: el estado nunca depende del color. */}
                        {ok ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-700 dark:text-emerald-400">
                            <Check className="h-3 w-3" /> Confirmada
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-xs text-red-700 dark:text-red-400">
                            <AlertTriangle className="h-3 w-3" /> Rechazada
                          </span>
                        )}
                        {a.empresa_nombre}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Avisó {PESOS(a.monto)} · {a.metodo} · {cuando(a.creado_en)}
                        {a.referencia ? ` · ${a.referencia}` : ""}
                      </p>
                      {/* El motivo es LO que se le contesta al que reclama. */}
                      {a.motivo && (
                        <p className="mt-1 text-sm">
                          <span className="text-muted-foreground">Motivo: </span>
                          {a.motivo}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="mt-2 flex justify-end">
            <Button size="sm" variant="ghost" onClick={cargar} disabled={cargando}>
              Actualizar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
