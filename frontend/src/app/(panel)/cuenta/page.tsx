"use client";

/**
 * Mi cuenta (/cuenta) — por ahora: cambiar la contraseña estando logueado.
 * Pide la actual (para que nadie con la sesión abierta la cambie sin saberla)
 * y la nueva dos veces.
 */

import { useEffect, useState } from "react";
import { Crown, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { etiquetaPlan } from "@/lib/precios";
import { obtenerSuscripcion, type Suscripcion } from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CuentaPage() {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [nueva2, setNueva2] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function manejarSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (nueva.length < 8) {
      toast.error("La contraseña nueva debe tener al menos 8 caracteres");
      return;
    }
    if (nueva !== nueva2) {
      toast.error("Las contraseñas nuevas no coinciden");
      return;
    }
    setGuardando(true);
    try {
      await api.post("/auth/cambiar-password", {
        clave_actual: actual,
        clave_nueva: nueva,
      });
      toast.success("Contraseña actualizada");
      setActual("");
      setNueva("");
      setNueva2("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="w-full space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="titulo-pantalla">
          Mi <b>cuenta</b>.
        </h1>
      </div>

      <TarjetaSuscripcion />

      <div className="rounded-2xl border bg-card p-5">
        <p className="font-semibold">Cambiar contraseña</p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Si te la creó el negocio, acá elegís la tuya.
        </p>
        {/* El formulario NO se estira a los 1200px del contenedor: un campo
            de contraseña de 1150px de ancho se ve absurdo y encima cuesta
            más leerlo. El encabezado se alinea con el del resto del panel,
            que es lo que se nota al navegar; el formulario mantiene su
            ancho de formulario. */}
        <form onSubmit={manejarSubmit} className="mt-4 max-w-md space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="c-actual">Contraseña actual</Label>
            <Input
              id="c-actual"
              type="password"
              required
              value={actual}
              onChange={(e) => setActual(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="c-nueva">Contraseña nueva</Label>
            <Input
              id="c-nueva"
              type="password"
              required
              minLength={8}
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              placeholder="Mínimo 8 caracteres"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="c-nueva2">Repetí la nueva</Label>
            <Input
              id="c-nueva2"
              type="password"
              required
              value={nueva2}
              onChange={(e) => setNueva2(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={guardando}>
            {guardando ? "Guardando…" : "Cambiar contraseña"}
          </Button>
        </form>
      </div>
    </div>
  );
}

/* ── Tarjeta de estado de la suscripción ── */
function TarjetaSuscripcion() {
  const [sus, setSus] = useState<Suscripcion | null>(null);

  useEffect(() => {
    obtenerSuscripcion()
      .then(setSus)
      .catch(() => setSus(null));
  }, []);

  if (!sus) return null;

  // El color sale del TONO que manda el servidor (core/estados_suscripcion.py)
  // y no de una tabla por estado: así un estado nuevo nunca sale sin pintar.
  const TONOS: Record<string, { color: string; bg: string; Icono: typeof Crown }> = {
    info: { color: "#0ea5e9", bg: "#0ea5e915", Icono: Crown },
    ok: { color: "#10b981", bg: "#10b98115", Icono: CheckCircle2 },
    aviso: { color: "#f59e0b", bg: "#f59e0b15", Icono: AlertTriangle },
    error: { color: "#ef4444", bg: "#ef444415", Icono: AlertTriangle },
    neutro: { color: "#6b7280", bg: "#6b728015", Icono: Crown },
  };
  const estilo = { ...(TONOS[sus.tono ?? "neutro"] ?? TONOS.neutro), chip: sus.etiqueta ?? "—" };

  // Antes esto era un ternario con dos casos y un "si no, mostrá el código
  // crudo". Por eso el plan multi aparecía como «multi» en minúscula.
  const nombrePlan = `Plan ${etiquetaPlan(sus.plan)}`;

  return (
    <div
      className="rounded-2xl border p-5"
      style={{ borderColor: `${estilo.color}40`, background: estilo.bg }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
            style={{ background: `${estilo.color}22` }}
          >
            <estilo.Icono className="h-5 w-5" style={{ color: estilo.color }} />
          </div>
          <div>
            <p className="font-semibold leading-tight">{nombrePlan}</p>
            <p className="text-sm" style={{ color: estilo.color }}>
              {sus.mensaje}
            </p>
          </div>
        </div>
        {sus.estado !== "sin_vencimiento" && (
          <span
            className="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold"
            style={{ background: `${estilo.color}22`, color: estilo.color }}
          >
            {estilo.chip}
          </span>
        )}
      </div>

      {(sus.estado_base === "prorroga" || sus.estado_base === "vencida" || sus.estado_base === "prueba_vencida") && sus.estado !== "en_revision" && (
        <p className="mt-3 text-xs text-muted-foreground">
          Para seguir usando Turnos360 sin interrupciones, regularizá tu
          suscripción desde «Mi suscripción».
        </p>
      )}
    </div>
  );
}
