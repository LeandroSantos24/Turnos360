"use client";

/**
 * Campañas · Que no falten (/campanas/recordatorios): los dos recordatorios del turno.
 */

import { Bell, Clock } from "lucide-react";

import { HORAS_RECORDATORIO } from "@/lib/empresa-api";
import { CargandoCampanas, Grupo, Opciones, Tarjeta, textoAnticipacion, useCampanas } from "../_campanas";

export default function CampanasRecordatorios() {
  const { cfg, set } = useCampanas();
  if (!cfg) return <CargandoCampanas />;
  return (
    <div className="space-y-6">
      {/* ── Anti-ausencias ───────────────────────────────────────── */}
      <Grupo
        titulo="Que no falten"
        tono="var(--acento-cielo)"
        porQue="Un turno que se olvida es una hora que no se vende. Con dos avisos automáticos el cliente se acuerda y, si no puede venir, avisa con tiempo."
      >
        <Tarjeta
          Icono={Bell}
          tono="var(--acento-cielo)"
          titulo="Primer recordatorio"
          descripcion={`Le avisa al cliente ${textoAnticipacion(cfg.recordatorio_24h.horas_antes)}. El clásico: llega con tiempo para reprogramar en vez de faltar.`}
          activa={cfg.recordatorio_24h.activa}
          onSwitch={(v) => set("recordatorio_24h", { ...cfg.recordatorio_24h, activa: v })}
          tipo="recordatorio_24h"
        >
          <Opciones
            etiqueta="¿Cuánto antes?"
            valor={cfg.recordatorio_24h.horas_antes}
            opciones={HORAS_RECORDATORIO}
            texto={textoAnticipacion}
            onElegir={(h) => set("recordatorio_24h", { ...cfg.recordatorio_24h, horas_antes: h })}
            ayuda="Si trabajás con turnos del mismo día, 24 horas es demasiado: a esa altura la persona todavía no había reservado."
          />
        </Tarjeta>

        <Tarjeta
          Icono={Clock}
          tono="var(--acento-cielo)"
          titulo="Segundo recordatorio"
          descripcion={`El aviso corto, ${textoAnticipacion(cfg.recordatorio_2h.horas_antes)}. Juntos forman el doble recordatorio.`}
          activa={cfg.recordatorio_2h.activa}
          onSwitch={(v) => set("recordatorio_2h", { ...cfg.recordatorio_2h, activa: v })}
          tipo="recordatorio_2h"
        >
          <Opciones
            etiqueta="¿Cuánto antes?"
            valor={cfg.recordatorio_2h.horas_antes}
            opciones={HORAS_RECORDATORIO}
            texto={textoAnticipacion}
            onElegir={(h) => set("recordatorio_2h", { ...cfg.recordatorio_2h, horas_antes: h })}
            ayuda="Poné una anticipación distinta a la del primero: dos avisos a la misma hora se leen como un error tuyo."
          />
        </Tarjeta>
      </Grupo>
    </div>
  );
}
