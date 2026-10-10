"use client";

/**
 * Campañas · Que vuelvan (/campanas/fidelizacion): cumpleaños y clientes inactivos.
 *
 * Son promocionales: solo le llegan a quien aceptó recibir promociones.
 */

import { Cake, HeartHandshake } from "lucide-react";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AvisoPromos, CargandoCampanas, CampoAsunto, Grupo, Opciones, Tarjeta, useCampanas } from "../_campanas";

export default function CampanasFidelizacion() {
  const { cfg, set } = useCampanas();
  if (!cfg) return <CargandoCampanas />;
  return (
    <div className="space-y-6">
      <AvisoPromos />
      {/* ── Fidelización ─────────────────────────────────────────── */}
      <Grupo
        titulo="Que vuelvan"
        tono="var(--acento-rosa)"
        porQue="Recuperar a un cliente que ya te conoce cuesta mucho menos que conseguir uno nuevo. Estas dos hablan con gente que ya te eligió alguna vez."
      >
        <Tarjeta
          Icono={Cake}
          tono="var(--acento-rosa)"
          titulo="Saludo de cumpleaños"
          descripcion="Lo saluda antes de su cumple, con el beneficio que definas. Una excusa para volver, con motivo."
          activa={cfg.cumple.activa}
          onSwitch={(v) => set("cumple", { ...cfg.cumple, activa: v })}
          tipo="cumple"
        >
          <Opciones
            etiqueta="¿Cuántos días antes?"
            valor={cfg.cumple.dias_antes}
            opciones={[0, 1, 3, 7, 15]}
            texto={(d) => (d === 0 ? "El día" : d === 1 ? "1 día" : `${d} días`)}
            onElegir={(d) => set("cumple", { ...cfg.cumple, dias_antes: d })}
            ayuda="Unos días antes funciona mejor que el mismo día: le das tiempo de sacar el turno."
          />
          <CampoAsunto
            valor={cfg.cumple.asunto}
            placeholder="🎂 Te tenemos una sorpresa"
            onCambio={(v) => set("cumple", { ...cfg.cumple, asunto: v })}
          />
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">
              Beneficio (lo honrás vos en el local)
            </Label>
            <Textarea
              rows={2}
              maxLength={500}
              placeholder="20% en cualquier servicio durante tu semana de cumple 🎉"
              value={cfg.cumple.mensaje}
              onChange={(e) => set("cumple", { ...cfg.cumple, mensaje: e.target.value })}
            />
          </div>
        </Tarjeta>

        <Tarjeta
          Icono={HeartHandshake}
          tono="var(--acento-rosa)"
          titulo="Recuperar clientes inactivos"
          descripcion={`Al que lleva ${cfg.inactivos.dias} días o más sin venir le llega un «te extrañamos» con tu oferta. Se le avisa una sola vez.`}
          activa={cfg.inactivos.activa}
          onSwitch={(v) => set("inactivos", { ...cfg.inactivos, activa: v })}
          tipo="inactivos"
        >
          <Opciones
            etiqueta="¿Cuántos días sin venir?"
            valor={cfg.inactivos.dias}
            opciones={[30, 45, 60, 90, 120, 180]}
            texto={(d) => `${d} días`}
            onElegir={(d) => set("inactivos", { ...cfg.inactivos, dias: d })}
            ayuda="Poné un poco más que tu frecuencia normal. Si tus clientes vienen cada mes, 45 días ya es señal de que algo pasó."
          />
          <Opciones
            etiqueta="¿A quién le escribimos?"
            valor={cfg.inactivos.min_visitas}
            opciones={[1, 2, 3, 5]}
            texto={(v) => (v === 1 ? "A todos" : `Con ${v}+ visitas`)}
            onElegir={(v) => set("inactivos", { ...cfg.inactivos, min_visitas: v })}
            ayuda="«Te extrañamos» a alguien que vino una sola vez no es fidelizar: es escribirle a un desconocido. Con 2 o más hablás solo con quien ya había vuelto."
          />
          <CampoAsunto
            valor={cfg.inactivos.asunto}
            placeholder="Hace rato que no te vemos"
            onCambio={(v) => set("inactivos", { ...cfg.inactivos, asunto: v })}
          />
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">
              Oferta para que vuelva (opcional)
            </Label>
            <Textarea
              rows={2}
              maxLength={500}
              placeholder="Volvé este mes y tenés 15% en cualquier servicio"
              value={cfg.inactivos.mensaje}
              onChange={(e) => set("inactivos", { ...cfg.inactivos, mensaje: e.target.value })}
            />
          </div>
        </Tarjeta>
      </Grupo>
    </div>
  );
}
