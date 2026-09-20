/**
 * EL MOVIMIENTO DEL PRODUCTO, EN UN SOLO LUGAR
 * ═════════════════════════════════════════════
 *
 * Antes cada pantalla elegía su propia duración y su propia curva a ojo, y el
 * resultado es el que se nota sin saber nombrarlo: un diálogo que tarda 200ms,
 * una hoja que tarda 350 y una tarjeta que tarda 420. Cada pieza se mueve
 * distinto, así que el producto no se siente como UNA cosa.
 *
 * Esto es lo que Apple usa (charla «Designing Fluid Interfaces», WWDC 2018),
 * traducido a framer-motion. La idea de fondo: una animación con duración fija
 * NO puede responder a una entrada nueva. Si el usuario agarra algo que se está
 * moviendo, la duración fija tiene que terminar su recorrido o cortar de golpe.
 * Un resorte no: cambiarle el destino a mitad de camino es legal, arranca desde
 * donde está y con la velocidad que traía. Por eso todo lo que el usuario puede
 * TOCAR va con resorte, y solo lo que aparece solo (un bloque al hacer scroll)
 * se queda con duración y curva.
 *
 * Apple no piensa en masa/rigidez/amortiguación sino en dos números:
 *
 *   · AMORTIGUACIÓN (damping) — cuánto se pasa de largo.
 *       1.0 = no se pasa nunca, frena y se planta. Es el default.
 *       0.8 = se pasa un poquito y vuelve.
 *   · RESPUESTA (response) — en cuánto llega, en segundos. Más bajo, más seco.
 *       NO es "duración": un resorte no tiene duración fija, la que tarda en
 *       asentarse sale de los dos parámetros.
 *
 * En framer-motion esos dos son `bounce` y `duration`:
 *   bounce 0 ≡ amortiguación 1.0   ·   bounce 0.2 ≡ amortiguación ≈0.8
 *
 * REGLA: rebote SOLO cuando el gesto traía impulso (un tirón, un arrastre que
 * se suelta, una hoja que sube). Que rebote un menú que apenas se encendió se
 * lee como un error, no como vida.
 */

import type { Transition } from "framer-motion";

/**
 * Curva para lo que NO se toca: bloques que entran al hacer scroll, opacidades,
 * colores. Ahí un resorte no aporta nada (nadie va a agarrar un fade) y una
 * curva cuesta menos. Es la misma que ya usaban la vidriera y la landing.
 */
export const EASE: [number, number, number, number] = [0.21, 0.6, 0.35, 1];

/** Las tres duraciones del sistema, en segundos. Espejo de --rapido/--normal/--lento. */
export const DURACION = { rapido: 0.13, normal: 0.22, lento: 0.42 } as const;

/**
 * Los resortes del producto. Usar estos y no números sueltos.
 *
 * Los valores son los que Apple publica para cada tipo de interacción:
 * mover/reubicar 1.0/0.4, rotar 0.8/0.4, cajón u hoja 0.8/0.3.
 */
export const RESORTE = {
  /** Default de toda la interfaz. No se pasa de largo. Amortiguación 1.0, respuesta 0.4. */
  ui: { type: "spring", bounce: 0, duration: 0.4 },
  /** Lo mismo pero más seco: estados de un control, un check, un tab que se corre. */
  seco: { type: "spring", bounce: 0, duration: 0.25 },
  /** Hojas, cajones y modales que suben. Amortiguación 0.8, respuesta 0.3. */
  hoja: { type: "spring", bounce: 0.2, duration: 0.3 },
  /**
   * Para cuando el gesto traía impulso: una tarjeta que se tira, un carrusel
   * que se suelta. Es el ÚNICO caso donde el rebote está justificado.
   */
  impulso: { type: "spring", bounce: 0.2, duration: 0.4 },
} as const satisfies Record<string, Transition>;

/**
 * Dónde va a FRENAR algo que se soltó a esta velocidad.
 *
 * Es la misma curva de desaceleración que usa el scroll del sistema. Sirve para
 * no decidir el destino de un gesto por el punto donde se soltó el dedo sino
 * por el punto al que el gesto APUNTABA: alguien que tira fuerte una hoja hacia
 * abajo quiere cerrarla aunque la haya soltado arriba de la mitad.
 *
 * Ojo: NO es la fórmula de física de manual (v²/2a). Esta es la exponencial que
 * usa el sistema y se siente distinto.
 *
 * @param velocidad px/s al soltar (la que da framer-motion en `info.velocity`)
 * @param freno 0.998 se siente como el scroll normal; 0.99 más corto y seco
 * @returns cuántos px más va a recorrer desde donde está
 */
export function proyectar(velocidad: number, freno = 0.998): number {
  return ((velocidad / 1000) * freno) / (1 - freno);
}

/**
 * De una lista de posiciones a las que se puede caer, la más cercana a `punto`.
 * Se le pasa el punto PROYECTADO, no el punto donde se soltó.
 */
export function masCercano(punto: number, opciones: readonly number[]): number {
  return opciones.reduce((a, b) =>
    Math.abs(b - punto) < Math.abs(a - punto) ? b : a
  );
}

/**
 * Resistencia elástica en un borde.
 *
 * Frenar en seco al llegar al final se lee como "se colgó". Seguir un poco pero
 * cada vez menos se lee como "responde, pero acá no hay más". Es la diferencia
 * entre una lista que parece rota y una que parece que tiene un final.
 *
 * @param exceso cuántos px se pasó del borde
 * @param medida el alto (o ancho) del contenedor
 * @param k cuánto cede; 0.55 es el valor del sistema
 * @returns cuántos px mover de verdad — siempre menos que `exceso`
 */
export function gomita(exceso: number, medida: number, k = 0.55): number {
  return (exceso * medida * k) / (medida + k * Math.abs(exceso));
}

/**
 * La versión sin movimiento de cualquier transición, para
 * `prefers-reduced-motion`. No es "nada": es un fundido corto. Quien pidió
 * menos movimiento igual necesita ver QUE algo cambió — lo que no necesita es
 * que se lo deslicen por la pantalla.
 */
export const QUIETO: Transition = { duration: 0.15, ease: "easeOut" };

/** Elige entre la transición normal y la quieta. `quieto` sale de `useReducedMotion()`. */
export function segunPreferencia(t: Transition, quieto: boolean | null): Transition {
  return quieto ? QUIETO : t;
}
