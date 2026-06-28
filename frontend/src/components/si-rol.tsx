"use client";

/**
 * Guardas de UI por rol. Envolvés cualquier control y se muestra solo si el
 * rol del usuario lo permite. No reemplaza el candado del backend: es para que
 * el usuario no VEA botones que igual no podría usar.
 *
 *   <SoloDueno><BotonNuevoServicio /></SoloDueno>
 *   <SoloGestion><BotonCobrar /></SoloGestion>
 *   <SiRol roles={["dueno", "recepcion"]}>...</SiRol>
 */

import type { ReactNode } from "react";

import { esDueno, esGestion, useRol, type Rol } from "@/lib/roles";

interface Props {
  children: ReactNode;
  /** Qué mostrar si el rol NO está permitido (por defecto, nada). */
  fallback?: ReactNode;
}

/** Muestra children solo si el rol logueado está en `roles`. */
export function SiRol({
  roles,
  children,
  fallback = null,
}: Props & { roles: Rol[] }) {
  const rol = useRol();
  return <>{roles.includes(rol as Rol) ? children : fallback}</>;
}

/** Atajo: solo el dueño. */
export function SoloDueno({ children, fallback = null }: Props) {
  const rol = useRol();
  return <>{esDueno(rol) ? children : fallback}</>;
}

/** Atajo: gestión del día (dueño + recepción + admin). Excluye profesional. */
export function SoloGestion({ children, fallback = null }: Props) {
  const rol = useRol();
  return <>{esGestion(rol) ? children : fallback}</>;
}
