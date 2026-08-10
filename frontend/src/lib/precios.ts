/**
 * Precio de lista de Turnos360, en UN solo lugar.
 *
 * Existe por el mismo motivo que contacto.ts: el precio estaba escrito a mano
 * dentro del JSX de la landing y el panel de cobranza tenía OTRO número como
 * placeholder. Con el precio repartido, cambiarlo significa acordarse de todos
 * los lugares — y el que se olvida queda contradiciendo a la landing delante
 * del cliente.
 *
 * IMPORTANTE: el backend tiene su propia copia en la variable de entorno
 * PRECIO_LISTA_MENSUAL (config.py). No puede ser una sola porque este número
 * se compila dentro del bundle del navegador y no lee variables del servidor.
 * Si cambia el precio, se tocan LOS DOS:
 *   1. este archivo
 *   2. PRECIO_LISTA_MENSUAL en .env / .env.prod
 */

/** Precio normal, de lista. El que se cobra cuando no hay promoción. */
export const PRECIO_NORMAL = 14990;

/**
 * Promoción, apagada por defecto.
 *
 * Es un interruptor, no un compromiso: con PROMO_ACTIVA en false la
 * promoción no existe en ningún lado —ni precio tachado ni etiqueta— y la
 * landing muestra solamente el precio normal. Poniéndolo en true, aparece el
 * normal tachado, el promocional al lado y la etiqueta.
 *
 * En el backend el interruptor equivalente es PROMO_ACTIVA (config.py). Los
 * dos tienen que quedar iguales: el de acá decide qué se MUESTRA, el de allá
 * con qué precio nacen las empresas nuevas.
 */
export const PROMO_ACTIVA = false;
export const PRECIO_PROMO = 11990;
export const PROMO_ETIQUETA = "Precio de lanzamiento";

/** El precio que se cobra hoy. */
export const PRECIO_MENSUAL = PROMO_ACTIVA ? PRECIO_PROMO : PRECIO_NORMAL;

const enPesos = (n: number) => `$${n.toLocaleString("es-AR")}`;

/** "$14.990" — el precio vigente, formateado. */
export const PRECIO_MENSUAL_TEXTO = enPesos(PRECIO_MENSUAL);

/** El normal formateado. Solo se muestra (tachado) si hay promo activa. */
export const PRECIO_NORMAL_TEXTO = enPesos(PRECIO_NORMAL);

/**
 * Días de prueba gratis.
 *
 * Va acá y no suelto en el texto porque aparece en tres lugares de la landing
 * (la pastilla del plan, el botón y la pregunta frecuente). Cuando estaban
 * escritos a mano, dos decían 14 días y uno decía 7: el que leía las dos cosas
 * no sabía cuál creer.
 */
export const DIAS_PRUEBA = 14;
