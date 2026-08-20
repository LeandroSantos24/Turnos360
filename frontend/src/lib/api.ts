/**
 * Capa de comunicación con el backend de Turnos360.
 *
 * Centraliza TODAS las llamadas a la API: pone la URL base, adjunta el token
 * de autenticación, renueva la sesión cuando vence, y maneja los errores de
 * forma uniforme. Cada pantalla usa estas funciones en vez de armar sus
 * propias llamadas.
 *
 * RENOVACIÓN DE SESIÓN
 * --------------------
 * El backend expone /auth/refresh y el login guarda un refresh token de 7
 * días, pero hasta ahora nadie lo usaba: ante un 401 se borraba la sesión y
 * listo. Como el access token dura 30 minutos, TODOS los usuarios quedaban
 * expulsados cada media hora, perdiendo el formulario que estuvieran
 * llenando. Era el bug más visible del sistema.
 *
 * Ahora, ante un 401 se intenta renovar UNA vez y se reintenta el pedido
 * original. Recién si la renovación falla se cierra la sesión.
 */

import { clearToken, getRefreshToken, getToken, saveTokens } from "./auth";

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
 * Renovación en curso, si la hay.
 *
 * Es UNA sola para toda la aplicación, a propósito. Una pantalla como la
 * agenda dispara seis o siete pedidos a la vez; cuando el token vence, los
 * siete reciben 401 al mismo tiempo. Sin esta variable, los siete llamarían a
 * /auth/refresh en paralelo: seis de esas llamadas usarían un refresh token
 * que la primera acaba de rotar, fallarían, y cerrarían la sesión igual —
 * justo lo que estamos tratando de evitar. Con esto, el primero renueva y los
 * otros seis esperan ese mismo resultado.
 */
let renovacionEnCurso: Promise<string | null> | null = null;

/**
 * Pide un par de tokens nuevo con el refresh token guardado.
 * Devuelve el access token nuevo, o null si no se pudo renovar.
 */
async function renovarSesion(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return null;

    const data = await res.json();
    if (!data?.access_token || !data?.refresh_token) return null;

    saveTokens(data.access_token, data.refresh_token);
    return data.access_token as string;
  } catch {
    // Sin red, o el backend caído. No es una sesión inválida: no borramos
    // nada acá; que decida quien llamó.
    return null;
  }
}

/** Renueva una sola vez aunque la llamen varios pedidos a la vez. */
function renovarSesionUnaVez(): Promise<string | null> {
  if (!renovacionEnCurso) {
    renovacionEnCurso = renovarSesion().finally(() => {
      renovacionEnCurso = null;
    });
  }
  return renovacionEnCurso;
}

/** Lee el detalle de error que manda FastAPI, si lo hay. */
async function detalleDeError(res: Response, porDefecto: string): Promise<string> {
  try {
    const data = await res.json();
    return data?.detail || porDefecto;
  } catch {
    return porDefecto;
  }
}

interface OpcionesRequest extends RequestInit {
  /** Uso interno: evita que el reintento entre en bucle. */
  _reintento?: boolean;
}

/**
 * Hace una llamada a la API. Es la función base que usan todas las demás.
 *
 * - Adjunta el token automáticamente (si hay uno guardado).
 * - Ante un 401, renueva la sesión y reintenta UNA vez.
 * - Convierte los errores en ApiError con su código, para manejarlos arriba.
 * - Acepta `signal` para poder cancelar el pedido (ver AbortController).
 */
async function request<T>(path: string, options: OpcionesRequest = {}): Promise<T> {
  const { _reintento, ...init } = options;
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (res.status === 401) {
    // Segunda vez con 401: la renovación no alcanzó. Sesión terminada.
    if (_reintento) {
      clearToken();
      throw new ApiError(401, "Sesión expirada. Iniciá sesión de nuevo.");
    }

    const nuevo = await renovarSesionUnaVez();
    if (!nuevo) {
      clearToken();
      throw new ApiError(401, "Sesión expirada. Iniciá sesión de nuevo.");
    }

    // Con el token nuevo, se reintenta el pedido original tal cual.
    return request<T>(path, { ...options, _reintento: true });
  }

  if (!res.ok) {
    throw new ApiError(res.status, await detalleDeError(res, `Error ${res.status}`));
  }

  // 204 No Content (ej: un DELETE) no tiene cuerpo que parsear.
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

/**
 * ¿El error es porque cancelamos el pedido a propósito?
 *
 * Cuando el usuario cambia rápido de día en la agenda, los pedidos viejos se
 * cancelan. Eso NO es una falla: no hay que mostrar un cartel rojo por algo
 * que pidió el propio usuario.
 *
 *     try { ... } catch (e) {
 *       if (esCancelado(e)) return;   // navegó a otro lado, no pasa nada
 *       toast.error("No se pudo cargar");
 *     }
 */
export function esCancelado(error: unknown): boolean {
  return (
    error instanceof DOMException && error.name === "AbortError"
  ) || (error as { name?: string })?.name === "AbortError";
}

/** Atajos para los métodos HTTP más comunes. */
export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), signal }),
  patch: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body), signal }),
  put: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body), signal }),
  delete: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { method: "DELETE", signal }),
};
