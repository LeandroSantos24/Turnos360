/**
 * Datos de contacto comercial de Turnos360, en UN solo lugar.
 *
 * Existe por un motivo concreto: la landing tenía WA_NUMBER = "5492610000000"
 * (un placeholder) y el login tenía href="#" en las tres redes. Con los datos
 * repartidos por archivo, un placeholder puede quedar vivo en producción sin
 * que nadie lo note — y en la landing eso significa que cada CTA manda al
 * cliente a un WhatsApp que no existe.
 *
 * Si cambia el número o se suma una red, se toca ACÁ y nada más.
 */

/** Formato wa.me: código de país + 9 + área sin 0 + número sin 15. */
export const WA_NUMERO = "5492613456599";

/** +54 9 261 345-6599, para mostrar en pantalla. */
export const WA_VISIBLE = "+54 9 261 345-6599";

export const EMAIL_CONTACTO = "turnos360.contacto@gmail.com";

export const INSTAGRAM = "https://www.instagram.com/turnos360/";

/**
 * Página de Facebook. Cuando tengas la URL definitiva (la que sale al abrir
 * la página desde el navegador, no desde el administrador), reemplazá acá.
 * Mientras esté en null, el ícono no se muestra: preferible ausente que roto.
 */
export const FACEBOOK: string | null = null;

/** Todavía no hay canal. Cuando lo haya, va acá y aparece solo. */
export const YOUTUBE: string | null = null;

/** Arma un link de WhatsApp con mensaje inicial ya cargado. */
export function linkWa(mensaje: string): string {
  return `https://wa.me/${WA_NUMERO}?text=${encodeURIComponent(mensaje)}`;
}

/** El CTA por defecto de la landing. */
export const WA_LINK_DEMO = linkWa(
  "Hola! Quiero probar Turnos360 en mi negocio.",
);
