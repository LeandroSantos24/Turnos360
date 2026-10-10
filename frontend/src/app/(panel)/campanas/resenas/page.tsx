"use client";

/**
 * Campañas · Reseñas (/campanas/resenas): pedido de reseña en Google después del turno.
 */

import { Star } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CargandoCampanas, Grupo, Opciones, Tarjeta, useCampanas } from "../_campanas";

export default function CampanasResenas() {
  const { cfg, set } = useCampanas();
  if (!cfg) return <CargandoCampanas />;
  return (
    <div className="space-y-6">
      {/* ── Reputación ───────────────────────────────────────────── */}
      <Grupo
        titulo="Que te encuentren"
        tono="var(--acento-ambar)"
        porQue="Las reseñas de Google son lo que decide si alguien que no te conoce entra o sigue de largo. Pedirlas a mano no escala; así salen solas."
      >
        <Tarjeta
          Icono={Star}
          tono="var(--acento-ambar)"
          titulo="Reseña en Google"
          descripcion="Después de cada turno le pide al cliente una reseña. Reputación en piloto automático."
          activa={cfg.resena_google.activa}
          onSwitch={(v) => set("resena_google", { ...cfg.resena_google, activa: v })}
          tipo="resena_google"
        >
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">
              Link para reseñar tu negocio en Google
            </Label>
            <Input
              placeholder="https://g.page/r/…/review"
              value={cfg.resena_google.link}
              maxLength={300}
              onChange={(e) =>
                set("resena_google", { ...cfg.resena_google, link: e.target.value })
              }
            />
            <p className="text-xs text-muted-foreground">
              Lo sacás de tu Perfil de Empresa en Google → «Pedir reseñas».
            </p>
          </div>
          <Opciones
            etiqueta="¿Cuánto después del turno?"
            valor={cfg.resena_google.horas_despues}
            opciones={[0, 2, 4, 24, 48]}
            texto={(h) =>
              h === 0 ? "Al toque" : h >= 24 ? `${h / 24} día${h > 24 ? "s" : ""}` : `${h} h`
            }
            onElegir={(h) =>
              set("resena_google", { ...cfg.resena_google, horas_despues: h })
            }
            ayuda="Al toque es el peor momento: la persona está pagando y saliendo. Unas horas después ya está en su casa y el buen rato es un recuerdo."
          />
          {!cfg.resena_google.link.trim() && (
            <p className="rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
              Sin el link, la campaña queda prendida pero no puede mandar
              nada.
            </p>
          )}
        </Tarjeta>
      </Grupo>
    </div>
  );
}
