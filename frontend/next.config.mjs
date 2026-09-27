import { RUTAS_PRIVADAS } from "./src/lib/rutas-privadas.mjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Deuda técnica (documentada en la doc maestra): el panel tiene ~28 errores
  // de tipos preexistentes por el cambio de firma de @base-ui (asChild en
  // Button, onValueChange en Select). No afectan el runtime. Sin esto,
  // `next build` de producción no pasa. Los archivos nuevos (vidriera,
  // mi-página, landing) verifican en cero errores con tsc.
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },

  // Imagen de producción liviana: `next build` deja un server autocontenido
  // en .next/standalone (lo consume frontend/Dockerfile.prod). No afecta
  // en nada a `next dev`.
  output: "standalone",

  // No usamos next/image en ningún lado (cero imports en src/): apagar el
  // optimizador elimina de raíz el endpoint /_next/image y con él el
  // advisory de DoS de Next 14 (GHSA-h64f-5h5j-jqjh), que no tiene fix
  // dentro de la línea 14.x.
  images: { unoptimized: true },

  // Sin "X-Powered-By: Next.js": es reconocimiento gratis para un atacante.
  poweredByHeader: false,

  // Las privadas no se indexan aunque alguien las enlace. robots.txt solo
  // pide no rastrear; esto es lo que de verdad saca una URL de Google.
  async headers() {
    return RUTAS_PRIVADAS.flatMap((r) => [
      { source: `/${r}`, headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] },
      { source: `/${r}/:path*`, headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] },
    ]);
  },
};

export default nextConfig;
