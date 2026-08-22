import type { CSSProperties } from "react";

/**
 * Estilo único para montos y cifras del panel.
 *
 * Existe porque el mismo número se estaba escribiendo de dos formas distintas
 * dentro de una sola pantalla: algunos montos con Syne y otros con la
 * tipografía del cuerpo, según si el bloque tenía o no la constante local.
 * En una tabla de caja eso se lee como si las columnas no fueran del mismo
 * dato.
 *
 * - lining-nums: fuerza las cifras de altura uniforme, que es como se
 *   espera leer plata. (Hacía falta sobre todo con Syne, que traía cifras
 *   de estilo geométrico; se deja igual porque no cuesta nada y protege
 *   de la próxima fuente que sí las traiga).
 * - tabular-nums: todas las cifras del mismo ancho, para que las columnas de
 *   una tabla queden alineadas verticalmente.
 */
export const NUM: CSSProperties = {
  fontFamily: "var(--fuente-titulos)",
  fontVariantNumeric: "lining-nums tabular-nums",
};

/** 16000 -> "$16.000" */
export function pesos(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toLocaleString("es-AR")}`;
}
