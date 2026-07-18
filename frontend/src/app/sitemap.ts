import { MetadataRoute } from "next";

/**
 * sitemap.xml (Next lo sirve en /sitemap.xml).
 *
 * Lista la landing comercial + una URL por vidriera activa (/<slug>), que son
 * el activo SEO real: páginas locales indexables que crecen con cada cliente.
 *
 * Los slugs salen del backend (GET /publico/slugs). Corre en el SERVER de
 * Next, así que usa API_URL_INTERNA (http://backend:8000 dentro de Docker);
 * si el fetch falla (build sin backend, red caída), cae al sitemap mínimo
 * con solo la home: nunca rompe.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://turnos360.com.ar";
const API =
  process.env.API_URL_INTERNA ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

// Se regenera como mucho una vez por hora (alcanza: los slugs cambian poco).
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base: MetadataRoute.Sitemap = [
    { url: SITE, changeFrequency: "weekly", priority: 1 },
  ];

  try {
    const res = await fetch(`${API}/publico/slugs`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return base;
    const slugs: string[] = await res.json();
    return [
      ...base,
      ...slugs.map((slug) => ({
        url: `${SITE}/${slug}`,
        changeFrequency: "daily" as const,
        priority: 0.8,
      })),
    ];
  } catch {
    return base;
  }
}
