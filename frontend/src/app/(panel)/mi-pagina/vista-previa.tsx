"use client";

/**
 * La vista previa en celular del editor de «Mi página».
 *
 * POR QUÉ EXISTE
 * ──────────────
 * Para ver el efecto de un cambio había que guardar, cambiar de pestaña,
 * recargar y volver. Con ese costo nadie prueba nada.
 *
 * CÓMO ES AHORA
 * ─────────────
 * Antes era un resumen dibujado aparte (cabecera, dos botones y un servicio)
 * que no se parecía a la página real. Ahora es la página real: un iframe de
 * 390 px con /vista-previa, que pinta con el mismo componente que ve el
 * cliente. Lo que todavía no se guardó se le manda por postMessage en cada
 * cambio, así que se sigue viendo «en vivo», sin guardar.
 */

import { useCallback, useEffect, useRef } from "react";

import { MENSAJE_PREVIA, PREVIA_LISTA } from "@/lib/previa";
import type { Vidriera } from "@/lib/publico-api";

/** Ancho real de un celular: los breakpoints de la página miran este ancho. */
const ANCHO = 390;
const ALTO = 780;
/** Ancho del marco en el panel. El iframe se achica con transform. */
const MARCO = 300;
const ESCALA = MARCO / ANCHO;

export function VistaPrevia({ datos }: { datos: Partial<Vidriera> }) {
  const iframe = useRef<HTMLIFrameElement>(null);

  const enviar = useCallback(() => {
    iframe.current?.contentWindow?.postMessage(
      { tipo: MENSAJE_PREVIA, datos },
      window.location.origin,
    );
  }, [datos]);

  // Cada cambio del formulario, con un respiro corto para no mandar un
  // mensaje por tecla.
  useEffect(() => {
    const t = setTimeout(enviar, 120);
    return () => clearTimeout(t);
  }, [enviar]);

  // Cuando la previa termina de cargar, avisa; recién ahí se le manda el
  // borrador (antes no tendría quién lo escuche).
  useEffect(() => {
    function recibir(e: MessageEvent) {
      if (e.origin !== window.location.origin || e.source !== iframe.current?.contentWindow) return;
      if ((e.data as { tipo?: string } | null)?.tipo === PREVIA_LISTA) enviar();
    }
    window.addEventListener("message", recibir);
    return () => window.removeEventListener("message", recibir);
  }, [enviar]);

  return (
    <div className="sticky top-6">
      {/* Marco de celular. El notch y el borde grueso no son decoración: sin
          ellos el bloque se lee como "otra tarjeta del formulario" y no como
          "así se va a ver en el teléfono de tu cliente". */}
      <div
        className="relative mx-auto overflow-hidden"
        style={{
          width: MARCO + 20,
          borderRadius: 38,
          border: "10px solid #14161a",
          boxShadow: "var(--sombra-flotante)",
          background: "#14161a",
        }}
      >
        <div
          aria-hidden
          className="absolute left-1/2 top-0 z-10 -translate-x-1/2"
          style={{ width: 96, height: 20, background: "#14161a", borderRadius: "0 0 12px 12px" }}
        />
        <div className="overflow-hidden bg-white" style={{ width: MARCO, height: ALTO * ESCALA }}>
          <iframe
            ref={iframe}
            src="/vista-previa"
            title="Vista previa de tu página en un celular"
            style={{
              width: ANCHO,
              height: ALTO,
              border: 0,
              transform: `scale(${ESCALA})`,
              transformOrigin: "0 0",
            }}
          />
        </div>
      </div>

      <p className="mt-3 text-center text-xs text-muted-foreground">
        Así la ve tu cliente en el celular. Los cambios se ven acá antes de publicarlos.
      </p>
    </div>
  );
}
