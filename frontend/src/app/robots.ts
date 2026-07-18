import { MetadataRoute } from "next";

/**
 * robots.txt (Next lo sirve en /robots.txt).
 *
 * Lo público (landing + vidrieras /<slug>) queda abierto; el panel, el admin
 * y las vistas de impresión se excluyen: son páginas detrás de login que a
 * Google solo le hacen gastar crawl en pantallas vacías.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://turnos360.com.ar";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/admin",
          "/login",
          "/inicio",
          "/agenda",
          "/clientes",
          "/servicios",
          "/recursos",
          "/membresias",
          "/mi-pagina",
          "/mi-dia",
          "/estadisticas",
          "/caja",
          "/metodos-pago",
          "/imprimir",
        ],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
  };
}
