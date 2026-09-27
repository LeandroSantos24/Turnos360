import type { Metadata } from "next";
import { notFound } from "next/navigation";

/**
 * SEO de la vidriera. La página es "use client" y trae los datos en el
 * navegador: sin esto, TODAS las vidrieras salían con el <title> y la
 * descripción de la landing de Turnos360, y sin canonical.
 *
 * Corre en el server de Next y le pega al backend por la red interna. El
 * header x-turnos360-ssr hace que el backend no lo cuente como visita.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
const API =
  process.env.API_URL_INTERNA ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

type VidrieraSEO = {
  nombre: string;
  slug: string;
  descripcion: string | null;
  direccion: string | null;
  telefono_publico: string | null;
  logo_url: string | null;
  portada_url: string | null;
  servicios: { nombre: string }[];
};

// "no-existe" = el backend dijo 404 (la página responde 404 de verdad, no un
// 200 vacío que Google indexa como soft-404). null = no se pudo preguntar
// (backend caído): la página se sirve igual y el navegador reintenta.
async function datos(slug: string): Promise<VidrieraSEO | "no-existe" | null> {
  if (!/^[a-z0-9-]{2,80}$/.test(slug)) return "no-existe";
  try {
    const r = await fetch(`${API}/publico/${encodeURIComponent(slug)}`, {
      headers: { "x-turnos360-ssr": "1" },
      next: { revalidate: 300 },
    });
    if (r.status === 404) return "no-existe";
    return r.ok ? ((await r.json()) as VidrieraSEO) : null;
  } catch {
    return null;
  }
}

function absoluta(url: string | null): string | undefined {
  if (!url) return undefined;
  if (/^https?:\/\//.test(url)) return url;
  // Las fotos subidas vienen como /uploads/...: se sirven por la API.
  const api = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  return url.startsWith("/uploads/") && api ? `${api}${url}` : undefined;
}

function descripcionDe(v: VidrieraSEO): string {
  if (v.descripcion?.trim()) return v.descripcion.trim().slice(0, 160);
  const servicios = v.servicios.slice(0, 3).map((s) => s.nombre).join(", ");
  const donde = v.direccion ? ` en ${v.direccion}` : "";
  return `Reservá tu turno online en ${v.nombre}${donde}.${
    servicios ? ` ${servicios}.` : ""
  }`.slice(0, 160);
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const v = await datos(params.slug);
  if (v === "no-existe") {
    return { title: "Página no encontrada · Turnos360", robots: { index: false, follow: false } };
  }
  // Backend sin responder: al menos que no herede el canonical de la home.
  if (!v) return { alternates: { canonical: `/${params.slug}` } };
  const titulo = `${v.nombre} · Reservá tu turno online`;
  const descripcion = descripcionDe(v);
  const imagen = absoluta(v.portada_url) || absoluta(v.logo_url);
  return {
    title: titulo,
    description: descripcion,
    alternates: { canonical: `/${v.slug}` },
    openGraph: {
      type: "website",
      locale: "es_AR",
      url: `/${v.slug}`,
      siteName: v.nombre,
      title: titulo,
      description: descripcion,
      ...(imagen ? { images: [{ url: imagen }] } : {}),
    },
    twitter: {
      card: imagen ? "summary_large_image" : "summary",
      title: titulo,
      description: descripcion,
      ...(imagen ? { images: [imagen] } : {}),
    },
  };
}

export default async function LayoutVidriera({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { slug: string };
}) {
  const r = await datos(params.slug);
  if (r === "no-existe") notFound();
  const v = r;
  const ld = v
    ? {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        name: v.nombre,
        url: `${SITE.replace(/\/$/, "")}/${v.slug}`,
        ...(v.descripcion ? { description: v.descripcion } : {}),
        ...(v.direccion ? { address: v.direccion } : {}),
        ...(v.telefono_publico ? { telephone: v.telefono_publico } : {}),
        ...(absoluta(v.logo_url) ? { image: absoluta(v.logo_url) } : {}),
      }
    : null;
  return (
    <>
      {ld && (
        <script
          type="application/ld+json"
          // El nombre y la descripción los escribe el negocio: se escapa "<"
          // para que un "</script>" no pueda cerrar la etiqueta.
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(ld).replace(/</g, "\\u003c"),
          }}
        />
      )}
      {children}
    </>
  );
}
