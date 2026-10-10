"use client";

/**
 * Mi cuenta · Seguridad (/cuenta/seguridad).
 *
 * Cambiar la contraseña y sacar de la cuenta a los demás dispositivos.
 *
 * Sobre las sesiones: no hay una lista de «dónde estás conectado» porque los
 * tokens no se guardan en el servidor. Mostrar una lista inventada sería peor
 * que no mostrar nada. Lo que sí funciona —y es lo que importa cuando alguien
 * sospecha que le entraron— es invalidarlas todas de una.
 */

import { useState } from "react";
import Link from "next/link";
import { Check, Eye, EyeOff, Loader2, LogOut, X } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { cambiarPassword, cerrarOtrasSesiones } from "@/lib/auth-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function CampoClave({
  id,
  etiqueta,
  valor,
  onCambio,
  autoComplete,
  describedBy,
}: {
  id: string;
  etiqueta: string;
  valor: string;
  onCambio: (v: string) => void;
  autoComplete: string;
  describedBy?: string;
}) {
  const [ver, setVer] = useState(false);
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{etiqueta}</Label>
      <div className="relative">
        <Input
          id={id}
          type={ver ? "text" : "password"}
          value={valor}
          maxLength={100}
          autoComplete={autoComplete}
          aria-describedby={describedBy}
          onChange={(e) => onCambio(e.target.value)}
          className="pr-10"
        />
        <button
          type="button"
          onClick={() => setVer((v) => !v)}
          aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}
          aria-pressed={ver}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {ver ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function Requisito({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className={`flex items-center gap-1.5 ${ok ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}`}>
      {ok ? <Check className="h-3.5 w-3.5" aria-hidden /> : <X className="h-3.5 w-3.5" aria-hidden />}
      <span>{children}</span>
      <span className="sr-only">{ok ? "(cumplido)" : "(pendiente)"}</span>
    </li>
  );
}

export default function CuentaSeguridad() {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [listo, setListo] = useState<string | null>(null);

  const largo = nueva.length >= 8;
  const distinta = nueva.length > 0 && nueva !== actual;
  const coincide = repetida.length > 0 && nueva === repetida;
  const puede = actual.length > 0 && largo && distinta && coincide;

  async function cambiar(e: React.FormEvent) {
    e.preventDefault();
    if (!puede) return;
    setGuardando(true);
    setListo(null);
    try {
      const detalle = await cambiarPassword(actual, nueva);
      setActual("");
      setNueva("");
      setRepetida("");
      setListo(detalle);
      toast.success("Contraseña actualizada");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="tarjeta p-5 sm:p-6" aria-labelledby="t-clave">
        <h2 id="t-clave" className="font-semibold">Cambiar contraseña</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Si te la creó el negocio, acá elegís la tuya. Al cambiarla se cierra la sesión en tus otros dispositivos; en este seguís adentro.
        </p>
        <form onSubmit={cambiar} className="mt-5 max-w-md space-y-3">
          <CampoClave id="c-actual" etiqueta="Contraseña actual" valor={actual} onCambio={setActual} autoComplete="current-password" />
          <CampoClave id="c-nueva" etiqueta="Contraseña nueva" valor={nueva} onCambio={setNueva} autoComplete="new-password" describedBy="c-requisitos" />
          <CampoClave id="c-repetida" etiqueta="Repetí la nueva" valor={repetida} onCambio={setRepetida} autoComplete="new-password" describedBy="c-requisitos" />
          <ul id="c-requisitos" className="space-y-1 text-xs" aria-live="polite">
            <Requisito ok={largo}>Al menos 8 caracteres</Requisito>
            <Requisito ok={distinta}>Distinta de la actual</Requisito>
            <Requisito ok={coincide}>Las dos nuevas coinciden</Requisito>
          </ul>
          <Button type="submit" className="w-full sm:w-auto" disabled={!puede || guardando}>
            {guardando && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            {guardando ? "Guardando…" : "Cambiar contraseña"}
          </Button>
          {listo && (
            <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
              {listo}
            </p>
          )}
        </form>
        <p className="mt-5 text-sm text-muted-foreground">
          ¿No te acordás de la actual?{" "}
          <Link href="/olvide-password" className="enlace">
            Recuperala por email
          </Link>
          .
        </p>
      </section>

      <CerrarSesiones />
    </div>
  );
}

function CerrarSesiones() {
  const [abierto, setAbierto] = useState(false);
  const [clave, setClave] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    if (!clave) return;
    setEnviando(true);
    try {
      const detalle = await cerrarOtrasSesiones(clave);
      toast.success(detalle);
      setAbierto(false);
      setClave("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudieron cerrar las sesiones");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="tarjeta p-5 sm:p-6" aria-labelledby="t-sesiones">
      <h2 id="t-sesiones" className="font-semibold">Sesiones en otros dispositivos</h2>
      <p className="mt-0.5 text-sm text-muted-foreground">
        ¿Entraste desde una computadora que no es tuya o perdiste el celular? Sacá tu cuenta de todos los demás dispositivos. En este seguís adentro.
      </p>
      <p className="mt-3 text-xs text-muted-foreground">
        Turnos360 no guarda la lista de dispositivos conectados, así que no te la podemos mostrar: lo que sí hacemos es cortarlas todas de una.
      </p>
      <Button type="button" variant="outline" className="mt-4" onClick={() => setAbierto(true)}>
        <LogOut className="mr-1.5 h-4 w-4" />
        Cerrar sesión en los demás dispositivos
      </Button>

      <Dialog open={abierto} onOpenChange={(v) => { setAbierto(v); if (!v) setClave(""); }}>
        <DialogContent>
          <form onSubmit={confirmar} className="space-y-4">
            <DialogHeader>
              <DialogTitle>¿Cerrar las demás sesiones?</DialogTitle>
              <DialogDescription>
                Cualquier otro dispositivo va a tener que volver a entrar con tu contraseña. Para confirmar que sos vos, escribila.
              </DialogDescription>
            </DialogHeader>
            <CampoClave id="s-clave" etiqueta="Tu contraseña" valor={clave} onCambio={setClave} autoComplete="current-password" />
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setAbierto(false)} disabled={enviando}>
                Cancelar
              </Button>
              <Button type="submit" disabled={!clave || enviando}>
                {enviando && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                Cerrar las demás
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}
