import { MetadataRoute } from "next";

import { RUTAS_PRIVADAS } from "@/lib/rutas-privadas.mjs";

/**
 * robots.txt (Next lo sirve en /robots.txt).
 *
 * Abierto: la landing, las vidrieras /<slug>, registro y las legales.
 * Cerrado: el panel, el admin, las vistas de impresión y las pantallas con
 * token en la URL. Cada ruta va dos veces —exacta con `$` y como carpeta—
 * porque Disallow es por PREFIJO: "/caja" a secas también tapaba la vidriera
 * de un negocio con slug "cajaboba".
 *
 * robots.txt NO es seguridad: la protección está en el backend. Las privadas
 * además salen con X-Robots-Tag: noindex (next.config.mjs).
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://turnos360.com.ar";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", ...RUTAS_PRIVADAS.flatMap((r) => [`/${r}$`, `/${r}/`, `/${r}?`])],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
  };
}
