"use client";

/**
 * Vista previa de la página del negocio (/vista-previa), para el editor de
 * «Mi página». Se abre dentro de un iframe del panel.
 *
 * POR QUÉ UN IFRAME CON LA VIDRIERA DE VERDAD
 * ───────────────────────────────────────────
 * La previa anterior era un resumen dibujado aparte: otra cabecera, otros
 * botones, un solo servicio. No se parecía a lo que veía el cliente. Acá se
 * pinta con CuerpoVidriera, el MISMO componente de la página pública, y en un
 * iframe de 390 px: así el diseño de celular es el de un celular de verdad
 * (los breakpoints miran el ancho del iframe, no el de la pantalla del panel).
 *
 * Los datos guardados vienen de /empresa/vidriera-previa (solo dueño; no
 * cuenta visitas ni exige el email confirmado). Lo que todavía no se guardó
 * llega del editor por postMessage y se pone encima.
 *
 * Seguridad del mensaje: solo se acepta del mismo origen y de la ventana que
 * contiene al iframe. Una página de otro sitio que embebiera esta ruta no
 * puede inyectarle nada.
 */

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import { MENSAJE_PREVIA, PREVIA_LISTA } from "@/lib/previa";
import type { Vidriera } from "@/lib/publico-api";
import { CuerpoVidriera } from "../(public)/[slug]/cuerpo-vidriera";

export default function VistaPreviaPage() {
  const [base, setBase] = useState<Vidriera | null>(null);
  const [borrador, setBorrador] = useState<Partial<Vidriera>>({});
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      setError("Entrá al panel para ver la vista previa.");
      return;
    }
    api
      .get<Vidriera>("/empresa/vidriera-previa")
      .then(setBase)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar la vista previa."));
  }, []);

  useEffect(() => {
    function recibir(e: MessageEvent) {
      if (e.origin !== window.location.origin || e.source !== window.parent) return;
      const d = e.data as { tipo?: string; datos?: Partial<Vidriera> } | null;
      if (d?.tipo === MENSAJE_PREVIA && d.datos && typeof d.datos === "object") {
        setBorrador(d.datos);
      }
    }
    window.addEventListener("message", recibir);
    // Avisarle al editor que ya puede mandar lo que no está guardado.
    if (window.parent !== window) window.parent.postMessage({ tipo: PREVIA_LISTA }, window.location.origin);
    return () => window.removeEventListener("message", recibir);
  }, []);

  if (error) {
    return <p className="p-6 text-center text-sm text-muted-foreground">{error}</p>;
  }
  if (!base) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const vidriera: Vidriera = { ...base, ...borrador };

  return (
    <CuerpoVidriera
      vidriera={vidriera}
      sucursalId={vidriera.sucursales.length === 1 ? vidriera.sucursales[0].id : null}
      onSucursal={() => {}}
      onReservar={() => {
        setAviso(true);
        setTimeout(() => setAviso(false), 2500);
      }}
      alFinal={
        aviso && (
          <div
            role="status"
            className="fixed inset-x-4 bottom-24 z-[70] rounded-xl bg-black/85 px-4 py-3 text-center text-sm text-white"
          >
            Es la vista previa: acá tus clientes eligen el turno.
          </div>
        )
      }
    />
  );
}
