/**
 * Colores de marca que tienen que poder leerse.
 *
 * El color del negocio puede ser cualquiera: un turquesa claro o un amarillo
 * con texto blanco encima no pasa el mínimo AA (4,5:1). `legible` lo oscurece
 * de a poco, sin cambiarle el tono, hasta que pasa. Sirve igual para el caso
 * inverso: el mismo color oscurecido se lee como texto sobre un fondo claro.
 */

function luminancia(r: number, g: number, b: number): number {
  const c = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

/** El color oscurecido hasta tener `minimo`:1 de contraste con el blanco. */
export function legible(hex: string, minimo = 4.5, porDefecto = "#0a7d68"): string {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || "").trim());
  if (!m) return porDefecto;
  let [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  for (let i = 0; i < 30 && 1.05 / (luminancia(r, g, b) + 0.05) < minimo; i++) {
    [r, g, b] = [r, g, b].map((v) => Math.round(v * 0.92));
  }
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}
