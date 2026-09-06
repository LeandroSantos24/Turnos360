/**
 * El logo de Turnos360, con el archivo del repo de respaldo.
 *
 * CÓMO FUNCIONA, Y POR QUÉ ASÍ
 * ────────────────────────────
 * El super-admin puede cargar una URL (Cloudinary o donde sea) para cambiar
 * el logo sin desplegar: el gorrito de Navidad, los huevos de Pascua.
 *
 * Pero el logo es lo primero que se ve de la marca, así que NUNCA puede
 * quedar un hueco. La secuencia es:
 *
 *   1. Se pinta el archivo del repo (16 KB, mismo origen, ya cacheado).
 *   2. En paralelo se consulta si hay override. Si lo hay, se cambia el src.
 *   3. Si esa imagen no carga —URL mal, borrada, Cloudinary caído—, el
 *      `onError` vuelve al archivo del repo.
 *
 * Nunca hay un momento sin logo, y el override nunca está en el camino
 * crítico del primer pintado.
 *
 * OJO CON LA IDEA DE QUE ES «MÁS LIVIANO»
 * ───────────────────────────────────────
 * No lo es. El archivo local sale del mismo origen que la página; una URL
 * externa suma un DNS, un TLS y un tercero del que depende tu página de
 * ventas. Lo que se gana es poder cambiarlo sin desplegar — que es el pedido,
 * y es suficiente motivo.
 */

import { useEffect, useState } from "react";

import { API_URL } from "@/lib/api";

/** El del repo. Es el default y el respaldo de todo lo demás. */
export const LOGO_LOCAL = "/marca/logo-turnos360.webp";

/**
 * Devuelve el src del logo y el manejador de error que vuelve al local.
 *
 * Se usa así:
 *
 *   const { src, alFallar } = useLogoMarca();
 *   <img src={src} onError={alFallar} alt="Turnos360" />
 */
export function useLogoMarca() {
  const [src, setSrc] = useState(LOGO_LOCAL);

  useEffect(() => {
    let vivo = true;
    fetch(`${API_URL}/publico/marca`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const url = (d?.logo_url ?? "").trim();
        if (vivo && url) setSrc(url);
      })
      // Que no haya override —o que el backend no conteste— es el caso
      // normal, no un error: el logo del repo ya está en pantalla.
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, []);

  return {
    src,
    /** Si el override no carga, se vuelve al archivo del repo. */
    alFallar: () => setSrc((actual) => (actual === LOGO_LOCAL ? actual : LOGO_LOCAL)),
  };
}
