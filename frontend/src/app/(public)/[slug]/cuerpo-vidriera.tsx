"use client";

/**
 * El cuerpo de la vidriera: todo lo que ve el cliente, sin el wizard, los
 * banners ni el seguimiento.
 *
 * Lo usan la página pública (/<slug>) y la vista previa de «Mi página»
 * (/vista-previa). Una sola implementación es lo que garantiza que la previa
 * no mienta: antes la previa era un resumen dibujado aparte, con otro
 * diseño, y no se parecía a lo que veía el cliente.
 */

import type { Vidriera } from "@/lib/publico-api";
import {
  conAlfa,
  estilosDe,
  formaDelLogo,
  normalizarTema,
  type TemaVidriera,
} from "@/lib/tema-vidriera";
import {
  TopBar,
  Hero,
  Servicios,
  Equipo,
  Galeria,
  Horarios,
  Ubicacion,
  Confianza,
  Contacto,
  FooterVidriera,
  BarraMobile,
  acentoDe,
  TINTA_SUAVE,
  BORDE,
  hexA,
} from "./vidriera-ui";

export function CuerpoVidriera({
  vidriera,
  sucursalId,
  onSucursal,
  onReservar,
  arriba,
  alFinal,
}: {
  vidriera: Vidriera;
  sucursalId: number | null;
  onSucursal: (id: number) => void;
  onReservar: (servicioId?: number) => void;
  arriba?: React.ReactNode;
  alFinal?: React.ReactNode;
}) {
  const acento = acentoDe(vidriera);
  // El look que eligió el negocio en «Mi página». Se resuelve una vez y baja
  // por variables CSS: ver el comentario de TINTA en vidriera-ui.tsx.
  const tema = normalizarTema(vidriera.tema as Partial<TemaVidriera> | undefined);
  const look = estilosDe(tema, vidriera.color_marca);

  return (
    <div
      className="vd-raiz min-h-screen antialiased"
      style={
        {
          // Las variables que consume TODA la vidriera. Definidas acá arriba
          // una sola vez: cualquier componente de adentro —y cualquiera que
          // se agregue después— hereda el look sin recibir nada.
          "--vd-texto": look.texto,
          "--vd-texto-suave": look.textoSuave,
          "--vd-borde": conAlfa(look.texto, 0.12),
          "--vd-superficie": conAlfa(look.texto, 0.05),
          "--vd-tarjeta": look.tarjeta.background as string,
          "--vd-radio": look.radio,
          // La forma del logo, por el mismo canal que los colores. Ver
          // Monograma en vidriera-ui.tsx: antes estaba cableada ahí y no
          // tenía forma de enterarse de lo que el dueño había elegido.
          "--vd-logo-radio": formaDelLogo(tema.logo_forma).radio,
          "--vd-logo-ajuste": formaDelLogo(tema.logo_forma).ajuste,
          color: look.texto,
          fontFamily: undefined,
          ...look.fondo,
        } as React.CSSProperties
      }
    >
      {/* La tipografía de títulos que eligió el negocio. Va en un <style> y no
          en el style del div porque tiene que alcanzar a los h1..h3 que están
          repartidos por todos los componentes hijos. */}
      <style>{`
        .vd-raiz h1, .vd-raiz h2, .vd-raiz h3 { font-family: ${look.familiaTitulos}; }
        .vd-tarjeta { background: var(--vd-tarjeta, #ffffff); }
      `}</style>
      {arriba}
      <TopBar v={vidriera} acento={acento} onReservar={() => onReservar()} />
      <Hero v={vidriera} acento={acento} onReservar={() => onReservar()} />

      {/* Elegir local. Solo con más de uno: el cliente de un negocio de una
          silla no tiene que elegir entre una sola opción. */}
      {vidriera.sucursales.length > 1 && (
        <section className="mx-auto max-w-3xl px-5 pb-2 pt-4">
          <p
            className="mb-2 text-center text-sm font-medium"
            style={{ color: TINTA_SUAVE }}
          >
            ¿A qué local querés ir?
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {vidriera.sucursales.map((suc) => {
              const elegido = suc.id === sucursalId;
              return (
                <button
                  key={suc.id}
                  type="button"
                  onClick={() => onSucursal(suc.id)}
                  className="rounded-2xl border px-4 py-3 text-left transition-colors"
                  style={{
                    borderColor: elegido ? acento : BORDE,
                    background: elegido ? hexA(acento, 0.08) : "transparent",
                  }}
                >
                  <span className="block text-sm font-semibold">{suc.nombre}</span>
                  {suc.direccion && (
                    <span className="block text-xs" style={{ color: TINTA_SUAVE }}>
                      {suc.direccion}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {vidriera.descripcion && (
        <section className="mx-auto max-w-3xl px-5 pb-4 text-center">
          <p
            className="whitespace-pre-line text-base leading-relaxed"
            style={{ color: TINTA_SUAVE }}
          >
            {vidriera.descripcion}
          </p>
        </section>
      )}

      <Servicios v={vidriera} acento={acento} onElegir={(id) => onReservar(id)} />
      <Equipo v={vidriera} acento={acento} />
      <Galeria v={vidriera} acento={acento} />
      <Horarios v={vidriera} acento={acento} />
      <Ubicacion v={vidriera} acento={acento} />
      <Confianza v={vidriera} acento={acento} />
      <Contacto v={vidriera} acento={acento} />
      <FooterVidriera />

      <BarraMobile acento={acento} onReservar={() => onReservar()} />
      {alFinal}
    </div>
  );
}
