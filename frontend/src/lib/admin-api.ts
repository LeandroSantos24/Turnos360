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
  plan: string;
  suscripcion_vence: string | null;
  estado_suscripcion: string;
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

export function setearSuscripcion(
  id: number,
  datos: { plan?: string; suscripcion_vence?: string | null; renovar_30?: boolean },
): Promise<EmpresaAdmin> {
  return adminApi.patch<EmpresaAdmin>(`/admin/empresas/${id}/suscripcion`, datos);
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
// ═══════════════════════════════════════════════════════════════════
// Cobranza del SaaS (semáforo, resumen, pagos, prórrogas)
// ═══════════════════════════════════════════════════════════════════

export type SemaforoColor = "verde" | "amarillo" | "rojo" | "gris";

export interface EmpresaCobranza {
  id: number;
  nombre: string;
  slug: string;
  activa: boolean;
  plan: string;
  suscripcion_vence: string | null;
  precio_mensual: number | null;
  razon_social: string | null;
  cuit: string | null;
  contacto_nombre: string | null;
  contacto_email: string | null;
  contacto_telefono: string | null;
  notas_admin: string | null;
  cantidad_usuarios: number;
  cantidad_recursos: number;
  limite_recursos: number | null;
  capacidad_excedida: boolean;
  ultimo_pago: string | null;
  semaforo_color: SemaforoColor;
  semaforo_dias_restantes: number | null;
  semaforo_fin_prorroga: string | null;
  semaforo_en_prorroga: boolean;
  semaforo_detalle: string;
}

export interface ResumenCobranza {
  cobrado_mes: number;
  por_metodo: { metodo: string; total: number }[];
  pendiente_estimado: number;
  empresas_por_vencer: number;
  por_vencer_sin_precio: number;
  deuda_vencida: number;
  empresas_vencidas: number;
  mrr: number;
  dias_aviso: number;
}

export interface PagoSuscripcion {
  id: number;
  fecha: string;
  monto: number;
  metodo: string;
  periodo_desde: string | null;
  periodo_hasta: string | null;
  notas: string | null;
}

export function listarCobranza(filtros: {
  buscar?: string;
  color?: SemaforoColor | "";
  plan?: string;
} = {}): Promise<EmpresaCobranza[]> {
  const p = new URLSearchParams();
  if (filtros.buscar) p.set("buscar", filtros.buscar);
  if (filtros.color) p.set("color", filtros.color);
  if (filtros.plan) p.set("plan", filtros.plan);
  const qs = p.toString();
  return adminRequest<EmpresaCobranza[]>(`/admin/cobranza/empresas${qs ? `?${qs}` : ""}`);
}

export function resumenCobranza(): Promise<ResumenCobranza> {
  return adminRequest<ResumenCobranza>("/admin/cobranza/resumen");
}

export function historialPagos(empresaId: number): Promise<PagoSuscripcion[]> {
  return adminRequest<PagoSuscripcion[]>(`/admin/empresas/${empresaId}/pagos`);
}

export function registrarPago(
  empresaId: number,
  datos: { monto: number; metodo: string; fecha?: string; notas?: string; renovar?: boolean },
): Promise<PagoSuscripcion> {
  return adminRequest<PagoSuscripcion>(`/admin/empresas/${empresaId}/pagos`, {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

export function darProrroga(empresaId: number, dias: number): Promise<EmpresaCobranza> {
  return adminRequest<EmpresaCobranza>(`/admin/empresas/${empresaId}/prorroga`, {
    method: "POST",
    body: JSON.stringify({ dias }),
  });
}

export function guardarFicha(
  empresaId: number,
  datos: Partial<{
    razon_social: string | null;
    cuit: string | null;
    contacto_nombre: string | null;
    contacto_email: string | null;
    contacto_telefono: string | null;
    notas_admin: string | null;
    precio_mensual: number | null;
    limite_recursos: number | null;
  }>,
): Promise<EmpresaCobranza> {
  return adminRequest<EmpresaCobranza>(`/admin/empresas/${empresaId}/ficha`, {
    method: "PUT",
    body: JSON.stringify(datos),
  });
}
