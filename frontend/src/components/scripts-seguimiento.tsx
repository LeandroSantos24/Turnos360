"use client";

/**
 * Scripts de seguimiento de la vidriera pública (Meta Pixel + Google Tag).
 *
 * Cada negocio conecta SU pixel para medir las visitas y las reservas de SU
 * página en sus propias campañas. Si no cargó ninguno, este componente no
 * renderiza nada y la vidriera no pide un solo byte de más.
 *
 * SEGURIDAD: los IDs se escriben dentro de un <script>. El backend ya los
 * valida contra una lista blanca cerrada (solo dígitos para Meta, formato
 * G-/AW- para Google), pero acá se vuelve a chequear: cualquier ID que no
 * calce simplemente no se inyecta. Es la clase de dato donde conviene
 * desconfiar en las dos puntas, porque un ID mal formado dentro de un script
 * es XSS en la página donde los clientes dejan su teléfono.
 */

import Script from "next/script";

const META_OK = /^\d{6,20}$/;
const GOOGLE_OK = /^(G|AW|GT|UA)-[A-Z0-9-]{4,30}$/i;

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
  const meta = (metaPixelId ?? "").trim();
  const google = (googleTagId ?? "").trim();
  const metaValido = META_OK.test(meta) ? meta : null;
  const googleValido = GOOGLE_OK.test(google) ? google : null;

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
 * Nunca rompe la reserva: si el script no cargó (bloqueador, sin conexión),
 * falla en silencio.
 */
export function registrarReservaConfirmada(valor?: number | null) {
  try {
    const w = window as unknown as {
      fbq?: (...args: unknown[]) => void;
      gtag?: (...args: unknown[]) => void;
    };
    w.fbq?.("track", "Schedule", {
      value: valor ?? undefined,
      currency: "ARS",
    });
    w.gtag?.("event", "generate_lead", {
      value: valor ?? undefined,
      currency: "ARS",
    });
  } catch {
    /* medir nunca puede romper una reserva */
  }
}
