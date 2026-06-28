/**
 * Cliente de la API del panel de super-administración.
 * Usa un token propio (separado del de los usuarios de empresa).
 */

import { ApiError } from "./api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ADMIN_TOKEN_KEY = "turnos360_admin_token";

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}
export function setAdminToken(t: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ADMIN_TOKEN_KEY, t);
}
export function clearAdminToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

async function adminRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAdminToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearAdminToken();
    throw new ApiError(401, "Sesión de administrador expirada. Iniciá sesión de nuevo.");
  }
  if (!res.ok) {
    let detalle = `Error ${res.status}`;
    try {
      const d = await res.json();
      detalle = d.detail || detalle;
    } catch {
      // respuesta no-JSON
    }
    throw new ApiError(res.status, detalle);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

const adminApi = {
  get: <T>(p: string) => adminRequest<T>(p),
  post: <T>(p: string, b: unknown) =>
    adminRequest<T>(p, { method: "POST", body: JSON.stringify(b) }),
  patch: <T>(p: string, b: unknown) =>
    adminRequest<T>(p, { method: "PATCH", body: JSON.stringify(b) }),
};

// ---------- Tipos ----------
export interface RubroAdmin {
  id: number;
  codigo: string;
  nombre: string;
}
export interface EmpresaAdmin {
  id: number;
  nombre: string;
  slug: string;
  rubro_nombre: string | null;
  activa: boolean;
  cantidad_usuarios: number;
}
export type RolUsuario = "dueno" | "admin" | "recepcion" | "profesional";
export interface UsuarioAdmin {
  id: number;
  nombre: string;
  email: string;
  rol: RolUsuario;
  activo: boolean;
}

// ---------- Login (fetch directo: un 401 acá es credencial inválida, no sesión vencida) ----------
export async function loginAdmin(
  email: string,
  clave: string,
): Promise<{ access_token: string; nombre: string }> {
  const res = await fetch(`${API_URL}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, clave }),
  });
  if (!res.ok) {
    let detalle = "Email o contraseña incorrectos";
    try {
      const d = await res.json();
      detalle = d.detail || detalle;
    } catch {
      // no-JSON
    }
    throw new ApiError(res.status, detalle);
  }
  return res.json();
}

// ---------- Rubros ----------
export function listarRubros(): Promise<RubroAdmin[]> {
  return adminApi.get<RubroAdmin[]>("/admin/rubros");
}

// ---------- Empresas ----------
export function listarEmpresas(): Promise<EmpresaAdmin[]> {
  return adminApi.get<EmpresaAdmin[]>("/admin/empresas");
}
export function crearEmpresa(datos: {
  nombre: string;
  slug: string;
  rubro_id: number;
  dueno: { nombre: string; email: string; clave: string };
}): Promise<EmpresaAdmin> {
  return adminApi.post<EmpresaAdmin>("/admin/empresas", datos);
}
export function pausarEmpresa(id: number, activa: boolean): Promise<EmpresaAdmin> {
  return adminApi.patch<EmpresaAdmin>(`/admin/empresas/${id}`, { activa });
}

// ---------- Usuarios ----------
export function listarUsuarios(empresaId: number): Promise<UsuarioAdmin[]> {
  return adminApi.get<UsuarioAdmin[]>(`/admin/empresas/${empresaId}/usuarios`);
}
export function crearUsuario(
  empresaId: number,
  datos: { nombre: string; email: string; clave: string; rol: RolUsuario },
): Promise<UsuarioAdmin> {
  return adminApi.post<UsuarioAdmin>(`/admin/empresas/${empresaId}/usuarios`, datos);
}
export function actualizarUsuario(id: number, activo: boolean): Promise<UsuarioAdmin> {
  return adminApi.patch<UsuarioAdmin>(`/admin/usuarios/${id}`, { activo });
}