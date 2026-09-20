"use client";

/**
 * El movimiento de la landing, en un solo lugar.
 *
 * framer-motion ya estaba en el proyecto (lo usan el panel y la vidriera), así
 * que esto no suma una dependencia nueva.
 */

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import type { CSSProperties, ReactNode } from "react";

/** La misma curva que usa la vidriera. Tupla tipada: motion 12 es estricto. */
export const EASE: [number, number, number, number] = [0.21, 0.6, 0.35, 1];

/**
 * Sube y enciende un bloque cuando entra en pantalla, una sola vez.
 *
 * `amount: 0.15` y no 0.5: una tarjeta alta en un celular nunca llega a estar
 * medio visible antes de que el dedo la pase de largo, y se quedaba apagada.
 */
export function Revelar({
  children,
  demora = 0,
  y = 22,
  className,
  style,
}: {
  children: ReactNode;
  demora?: number;
  y?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const quieto = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      initial={quieto ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.6, ease: EASE, delay: demora }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Reloj de los mockups que se animan solos: devuelve el paso de un ciclo.
 *
 * Con `prefers-reduced-motion` no arranca y se queda en el ÚLTIMO paso, para
 * que quien pidió menos movimiento vea el estado final —el turno tomado, la
 * seña cobrada— y no una pantalla a medio llenar que parece rota.
 *
 * Ese salto va en un efecto y no en el useState inicial porque
 * `useReducedMotion` lee un media query que en el servidor no existe: arrancar
 * distinto según su valor rompería la hidratación.
 */
export function usePasos(tiempos: readonly number[]) {
  const quieto = useReducedMotion();
  const [paso, setPaso] = useState(0);

  // Los tiempos por referencia y no en las dependencias: si estuvieran ahí, dos
  // pasos seguidos de igual duración no volverían a disparar el efecto y el
  // ciclo se clavaría en el segundo.
  const tiemposRef = useRef(tiempos);
  tiemposRef.current = tiempos;

  useEffect(() => {
    const t = tiemposRef.current;
    if (quieto) {
      setPaso(t.length - 1);
      return;
    }
    const id = setTimeout(() => setPaso((p) => (p + 1) % t.length), t[paso]);
    return () => clearTimeout(id);
  }, [paso, quieto]);

  return paso;
}
