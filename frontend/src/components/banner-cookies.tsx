"use client";

/**
 * Consentimiento de cookies de la vidriera pública.
 *
 * Aparece SOLO si el negocio conectó un Meta Pixel o un Google Tag. Un negocio
 * sin seguimiento no pone ninguna cookie de terceros, así que un cartel ahí
 * sería un obstáculo entre el cliente y la reserva sin nada que consentir.
 *
 * Los scripts de Meta y Google no se cargan hasta que el visitante acepta: si
 * se cargaran antes, el banner sería decorativo — las cookies ya estarían
 * puestas para cuando aparece.
 *
 * La decisión se guarda en localStorage por slug, no en una cookie. Es la
 * única forma coherente: pedir permiso para poner cookies guardando una cookie
 * es contradictorio, y localStorage para recordar una preferencia del propio
 * sitio entra en "estrictamente necesario".
 */

import { useCallback, useEffect, useState } from "react";

export type Consentimiento = "aceptado" | "rechazado" | null;

const clave = (slug: string) => `t360:cookies:${slug}`;

/** Lee la decisión guardada. null = todavía no eligió. */
export function useConsentimiento(slug: string) {
  // Arranca en undefined (no leído) y no en null: durante el primer render del
  // servidor no hay localStorage, y si arrancara en null el banner
  // parpadearía en pantalla para quien ya había decidido.
  const [valor, setValor] = useState<Consentimiento | undefined>(undefined);

  useEffect(() => {
    try {
      const v = window.localStorage.getItem(clave(slug));
      setValor(v === "aceptado" || v === "rechazado" ? v : null);
    } catch {
      // Modo incógnito con storage bloqueado: se trata como "sin decidir" y
      // no se carga ningún script.
      setValor(null);
    }
  }, [slug]);

  const decidir = useCallback(
    (v: Exclude<Consentimiento, null>) => {
      setValor(v);
      try {
        window.localStorage.setItem(clave(slug), v);
      } catch {
        /* si no se puede guardar, vale para esta visita nada más */
      }
    },
    [slug],
  );

  return { valor, decidir };
}

export function BannerCookies({
  visible,
  acento,
  onAceptar,
  onRechazar,
}: {
  visible: boolean;
  acento: string;
  onAceptar: () => void;
  onRechazar: () => void;
}) {
  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Preferencias de cookies"
      className="fixed inset-x-0 bottom-0 z-50 p-3 md:p-4"
      style={{ pointerEvents: "none" }}
    >
      <div
        className="mx-auto flex max-w-3xl flex-col gap-3 rounded-2xl border bg-white p-4 shadow-lg md:flex-row md:items-center md:gap-4 md:p-5"
        style={{ borderColor: "#e3e7ec", pointerEvents: "auto" }}
      >
        <p className="flex-1 text-sm leading-relaxed" style={{ color: "#3d4453" }}>
          Este negocio usa herramientas de Meta y Google para medir las visitas
          de su página. Si aceptás, se guardan cookies de esos servicios.{" "}
          <span className="whitespace-nowrap">
            Podés reservar tu turno igual si rechazás.
          </span>
        </p>
        <div className="flex shrink-0 gap-2">
          {/* Rechazar va PRIMERO y con el mismo peso visual que aceptar.
              Un "rechazar" escondido o en gris claro es exactamente lo que las
              autoridades europeas vienen sancionando como consentimiento no
              válido, y además es feo con el cliente. */}
          <button
            type="button"
            onClick={onRechazar}
            className="flex-1 rounded-full border px-4 py-2.5 text-sm font-semibold transition-colors hover:bg-[#f4f6f8] md:flex-none"
            style={{ borderColor: "#d7dce4", color: "#1c222c" }}
          >
            Rechazar
          </button>
          <button
            type="button"
            onClick={onAceptar}
            className="flex-1 rounded-full px-5 py-2.5 text-sm font-semibold text-white md:flex-none"
            style={{ background: acento }}
          >
            Aceptar
          </button>
        </div>
      </div>
    </div>
  );
}
