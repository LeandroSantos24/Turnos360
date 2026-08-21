/**
 * Validación de los IDs de seguimiento (Meta Pixel y Google Tag).
 *
 * POR QUÉ ESTO VIVE SOLO, EN SU PROPIO ARCHIVO, SIN IMPORTAR NADA
 * ---------------------------------------------------------------
 * Estos valores terminan escritos DENTRO de un <script> en la vidriera
 * pública — la misma página donde el cliente deja su nombre y su teléfono.
 * Un ID mal formado ahí adentro es XSS.
 *
 * El backend ya los valida con la misma lista blanca, pero acá se vuelve a
 * chequear: es la clase de dato donde conviene desconfiar en las dos puntas.
 *
 * Al no depender de React ni de Next, este archivo se puede ejecutar solo, y
 * eso es lo que hace `scripts/verificar-seguimiento.mjs` con la misma lista de
 * venenos que la suite del backend. Sin esta separación, la defensa anti-XSS
 * del navegador no tendría un solo test.
 */

/** Meta Pixel: solo dígitos. */
export const META_OK = /^\d{6,20}$/;

/** Google Tag: G- (Analytics), AW- (Ads), GT- (Tag Manager) o UA- (viejo). */
export const GOOGLE_OK = /^(G|AW|GT|UA)-[A-Z0-9-]{4,30}$/i;

/**
 * La etiqueta de conversión de Google Ads.
 *
 * NO se pasa a mayúsculas en ningún lado: Google las genera distinguiendo
 * mayúsculas de minúsculas (algo como `AbC-D_efG-h12_34-567`) y cambiarlas
 * hace que la conversión no se registre — sin ningún error visible.
 */
export const LABEL_OK = /^[A-Za-z0-9_-]{6,40}$/;

/** El pixel de Meta si es válido, o null. */
export function pixelValido(id?: string | null): string | null {
  const v = (id ?? "").trim();
  return META_OK.test(v) ? v : null;
}

/** El tag de Google si es válido, o null. */
export function tagValido(id?: string | null): string | null {
  const v = (id ?? "").trim();
  return GOOGLE_OK.test(v) ? v : null;
}

/**
 * El `send_to` de Google Ads, o null si no hay con qué armarlo.
 *
 * Ads necesita el par completo `AW-XXXXXXXXX/etiqueta`. Con un tag de
 * Analytics (G-) no hay conversión de Ads que disparar, y sin etiqueta
 * tampoco: mandar el evento a medias no cuenta nada y ensucia la cuenta.
 */
export function destinoConversion(
  googleTagId?: string | null,
  googleConversionLabel?: string | null,
): string | null {
  const tag = tagValido(googleTagId);
  const label = (googleConversionLabel ?? "").trim();
  if (!tag || !tag.toUpperCase().startsWith("AW-")) return null;
  if (!LABEL_OK.test(label)) return null;
  return `${tag}/${label}`;
}
