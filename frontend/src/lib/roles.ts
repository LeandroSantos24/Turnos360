"use client";

/**
 * Lectura del rol del usuario logueado.
 *
 * El rol viaja firmado dentro del access token (payload.rol), así que lo
 * sacamos de ahí sin pegarle al backend. Reutiliza getToken() de auth.ts
 * para no duplicar de dónde sale el token.
 *
 * OJO: esto es SOLO para la UI (esconder botones/menús). El candado real
 * está en el backend (gate_dueno / gate_gestion en deps.py): aunque alguien
 * fuerce la UI, el endpoint igual le devuelve 403.
 */

import { useEffect, useState } from "react";

import { getToken } from "@/lib/auth";

export type Rol = "dueno" | "recepcion" | "profesional" | "admin";

/** Decodifica el payload del JWT y devuelve el rol (o null si no se puede). */
function decodificarRol(token: string | null): Rol | null {
  if (!token) return null;
  try {
    const parte = token.split(".")[1];
    const base64 = parte.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64)) as { rol?: Rol };
    return payload.rol ?? null;
  } catch {
    return null;
  }
}

/**
 * Hook: devuelve el rol del usuario logueado, o null si no hay sesión.
 *
 * Lee en un useEffect (no en el render) para no romper la hidratación de
 * Next: el server no tiene localStorage, así que el primer render es null
 * en ambos lados y recién después se resuelve en el navegador.
 */
export function useRol(): Rol | null {
  const [rol, setRol] = useState<Rol | null>(null);
  useEffect(() => {
    setRol(decodificarRol(getToken()));
  }, []);
  return rol;
}

// --- Criterios de permiso (los MISMOS grupos que el backend) ---------------
/** Solo el dueño: catálogo, config, finanzas sensibles. */
export const esDueno = (rol: Rol | null): boolean => rol === "dueno";

/** Gestión del día: dueño + recepción (+ admin dormido). Excluye profesional. */
export const esGestion = (rol: Rol | null): boolean =>
  rol === "dueno" || rol === "recepcion" || rol === "admin";

/** El profesional (su vista propia llega con el link Usuario<->Recurso). */
export const esProfesional = (rol: Rol | null): boolean => rol === "profesional";
