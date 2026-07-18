"use client";

/**
 * Campañas (/campanas). Automatizaciones del negocio como tarjetas con switch:
 * prender, completar 1-2 campos, guardar. Sin segmentaciones ni complejidad.
 *
 * - Recordatorio 24 h  ·  Recordatorio 2 h (doble recordatorio anti-ausencias)
 * - Cumpleaños con beneficio (X días antes, una vez por año)
 * - Pedido de reseña en Google al finalizar cada turno
 * - Recuperación de clientes inactivos (X días sin venir)
 *
 * Todo sale por EMAIL (el cliente necesita email cargado). Cuando WhatsApp
 * Cloud API esté aprobado (E6), estas mismas campañas se extienden a WA.
 */

import { useEffect, useState } from "react";
import { Megaphone, Bell, Cake, Star, HeartHandshake, Clock, Send } from "lucide-react";
import { toast } from "sonner";

import {
  obtenerAutomatizaciones,
  guardarAutomatizaciones,
  probarCampana,
  type Automatizaciones,
} from "@/lib/empresa-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

function Tarjeta({
  Icono,
  titulo,
  descripcion,
  activa,
  onSwitch,
  tipo,
  children,
}: {
  Icono: typeof Bell;
  titulo: string;
  descripcion: string;
  activa: boolean;
  onSwitch: (v: boolean) => void;
  tipo: string;
  children?: React.ReactNode;
}) {
  const [probando, setProbando] = useState(false);

  async function probar() {
    const destino = window.prompt(
      "¿A qué email te mandamos la muestra?",
      "",
    );
    if (!destino) return;
    setProbando(true);
    try {
      const r = await probarCampana(tipo, destino.trim());
      toast.success(r.detalle);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo enviar la prueba");
    } finally {
      setProbando(false);
    }
  }

  return (
    <div className="rounded-2xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Icono className="h-[18px] w-[18px]" />
          </span>
          <div>
            <p className="font-semibold">{titulo}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">{descripcion}</p>
          </div>
        </div>
        <Switch checked={activa} onCheckedChange={onSwitch} />
      </div>
      {activa && (
        <div className="mt-4 space-y-3 border-t pt-4">
          {children}
          <button
            type="button"
            onClick={probar}
            disabled={probando}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            {probando ? "Enviando…" : "Enviarme una prueba"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function CampanasPage() {
  const [cfg, setCfg] = useState<Automatizaciones | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    obtenerAutomatizaciones()
      .then(setCfg)
      .catch(() => toast.error("No se pudieron cargar las campañas"));
  }, []);

  function set<K extends keyof Automatizaciones>(clave: K, valor: Automatizaciones[K]) {
    setCfg((prev) => (prev ? { ...prev, [clave]: valor } : prev));
  }

  async function guardar() {
    if (!cfg) return;
    if (cfg.resena_google.activa && !cfg.resena_google.link.trim()) {
      toast.error("Pegá el link de tu perfil de Google para pedir reseñas");
      return;
    }
    setGuardando(true);
    try {
      setCfg(await guardarAutomatizaciones(cfg));
      toast.success("Campañas guardadas");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (!cfg) {
    return <p className="p-6 text-sm text-muted-foreground">Cargando…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      <div className="flex items-center gap-2.5">
        <Megaphone className="h-6 w-6 text-primary" />
        <h1 className="font-[family-name:var(--font-syne)] text-2xl font-bold">Campañas</h1>
      </div>
      <p className="-mt-2 text-sm text-muted-foreground">
        Mensajes automáticos por email a tus clientes. Prendé lo que quieras usar
        — el sistema se encarga solo. Probá cada uno con &quot;Enviarme una
        prueba&quot; antes de dejarlo andando.
      </p>
      <div className="rounded-xl border border-amber-300/60 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
        <b>Cumpleaños</b> y <b>recuperar inactivos</b> son promocionales: solo se
        mandan a los clientes que aceptaron recibir promociones (el tilde que
        aparece al reservar). Los recordatorios y la reseña son parte del servicio
        y le llegan a todos.
      </div>

      <Tarjeta
        Icono={Bell}
        titulo="Recordatorio 24 horas antes"
        descripcion="Le recuerda el turno al cliente el día anterior. El clásico anti-ausencias."
        activa={cfg.recordatorio_24h.activa}
        onSwitch={(v) => set("recordatorio_24h", { activa: v })}
        tipo="recordatorio_24h"
      />

      <Tarjeta
        Icono={Clock}
        titulo="Recordatorio 2 horas antes"
        descripcion="El segundo aviso, el mismo día. Juntos forman el doble recordatorio."
        activa={cfg.recordatorio_2h.activa}
        onSwitch={(v) => set("recordatorio_2h", { activa: v })}
        tipo="recordatorio_2h"
      />

      <Tarjeta
        Icono={Cake}
        titulo="Saludo de cumpleaños"
        descripcion="Saluda al cliente antes de su cumpleaños, con el beneficio que definas."
        activa={cfg.cumple.activa}
        onSwitch={(v) => set("cumple", { ...cfg.cumple, activa: v })}
        tipo="cumple"
      >
        <div className="grid gap-3 sm:grid-cols-[140px_1fr]">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Días de anticipación</Label>
            <Input
              type="number"
              min={0}
              max={30}
              value={cfg.cumple.dias_antes}
              onChange={(e) =>
                set("cumple", { ...cfg.cumple, dias_antes: Number(e.target.value) })
              }
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">
              Beneficio / mensaje (lo honrás en el local)
            </Label>
            <Input
              placeholder="20% de descuento en corte durante tu semana de cumple 🎉"
              value={cfg.cumple.mensaje}
              maxLength={500}
              onChange={(e) => set("cumple", { ...cfg.cumple, mensaje: e.target.value })}
            />
          </div>
        </div>
      </Tarjeta>

      <Tarjeta
        Icono={Star}
        titulo="Reseña en Google"
        descripcion="Al finalizar cada turno, le pide al cliente una reseña. Reputación en piloto automático."
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
            Lo sacás de tu Perfil de Empresa en Google → &quot;Pedir reseñas&quot;.
          </p>
        </div>
      </Tarjeta>

      <Tarjeta
        Icono={HeartHandshake}
        titulo="Recuperar clientes inactivos"
        descripcion="Al cliente que lleva X días o más sin venir le llega un «te extrañamos» con tu oferta. Se le avisa una sola vez."
        activa={cfg.inactivos.activa}
        onSwitch={(v) => set("inactivos", { ...cfg.inactivos, activa: v })}
        tipo="inactivos"
      >
        <div className="grid gap-3 sm:grid-cols-[140px_1fr]">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Días sin venir (mínimo 7)</Label>
            <Input
              type="number"
              min={7}
              max={365}
              value={cfg.inactivos.dias}
              onChange={(e) =>
                set("inactivos", { ...cfg.inactivos, dias: Number(e.target.value) })
              }
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Oferta / mensaje (opcional)</Label>
            <Input
              placeholder="Volvé este mes y tenés 15% en cualquier servicio"
              value={cfg.inactivos.mensaje}
              maxLength={500}
              onChange={(e) =>
                set("inactivos", { ...cfg.inactivos, mensaje: e.target.value })
              }
            />
          </div>
        </div>
      </Tarjeta>

      <div className="flex justify-end pt-2">
        <Button onClick={guardar} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar campañas"}
        </Button>
      </div>
    </div>
  );
}
