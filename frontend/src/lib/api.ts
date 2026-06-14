/**
 * Capa de comunicación con el backend de Turnos360.
 *
 * Centraliza TODAS las llamadas a la API: pone la URL base, adjunta el token
 * de autenticación, y maneja los errores de forma uniforme. Cada pantalla usa
 * estas funciones en vez de armar sus propias llamadas.
 */

import { getToken, clearToken } from "./auth";

// La URL del backend viene de la variable de entorno (definida en docker-compose).
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Error con el código HTTP, para que las pantallas sepan qué pasó. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Hace una llamada a la API. Es la función base que usan todas las demás.
 *
 * - Adjunta el token automáticamente (si hay uno guardado).
 * - Si el backend responde 401 (token vencido/inválido), borra el token.
 * - Convierte los errores en ApiError con su código, para manejarlos arriba.
 */
async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  // 401 = no autorizado: el token no sirve, lo borramos.
  if (res.status === 401) {
    clearToken();
    throw new ApiError(401, "Sesión expirada. Iniciá sesión de nuevo.");
  }

  // Cualquier otro error: intentamos leer el detalle que manda FastAPI.
  if (!res.ok) {
    let detalle = `Error ${res.status}`;
    try {
      const data = await res.json();
      detalle = data.detail || detalle;
    } catch {
      // si la respuesta no es JSON, dejamos el mensaje genérico
    }
    throw new ApiError(res.status, detalle);
  }

  // 204 No Content (ej: un DELETE) no tiene cuerpo que parsear.
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

/** Atajos para los métodos HTTP más comunes. */
export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};