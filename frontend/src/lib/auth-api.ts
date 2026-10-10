/**
 * Llamadas de autenticación al backend.
 * Separadas de api.ts porque el login NO lleva token (todavía no lo tenés).
 */

import { saveTokens } from "./auth";
import { ApiError } from "./api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UsuarioMe {
  id: number;
  nombre: string;
  email: string;
  rol: string;
  empresa_id: number;
  /** El local al que pertenece. Con un solo local, siempre el mismo. */
  sucursal_id: number | null;
  /**
   * false solo para quien se registró solo y todavía no confirmó su email.
   * Mientras esté en false, la página pública de su negocio no se muestra.
   */
  email_verificado: boolean;
  /** Nombre del negocio y del local de esta persona (para «Mi cuenta»). */
  empresa_nombre?: string | null;
  sucursal_nombre?: string | null;
}

/** Inicia sesión: manda email + clave, guarda los tokens si todo va bien. */
export async function login(email: string, clave: string): Promise<void> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, clave }),
  });

  if (!res.ok) {
    let detalle = "Email o contraseña incorrectos";
    try {
      const data = await res.json();
      detalle = data.detail || detalle;
    } catch {
      // respuesta sin JSON
    }
    throw new ApiError(res.status, detalle);
  }

  const data: TokenResponse = await res.json();
  saveTokens(data.access_token, data.refresh_token);
}

/** Trae los datos del usuario logueado (usa el token guardado). */
export async function getMe(): Promise<UsuarioMe> {
  const { api } = await import("./api");
  return api.get<UsuarioMe>("/auth/me");
}

/** Aviso para que el panel (barra lateral) vuelva a leer el usuario. */
export const EVENTO_PERFIL = "t360:perfil-actualizado";

/** Cambia el nombre propio. Es lo único que cada uno edita de sí mismo. */
export async function actualizarPerfil(nombre: string): Promise<UsuarioMe> {
  const { api } = await import("./api");
  const u = await api.patch<UsuarioMe>("/auth/me", { nombre });
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENTO_PERFIL));
  return u;
}

interface SesionRenovada extends TokenResponse {
  detalle: string;
}

/**
 * Cambia la contraseña. El servidor cierra TODAS las sesiones y devuelve un
 * par nuevo para este dispositivo: se guarda acá para no quedar afuera.
 */
export async function cambiarPassword(claveActual: string, claveNueva: string): Promise<string> {
  const { api } = await import("./api");
  const r = await api.post<SesionRenovada>("/auth/cambiar-password", {
    clave_actual: claveActual,
    clave_nueva: claveNueva,
  });
  saveTokens(r.access_token, r.refresh_token);
  return r.detalle;
}

/** Saca de la cuenta a los demás dispositivos. Pide la contraseña. */
export async function cerrarOtrasSesiones(claveActual: string): Promise<string> {
  const { api } = await import("./api");
  const r = await api.post<SesionRenovada>("/auth/cerrar-otras-sesiones", {
    clave_actual: claveActual,
  });
  saveTokens(r.access_token, r.refresh_token);
  return r.detalle;
}

/** Vuelve a mandar el email para confirmar la dirección. */
export async function reenviarVerificacion(): Promise<void> {
  const { api } = await import("./api");
  await api.post("/auth/reenviar-verificacion", {});
}
