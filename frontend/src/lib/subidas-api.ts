/**
 * Subir imágenes del negocio.
 *
 * El `proposito` le dice al servidor PARA QUÉ es, y con eso decide a cuánto
 * reducirla. El tamaño lo elige el servidor a propósito: si viniera de acá,
 * bastaría con cambiar un número en el navegador para guardar imágenes
 * gigantes y llenarle el disco.
 */

import { api } from "./api";

export type Proposito = "avatar" | "logo" | "portada" | "galeria";

export async function subirImagen(
  archivo: File,
  proposito: Proposito,
): Promise<{ url: string }> {
  const form = new FormData();
  form.append("archivo", archivo);
  form.append("proposito", proposito);
  // Sin Content-Type a mano: el navegador tiene que ponerlo él para incluir el
  // `boundary` del multipart. Escribirlo rompe la subida con un 422 que no
  // menciona el boundary por ningún lado.
  return api.postForm<{ url: string }>("/subidas/imagen", form);
}
