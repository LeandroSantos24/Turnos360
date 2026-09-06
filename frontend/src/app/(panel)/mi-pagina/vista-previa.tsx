"use client";

/**
 * La vista previa en celular del editor de «Mi página».
 *
 * POR QUÉ EXISTE
 * ──────────────
 * El editor era un formulario largo con un link «Abrir» arriba. Para ver el
 * efecto de un cambio había que guardar, cambiar de pestaña, recargar y
 * volver: cuatro pasos por cada ajuste de color. Con ese costo, nadie prueba
 * — se elige el primer color que suena bien y no se toca nunca más.
 *
 * POR QUÉ NO ES UN IFRAME DE LA PÁGINA REAL
 * ─────────────────────────────────────────
 * Porque la página real muestra lo GUARDADO, y acá lo que hay que ver es lo
 * que todavía no se guardó. Un iframe obligaría a guardar en cada tecla para
 * poder previsualizar.
 *
 * Lo que sí se comparte con la página real son los ESTILOS: los dos lados
 * llaman a `estilosDe()` de lib/tema-vidriera. Es lo único que garantiza que
 * la previa no mienta — con dos implementaciones, el día que alguien toque una
 * y no la otra, la previa queda linda y la página de verdad no.
 *
 * Es un RESUMEN, no la página entera: cabecera, dos botones y un servicio.
 * Alcanza para juzgar el look, que es para lo que está.
 */

import { Calendar, MapPin } from "lucide-react";
import { urlDeImagen } from "@/lib/imagenes";

import { estilosDe, conAlfa, formaDelLogo, type TemaVidriera } from "@/lib/tema-vidriera";

export interface DatosPrevia {
  nombre: string;
  descripcion?: string | null;
  direccion?: string | null;
  logo_url?: string | null;
  portada_url?: string | null;
  color_marca?: string | null;
  servicio?: { nombre: string; precio: number | null; duracion_min: number } | null;
}

export function VistaPrevia({
  tema,
  datos,
}: {
  tema: TemaVidriera;
  datos: DatosPrevia;
}) {
  const e = estilosDe(tema, datos.color_marca);
  // La geometría del logo sale del MISMO lugar que la usa la página real
  // (lib/tema-vidriera.ts). Acá estaba calculada a mano —círculo o 18 % de
  // radio— y la página real usaba otra: dos previas de la misma cosa que no
  // coincidían entre sí ni con lo que veía el cliente.
  const geo = formaDelLogo(tema.logo_forma);
  const logoAlto = tema.logo_tamano === "grande" ? 76 : 52;
  const logoAncho = Math.round(logoAlto * geo.aspecto);

  return (
    <div className="sticky top-6">
      {/* Marco de celular. El notch y el borde grueso no son decoración: sin
          ellos el bloque se lee como "otra tarjeta del formulario" y no como
          "así se va a ver en el teléfono de tu cliente". */}
      <div
        className="mx-auto overflow-hidden"
        style={{
          width: 300,
          borderRadius: 38,
          border: "10px solid #14161a",
          boxShadow: "var(--sombra-flotante)",
          background: "#14161a",
        }}
      >
        <div
          className="relative overflow-hidden"
          style={{ height: 560, ...e.fondo, color: e.texto }}
        >
          {/* Notch */}
          <div
            aria-hidden
            className="absolute left-1/2 top-0 z-10 -translate-x-1/2"
            style={{
              width: 96,
              height: 20,
              background: "#14161a",
              borderRadius: "0 0 12px 12px",
            }}
          />

          <div className="h-full overflow-y-auto">
            {/* ── Cabecera ─────────────────────────────────────────── */}
            <div
              className="relative flex flex-col items-center px-5 pb-6 pt-9 text-center"
              style={
                datos.portada_url
                  ? {
                      backgroundImage: `linear-gradient(${conAlfa(
                        e.texto === "#ffffff" ? "#000000" : "#ffffff",
                        0.55,
                      )}, ${conAlfa(e.texto === "#ffffff" ? "#000000" : "#ffffff", 0.8)}), url(${datos.portada_url})`,
                      backgroundSize: "cover",
                      backgroundPosition: "center",
                    }
                  : undefined
              }
            >
              <div
                className="mb-3 flex shrink-0 items-center justify-center overflow-hidden bg-white"
                style={{
                  width: logoAncho,
                  height: logoAlto,
                  borderRadius: geo.radio,
                  boxShadow: `0 6px 18px ${conAlfa(e.texto, 0.18)}`,
                }}
              >
                {datos.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={urlDeImagen(datos.logo_url)}
                    alt=""
                    className="h-full w-full"
                    style={{ objectFit: geo.ajuste }}
                  />
                ) : (
                  <span
                    className="text-xl font-bold"
                    style={{ color: e.acento, fontFamily: e.familiaTitulos }}
                  >
                    {datos.nombre.charAt(0).toUpperCase() || "?"}
                  </span>
                )}
              </div>

              <p
                className="text-[19px] font-bold leading-tight"
                style={{ fontFamily: e.familiaTitulos }}
              >
                {datos.nombre || "Tu negocio"}
              </p>

              {datos.direccion && (
                <p
                  className="mt-1.5 flex items-center gap-1 text-[11px]"
                  style={{ color: e.textoSuave }}
                >
                  <MapPin className="h-3 w-3 shrink-0" />
                  <span className="line-clamp-1">{datos.direccion}</span>
                </p>
              )}

              <div className="mt-4 flex w-full flex-col gap-2">
                <div
                  className="flex items-center justify-center gap-1.5 py-2.5 text-[12.5px] font-semibold"
                  style={e.boton}
                >
                  <Calendar className="h-3.5 w-3.5" />
                  Reservar turno
                </div>
                <div
                  className="py-2.5 text-center text-[12.5px] font-semibold"
                  style={e.botonSecundario}
                >
                  WhatsApp
                </div>
              </div>
            </div>

            {/* ── Descripción ──────────────────────────────────────── */}
            {datos.descripcion && (
              <p
                className="px-5 pb-5 text-center text-[11.5px] leading-relaxed"
                style={{ color: e.textoSuave }}
              >
                {datos.descripcion.slice(0, 140)}
                {datos.descripcion.length > 140 ? "…" : ""}
              </p>
            )}

            {/* ── Un servicio ──────────────────────────────────────── */}
            <div className="px-5 pb-8">
              <p
                className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em]"
                style={{ color: e.textoSuave }}
              >
                Servicios
              </p>
              <p
                className="mb-3 text-[15px] font-bold"
                style={{ fontFamily: e.familiaTitulos }}
              >
                Elegí tu servicio
              </p>
              <div className="flex items-center justify-between p-3" style={e.tarjeta}>
                <div style={{ color: e.tarjeta.background === "#ffffff" ? "#14161a" : e.texto }}>
                  <p className="text-[12.5px] font-semibold">
                    {datos.servicio?.nombre ?? "Corte"}
                  </p>
                  <p className="text-[10.5px] opacity-60">
                    {datos.servicio?.duracion_min ?? 30} min
                  </p>
                </div>
                <p
                  className="text-[13px] font-bold tabular-nums"
                  style={{ color: e.acento }}
                >
                  ${(datos.servicio?.precio ?? 9000).toLocaleString("es-AR")}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className="mt-3 text-center text-xs text-muted-foreground">
        Así la ve tu cliente en el celular
      </p>
    </div>
  );
}
