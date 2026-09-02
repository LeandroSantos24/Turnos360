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