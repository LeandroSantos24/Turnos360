"use client";

/**
 * Equipo (/equipo) — solo el dueño.
 *
 * Para qué existe
 * ---------------
 * El empleado se olvidó la contraseña, está parado en el mostrador, y no
 * tiene email cargado (o tiene uno que no revisa nunca). Hasta ahora eso se
 * resolvía escribiéndole al proveedor y esperando.
 *
 * Acá el dueño lo resuelve solo: genera un link de un solo uso y se lo pasa
 * por WhatsApp. El link vence en 60 minutos y se quema al usarse — nunca
 * aparece una contraseña en texto plano en ningún lado.
 *
 * La pantalla ordena a propósito primero a los que NO pueden recuperar su
 * clave solos: son los únicos que dependen del dueño, y por eso son los que
 * tienen que estar arriba.
 */

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  KeyRound,
  Link2,
  MessageCircle,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  generarLinkRestablecer,
  listarEquipo,
  MiembroEquipo,
  ROL_LABEL,
} from "@/lib/equipo-api";
import { RequiereDueno } from "@/components/requiere-rol";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function ContenidoEquipo() {
  const [miembros, setMiembros] = useState<MiembroEquipo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [generandoPara, setGenerandoPara] = useState<number | null>(null);
  const [link, setLink] = useState<{ url: string; usuario: string } | null>(null);
  const [copiado, setCopiado] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setMiembros(await listarEquipo());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cargar el equipo");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function generar(m: MiembroEquipo) {
    setGenerandoPara(m.id);
    try {
      const datos = await generarLinkRestablecer(m.id);
      setLink({ url: datos.url, usuario: datos.usuario });
      setCopiado(false);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo generar el link",
      );
    } finally {
      setGenerandoPara(null);
    }
  }

  async function copiar() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopiado(true);
      toast.success("Link copiado");
    } catch {
      // Sin permiso de portapapeles (pasa en http:// que no sea localhost).
      // El link está a la vista igual, así que se puede seleccionar a mano.
      toast.error("No pude copiarlo. Seleccionalo y copialo a mano.");
    }
  }

  function mandarPorWhatsApp() {
    if (!link) return;
    // Sin número: abre WhatsApp para que el dueño elija a quién mandárselo.
    // No tenemos el teléfono del empleado (el usuario no guarda teléfono),
    // y pedirlo solo para esto sería agregar un campo a mantener.
    const texto = `Hola ${link.usuario}! Entrá acá para elegir tu contraseña de Turnos360 (el link vence en 1 hora): ${link.url}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(texto)}`, "_blank", "noopener,noreferrer");
  }

  // Primero los que dependen del dueño para poder entrar.
  const ordenados = [...miembros].sort((a, b) => {
    if (a.activo !== b.activo) return a.activo ? -1 : 1;
    if (a.email_recuperable !== b.email_recuperable) {
      return a.email_recuperable ? 1 : -1;
    }
    return a.nombre.localeCompare(b.nombre);
  });

  const sinEmail = miembros.filter((m) => m.activo && !m.email_recuperable).length;

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-6">
      <div className="flex items-center gap-2.5">
        <Users className="h-6 w-6 text-primary" />
        <div>
          <h1 className="font-[family-name:var(--font-syne)] text-2xl font-bold">
            Equipo
          </h1>
          <p className="text-sm text-muted-foreground">
            Quién tiene cuenta en tu negocio y quién necesita que le des una mano
            para entrar.
          </p>
        </div>
      </div>

      {sinEmail > 0 && (
        <div className="flex items-start gap-2.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div className="text-sm">
            <p className="font-semibold text-amber-800 dark:text-amber-400">
              {sinEmail === 1
                ? "1 persona no puede recuperar su contraseña sola"
                : `${sinEmail} personas no pueden recuperar su contraseña solas`}
            </p>
            <p className="mt-0.5 text-muted-foreground">
              No tienen un email válido cargado, así que el link de
              &ldquo;olvidé mi contraseña&rdquo; no les llega a ningún lado. Si
              se olvidan la clave, se la tenés que generar vos desde acá.
            </p>
          </div>
        </div>
      )}

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <div className="space-y-2">
          {ordenados.map((m) => (
            <div
              key={m.id}
              className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 ${
                m.activo ? "bg-card" : "bg-muted/40 opacity-70"
              }`}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{m.nombre}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    {ROL_LABEL[m.rol] ?? m.rol}
                  </span>
                  {!m.activo && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      Inactivo
                    </span>
                  )}
                  {m.recurso && (
                    <span className="text-xs text-muted-foreground">
                      atiende en {m.recurso}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 truncate text-sm text-muted-foreground">
                  {m.email}
                </p>
                {!m.email_recuperable && m.activo && (
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-500">
                    Sin email válido: no puede recuperar su contraseña solo.
                  </p>
                )}
              </div>

              {m.rol !== "dueno" && m.activo && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => generar(m)}
                  disabled={generandoPara === m.id}
                >
                  <KeyRound className="mr-1.5 h-4 w-4" />
                  {generandoPara === m.id ? "Generando…" : "Generar link de contraseña"}
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">
          ¿Cómo agrego o saco gente del equipo?
        </p>
        <p className="mt-1">
          Las altas y bajas de usuarios las hacemos nosotros: escribinos y lo
          resolvemos en el momento. Desde acá podés ver quién tiene cuenta y
          darle una contraseña nueva a quien la haya perdido.
        </p>
      </div>

      {/* ── El link generado ─────────────────────────────────────────── */}
      <Dialog open={link !== null} onOpenChange={(a) => !a && setLink(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-primary" />
              Link para {link?.usuario}
            </DialogTitle>
            <DialogDescription>
              Pasáselo y que elija su contraseña. Vence en 60 minutos y sirve
              una sola vez.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="rounded-xl border bg-muted/50 p-3">
              <p className="break-all font-mono text-xs">{link?.url}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={copiar} className="flex-1">
                {copiado ? (
                  <Check className="mr-1.5 h-4 w-4" />
                ) : (
                  <Copy className="mr-1.5 h-4 w-4" />
                )}
                {copiado ? "Copiado" : "Copiar link"}
              </Button>
              <Button variant="outline" className="flex-1" onClick={mandarPorWhatsApp}>
                <MessageCircle className="mr-1.5 h-4 w-4" />
                Mandar por WhatsApp
              </Button>
            </div>

            <p className="text-xs text-muted-foreground">
              Cuando lo use, todas sus sesiones abiertas se cierran y tiene que
              entrar con la contraseña nueva. Queda registrado que este link lo
              generaste vos.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function EquipoPage() {
  return (
    <RequiereDueno>
      <ContenidoEquipo />
    </RequiereDueno>
  );
}
