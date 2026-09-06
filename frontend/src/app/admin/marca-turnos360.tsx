"use client";

/**
 * El logo de Turnos360, cambiable sin desplegar.
 *
 * PARA QUÉ. Lo pidió Leandro: «en Navidad le pongo un gorrito, en Pascua le
 * pongo huevos». Hoy eso es reemplazar un archivo del repo y desplegar, que
 * para un chiste de una semana no lo hace nadie.
 *
 * EL ARCHIVO DEL REPO NO SE VA. La URL lo PISA; vaciar el campo vuelve al de
 * siempre. Esa vuelta atrás tiene que ser tan fácil como ponerlo, o el
 * gorrito se queda hasta marzo.
 *
 * La previa de abajo NO es decorativa: es lo único que separa «pegué el link
 * y quedó lindo» de «pegué el link, se rompió, y me entero cuando alguien
 * entra a la landing». Muestra la imagen de verdad, en los dos tamaños en que
 * se usa, y avisa si no carga.
 */

import { useCallback, useEffect, useState } from "react";
import { Check, ImageIcon, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { guardarMarca, leerMarca } from "@/lib/admin-api";
import { LOGO_LOCAL } from "@/lib/marca";

const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

export function MarcaTurnos360() {
  const [url, setUrl] = useState("");
  const [guardado, setGuardado] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [roto, setRoto] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const r = await leerMarca();
      setUrl(r.logo_url ?? "");
      setGuardado(r.logo_url ?? "");
    } catch {
      // Que no cargue no puede romper el panel de empresas, que es lo que
      // la persona vino a hacer.
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function guardar() {
    setGuardando(true);
    try {
      const r = await guardarMarca(url.trim() || null);
      setGuardado(r.logo_url ?? "");
      setUrl(r.logo_url ?? "");
      setRoto(false);
      toast.success(
        r.logo_url
          ? "Logo actualizado. Recargá la landing para verlo."
          : "Volvimos al logo de siempre.",
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) return null;

  const hayCambio = url.trim() !== guardado;
  // Lo que se está por ver: lo escrito si hay algo, y si no el del repo.
  const previa = url.trim() || LOGO_LOCAL;

  return (
    <div className="mb-6 rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-sm font-semibold" style={SYNE}>
            <ImageIcon className="h-4 w-4" />
            Logo de Turnos360
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Pegá un link (Cloudinary, o donde lo tengas) para cambiarlo sin
            desplegar. Vacío = el logo de siempre.
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Input
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setRoto(false);
              }}
              placeholder="https://res.cloudinary.com/…/logo-navidad.png"
              className="min-w-[260px] flex-1 font-mono text-xs"
              maxLength={500}
            />
            <Button size="sm" onClick={guardar} disabled={guardando || !hayCambio}>
              {guardando ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> Guardando…
                </>
              ) : hayCambio ? (
                "Guardar"
              ) : (
                <>
                  <Check className="mr-1.5 h-3.5 w-3.5" /> Guardado
                </>
              )}
            </Button>
            {guardado && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setUrl("")}
                disabled={guardando || !url}
              >
                Volver al de siempre
              </Button>
            )}
          </div>

          {roto && (
            <p className="mt-2 text-xs font-medium text-red-600 dark:text-red-400">
              Esa imagen no carga. Si la guardás igual, la landing va a mostrar
              el logo de siempre — pero revisá el link antes.
            </p>
          )}
        </div>

        {/* Los DOS tamaños en que se usa. Un logo con mucho detalle se ve bien
            en la landing (44px) y se convierte en una mancha en el sidebar
            (28px): si solo mostráramos el grande, eso se descubre después. */}
        <div className="flex shrink-0 items-end gap-4 rounded-xl border bg-muted/30 p-3">
          {[44, 28].map((lado) => (
            <div key={lado} className="text-center">
              <div
                className="flex items-center justify-center rounded-lg bg-white p-0.5"
                style={{ width: lado, height: lado }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previa}
                  alt=""
                  className="h-full w-full object-contain"
                  onError={() => setRoto(true)}
                />
              </div>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {lado === 44 ? "landing" : "panel"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
