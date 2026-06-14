/**
 * Manejo del token de autenticación en el navegador.
 *
 * Guardamos el access token en localStorage para que la sesión persista
 * entre recargas de página. Es simple y suficiente para el panel interno.
 */

const TOKEN_KEY = "turnos360_token";
const REFRESH_KEY = "turnos360_refresh";

/** Guarda los tokens tras un login exitoso. */
export function saveTokens(access: string, refresh: string): void {
  if (typeof window === "undefined") return; // no existe en el servidor
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

/** Devuelve el access token guardado, o null si no hay sesión. */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** Devuelve el refresh token guardado. */
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

/** Borra los tokens (logout o sesión vencida). */
export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/** ¿Hay una sesión activa? (true si hay token guardado) */
export function isLoggedIn(): boolean {
  return getToken() !== null;
}