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
export const PRECIO_NORMAL = 13900;

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
export const PRECIO_PROMO = 11900;
export const PROMO_ETIQUETA = "Precio de lanzamiento";

/** El precio que se cobra hoy. */
export const PRECIO_MENSUAL = PROMO_ACTIVA ? PRECIO_PROMO : PRECIO_NORMAL;

const enPesos = (n: number) => `$${n.toLocaleString("es-AR")}`;

/** El precio vigente, formateado. */
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


/**
 * La grilla de planes, espejo de backend/app/core/planes.py.
 *
 * Está duplicada a propósito y no viene por API: el panel de super-admin
 * necesita poder ARMAR el selector antes de tener una empresa cargada. Si
 * cambian los precios, se tocan los dos lados — el backend es el que manda,
 * este es solo para pintar.
 */
export const PLANES = [
  {
    codigo: "gratuito",
    etiqueta: "Prueba",
    precio: 0,
    resumen: "Todo desbloqueado, con los cupos de Inicial",
    paraQuien: "Para probarlo con tus turnos de verdad, sin tarjeta.",
  },
  {
    // Los cupos se cuentan como los cuenta el dueño: él y los que atienden
    // con él. El dueño ENTRA en el cupo —en estos rubros atiende— así que
    // «1 dueño + 3» son cuatro columnas en la agenda. Es el mismo número que
    // aplica el backend (planes.py), y hay un test que compara los dos.
    codigo: "inicial",
    etiqueta: "Inicial",
    precio: 13900,
    resumen: "1 dueño + 3 que atienden · 1 local",
    paraQuien: "El que atiende solo o con un equipo chico.",
  },
  {
    codigo: "pro",
    etiqueta: "Pro",
    precio: 19990,
    resumen: "1 dueño + 10 que atienden · 1 local",
    paraQuien: "El local con equipo, que ya quiere vender más a los que tiene.",
  },
  {
    codigo: "multi",
    etiqueta: "Multi",
    precio: 34990,
    resumen: "Equipo ilimitado · hasta 3 locales",
    paraQuien: "El que abrió el segundo local y necesita compararlos.",
  },
  {
    // Precio 0 = a convenir, NO gratis. El super-admin le carga el precio
    // real en `precio_mensual` de la ficha comercial, que es lo que se cobra.
    // No se contrata online: no tiene precio de lista que cobrar.
    codigo: "enterprise",
    etiqueta: "Enterprise",
    precio: 0,
    resumen: "Todo ilimitado · locales a medida",
    paraQuien: "Cadenas y franquicias. Precio y cupos pactados a mano.",
  },
];
