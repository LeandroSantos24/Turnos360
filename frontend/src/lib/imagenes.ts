/**
 * Dónde vive una imagen subida por el negocio.
 *
 * EL PROBLEMA QUE RESUELVE
 * ────────────────────────
 * El backend devuelve rutas RELATIVAS: `/uploads/12/abc.webp`. Eso es a
 * propósito —lo que se guarda en la base no incluye el dominio, así que mudar
 * el servidor o cambiar de dominio no rompe las fotos de todos los clientes—,
 * pero el navegador resuelve una ruta relativa contra la página que la muestra,
 * y el panel corre en :3000 mientras la API sirve los archivos desde :8000.
 * Resultado: la imagen no carga y se ve el texto alternativo.
 *
 * Acá se le pone el origen de la API justo antes de mostrarla. La base sigue
 * guardando la ruta portable; el prefijo es cosa de la vista.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function urlDeImagen(url: string | null | undefined): string {
  const u = (url || "").trim();
  if (!u) return "";
  // Absoluta (una URL pegada a mano de antes, o un data:) se deja como está.
  if (/^(https?:)?\/\//i.test(u) || u.startsWith("data:")) return u;
  if (u.startsWith("/uploads/")) return `${API_URL}${u}`;
  return u;
}
