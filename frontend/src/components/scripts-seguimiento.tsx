"use client";

/**
 * Scripts de seguimiento de la vidriera pública (Meta Pixel + Google Tag).
 *
 * Cada negocio conecta SU pixel para medir las visitas y las reservas de SU
 * página en sus propias campañas. Si no cargó ninguno, este componente no
 * renderiza nada y la vidriera no pide un solo byte de más.
 *
 * SEGURIDAD: los IDs se escriben dentro de un <script>. La validación vive en
 * `@/lib/seguimiento` — sin React ni Next adentro, justamente para poder
 * ejecutarla sola contra una lista de venenos (`npm run check:seguimiento`).
 * Cualquier valor que no calce simplemente no se inyecta.
 */

import Script from "next/script";

import { destinoConversion, pixelValido, tagValido } from "@/lib/seguimiento";

export { destinoConversion };

export function ScriptsSeguimiento({
  metaPixelId,
  googleTagId,
  habilitado = true,
}: {
  metaPixelId?: string | null;
  googleTagId?: string | null;
  /**
   * Solo se inyectan los scripts con esto en true. Lo controla el banner de
   * cookies: si cargaran antes de la respuesta del visitante, las cookies de
   * Meta y Google ya estarían puestas para cuando el cartel aparece y el
   * consentimiento sería decorativo.
   */
  habilitado?: boolean;
}) {
  if (!habilitado) return null;
  const metaValido = pixelValido(metaPixelId);
  const googleValido = tagValido(googleTagId);

  if (!metaValido && !googleValido) return null;

  return (
    <>
      {metaValido && (
        <>
          <Script id="meta-pixel" strategy="afterInteractive">
            {`!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init','${metaValido}');fbq('track','PageView');`}
          </Script>
          <noscript>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              height="1"
              width="1"
              style={{ display: "none" }}
              alt=""
              src={`https://www.facebook.com/tr?id=${metaValido}&ev=PageView&noscript=1`}
            />
          </noscript>
        </>
      )}

      {googleValido && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(googleValido)}`}
            strategy="afterInteractive"
          />
          <Script id="google-tag" strategy="afterInteractive">
            {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('js',new Date());gtag('config','${googleValido}');`}
          </Script>
        </>
      )}
    </>
  );
}

/**
 * Dispara el evento de conversión cuando una reserva se confirma.
 *
 * Es el evento que hace útil todo lo demás: sin esto el negocio mide visitas
 * pero no sabe cuáles terminaron en un turno, que es lo único que le importa
 * para decidir si la publicidad le rinde.
 *
 * POR QUÉ SON DOS EVENTOS DE GOOGLE Y NO UNO
 * -------------------------------------------
 * `generate_lead` es un evento recomendado de Google ANALYTICS. Aparece en
 * GA4 y sirve para mirar el embudo, pero **Google ADS no lo cuenta como
 * conversión**. Ads necesita su propio evento con el par completo
 * AW-XXXXXXXXX/etiqueta en el `send_to`.
 *
 * Antes solo se mandaba `generate_lead`. Un negocio que conectaba su tag de
 * Ads veía las visitas subir y las conversiones en CERO, y concluía que la
 * publicidad no le rendía — con un dato falso. Medir mal es peor que no medir.
 *
 * Nunca rompe la reserva: si el script no cargó (bloqueador, sin conexión, el
 * visitante rechazó las cookies), falla en silencio.
 */
export function registrarReservaConfirmada(
  valor?: number | null,
  destino?: string | null,
) {
  try {
    const w = window as unknown as {
      fbq?: (...args: unknown[]) => void;
      gtag?: (...args: unknown[]) => void;
    };
    w.fbq?.("track", "Schedule", {
      value: valor ?? undefined,
      currency: "ARS",
    });
    // Analytics: el embudo.
    w.gtag?.("event", "generate_lead", {
      value: valor ?? undefined,
      currency: "ARS",
    });
    // Ads: la conversión de verdad, solo si el negocio cargó la etiqueta.
    if (destino) {
      w.gtag?.("event", "conversion", {
        send_to: destino,
        value: valor ?? undefined,
        currency: "ARS",
      });
    }
  } catch {
    /* medir nunca puede romper una reserva */
  }
}
