/**
 * Cliente de la API del panel de super-administración.
 * Usa un token propio (separado del de los usuarios de empresa).
 */

import { ApiError, textoDeDetalle } from "./api";
import type { EstadoSuscripcion, TonoEstado } from "./empresa-api";

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
      detalle = textoDeDetalle(d.detail, detalle);
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
  put: <T>(p: string, b: unknown) =>
    adminRequest<T>(p, { method: "PUT", body: JSON.stringify(b) }),
};

// ---------- Tipos ----------
export type { EstadoSuscripcion, TonoEstado };
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
  /** Sale de estado_suscripcion() (core/estados_suscripcion.py). */
  estado_suscripcion: EstadoSuscripcion;
}
export type RolUsuario = "dueno" | "admin" | "recepcion" | "profesional";
export interface EstadoInvitacion {
  estado: "enviando" | "enviada" | "envio_fallido" | "vencida" | "sin_invitacion";
  creada_en?: string | null;
  expira_en: string | null;
  enviada_en: string | null;
  envio_error: string | null;
}
export interface UsuarioAdmin {
  id: number;
  nombre: string;
  email: string;
  rol: RolUsuario;
  activo: boolean;
  activacion_pendiente?: boolean;
  ultimo_ingreso_en?: string | null;
  invitacion?: EstadoInvitacion | null;
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
  /** Días de prueba con los que arranca. 0 = cliente que ya paga. */
  dias_prueba?: number;
}): Promise<EmpresaAdmin> {
  return adminApi.post<EmpresaAdmin>("/admin/empresas", datos);
}
export function pausarEmpresa(
  id: number,
  activa: boolean,
  motivo?: string | null,
): Promise<EmpresaAdmin> {
  return adminApi.patch<EmpresaAdmin>(`/admin/empresas/${id}`, { activa, motivo: motivo || null });
}

export function setearSuscripcion(
  id: number,
  datos: {
    plan?: string;
    suscripcion_vence?: string | null;
    renovar_30?: boolean;
    /** Obligatorio: lo exige el backend para todo cambio de plan o vencimiento. */
    motivo: string;
    categoria?: "cortesia" | "incidencia" | "correccion" | null;
  },
): Promise<EmpresaAdmin> {
  return adminApi.patch<EmpresaAdmin>(`/admin/empresas/${id}/suscripcion`, datos);
}

// ---------- Usuarios ----------
export function listarUsuarios(empresaId: number): Promise<UsuarioAdmin[]> {
  return adminApi.get<UsuarioAdmin[]>(`/admin/empresas/${empresaId}/usuarios`);
}
/** Alta por invitación: sin contraseña, le llega un link para elegirla. */
export function crearUsuario(
  empresaId: number,
  datos: { nombre: string; email: string; rol: RolUsuario },
): Promise<UsuarioAdmin> {
  return adminApi.post<UsuarioAdmin>(`/admin/empresas/${empresaId}/usuarios`, datos);
}
export function actualizarUsuario(id: number, activo: boolean): Promise<UsuarioAdmin> {
  return adminApi.patch<UsuarioAdmin>(`/admin/usuarios/${id}`, { activo });
}
// ═══════════════════════════════════════════════════════════════════
// Cobranza del SaaS (semáforo, resumen, pagos, prórrogas)
// ═══════════════════════════════════════════════════════════════════

/** azul = dentro del período de prueba (ni al día ni moroso). */
export type SemaforoColor = "verde" | "amarillo" | "rojo" | "gris" | "azul";

export interface EmpresaCobranza {
  id: number;
  nombre: string;
  slug: string;
  activa: boolean;
  plan: string;
  suscripcion_vence: string | null;
  precio_mensual: number | null;
  /** ¿Tiene un precio especial cargado, o paga simplemente el de su plan? */
  precio_pactado: boolean;
  /**
   * El débito automático de Mercado Pago, o null si no tiene.
   *
   * Es la distinción que ordena el trabajo de cobranza: a quien paga solo no
   * hay que llamarlo ni revisarle el banco. Al que tiene un cobro rebotado
   * sí, y urgente — él todavía no lo sabe.
   */
  debito: {
    estado: string;
    cobros_fallidos: number;
    ultimo_error: string | null;
  } | null;
  razon_social: string | null;
  cuit: string | null;
  contacto_nombre: string | null;
  contacto_email: string | null;
  contacto_telefono: string | null;
  notas_admin: string | null;
  cantidad_usuarios: number;
  cantidad_recursos: number;
  limite_recursos: number | null;
  limite_sucursales: number | null;
  capacidad_excedida: boolean;
  ultimo_pago: string | null;
  semaforo_color: SemaforoColor;
  semaforo_dias_restantes: number | null;
  semaforo_fin_prorroga: string | null;
  semaforo_en_prorroga: boolean;
  semaforo_detalle: string;
  /** Estado centralizado, con su etiqueta y tono (los mismos que ve el negocio). */
  estado: EstadoSuscripcion;
  estado_etiqueta: string;
  estado_tono: TonoEstado;
  cancela_al_vencer: boolean;
  plan_programado: string | null;
}

/** Chips de filtro del panel de cobranza. "" = todas. */
export type FiltroCobranza =
  | ""
  | "en_revision"
  | "por_vencer"
  | "vencidas"
  | "al_dia"
  | "en_prueba"
  | "canceladas"
  | "sin_vencimiento";

export interface AlertaCobranza {
  nivel: "rojo" | "naranja" | "ambar" | "verde";
  filtro: FiltroCobranza | null;
  texto: string;
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
  /** Días de gracia después del vencimiento. Lo define el backend. */
  dias_prorroga: number;
  empresas_en_prueba: number;
  suscripciones_activas: number;
  pagos_en_revision: number;
  monto_en_revision: number;
  cancelaciones_mes: number;
  cancelaciones_programadas: number;
  pagos_rechazados: number;
  renovaciones_mes: number;
  alertas: AlertaCobranza[];
}

export interface PagoSuscripcion {
  id: number;
  fecha: string;
  monto: number;
  metodo: string;
  periodo_desde: string | null;
  periodo_hasta: string | null;
  notas: string | null;
  anulado?: boolean;
  anulado_por?: string | null;
  /** Presente = entró por Mercado Pago y se le puede preguntar a MP qué pasó. */
  mp_payment_id?: string | null;
}

/**
 * Lo que Mercado Pago dice HOY de una cuota que ya acreditamos.
 *
 * El webhook acredita solo y después esa fila no se vuelve a mirar nunca: si
 * el pago se devolvió o terminó en contracargo, MP lo sabe y el panel sigue
 * mostrando «cobrado». Esto es la consulta que cierra ese agujero.
 */
export interface VerificacionMP {
  pago_id: number;
  mp_payment_id: string | null;
  monto_registrado: number;
  anulado: boolean;
  /** false = no se pudo consultar; `motivo` dice por qué. */
  consultable: boolean;
  motivo: "sin_id" | "mp_apagado" | "sin_respuesta" | null;
  estado: string | null;
  estado_etiqueta: string | null;
  color: "verde" | "ambar" | "rojo" | "gris";
  monto_mp: number | null;
  /** El monto de MP coincide con el registrado. */
  coincide: boolean | null;
  /** null = no sabemos (no se pudo consultar). Nunca false por un error de red. */
  acreditado: boolean | null;
  detalle: string | null;
}

export function verificarPagoMP(pagoId: number): Promise<VerificacionMP> {
  return adminRequest<VerificacionMP>(`/admin/pagos/${pagoId}/verificar-mp`);
}

export function listarCobranza(filtros: {
  buscar?: string;
  color?: SemaforoColor | "";
  plan?: string;
  filtro?: FiltroCobranza;
} = {}): Promise<EmpresaCobranza[]> {
  const p = new URLSearchParams();
  if (filtros.buscar) p.set("buscar", filtros.buscar);
  if (filtros.filtro) p.set("filtro", filtros.filtro);
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
  datos: {
    monto: number;
    metodo: string;
    fecha?: string;
    notas?: string;
    renovar?: boolean;
    /**
     * A qué plan queda la empresa con este pago.
     *
     * Sin esto, una transferencia hecha PARA pasar a Pro se registraba como
     * cuota y dejaba al negocio en Inicial: cobrado el dinero, sin entregar lo
     * que compró. El plan viaja con el pago porque es parte del pago.
     */
    plan?: string;
    /**
     * Un id por apertura del diálogo. Un doble click o un reintento por red
     * devuelven el MISMO pago en vez de registrar dos cuotas.
     */
    clave_idempotencia?: string;
  },
): Promise<PagoSuscripcion> {
  return adminRequest<PagoSuscripcion>(`/admin/empresas/${empresaId}/pagos`, {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

/** Un movimiento del vencimiento de la suscripción (quién, cuándo, de qué fecha a cuál). */
export interface AjusteSuscripcion {
  id: number;
  /** pago | renovacion | prorroga | manual | reversion | plan | cancelacion | … */
  tipo: string;
  actor_tipo?: string | null;
  estado_antes?: string | null;
  estado_despues?: string | null;
  plan_antes?: string | null;
  plan_despues?: string | null;
  monto?: number | null;
  vence_antes: string | null;
  vence_despues: string | null;
  dias: number | null;
  detalle: string | null;
  hecho_por: string | null;
  creado_en: string | null;
  revertido: boolean;
  revertido_por: string | null;
  reversible: boolean;
  categoria?: string | null;
  motivo?: string | null;
}

/**
 * Un negocio que dijo "ya te transferí" y todavía no se confirmó.
 *
 * Viaja con TODO lo necesario para decidir sin abrir otra pantalla: lo que
 * avisó, lo que se le espera cobrar, en qué plan está y si los dos números
 * coinciden. Ese último campo es el que permite mirar la bandeja y saber
 * cuáles se confirman solos y cuáles hay que pensar.
 */
export interface AvisoPago {
  id: number;
  empresa_id: number;
  empresa_nombre: string;
  metodo: string;
  /** Lo que el negocio dijo que transfirió. Puede no haberlo cargado. */
  monto: number | null;
  referencia: string | null;
  /** Quién avisó, desde el panel del negocio. */
  avisado_por: string | null;
  creado_en: string | null;
  /** pendiente | info_solicitada | confirmada | rechazada. */
  estado: "pendiente" | "info_solicitada" | "confirmada" | "rechazada";
  /** Por qué se rechazó. Solo viene en las rechazadas. */
  motivo: string | null;
  resuelto: boolean;
  /** Lo que le corresponde pagar: su precio pactado, o el de su plan. */
  monto_esperado: number | null;
  plan_codigo: string;
  plan_etiqueta: string;
  vence: string | null;
  /** Avisó exactamente lo esperado. */
  coincide: boolean;
  /** El plan que tiene HOY (el del aviso es el que está comprando). */
  plan_actual_etiqueta: string;
  /** alta | renovacion | cambio_plan | reactivacion */
  tipo: string;
  tiene_comprobante: boolean;
  mensaje_admin: string | null;
  pago_id: number | null;
  resuelto_por: string | null;
  resuelto_en: string | null;
}

/** Aprueba la transferencia: registra la cuota UNA vez y cierra el aviso. */
export function aprobarAvisoPago(
  avisoId: number,
  datos: { monto?: number | null; fecha?: string | null; notas?: string | null },
): Promise<PagoSuscripcion> {
  return adminApi.post<PagoSuscripcion>(`/admin/cobranza/avisos/${avisoId}/aprobar`, {
    ...datos,
    confirmo: true,
  });
}

/** Le pide al negocio un dato más. El aviso sigue abierto. */
export function solicitarInfoAviso(avisoId: number, mensaje: string): Promise<{ ok: boolean }> {
  return adminApi.post(`/admin/cobranza/avisos/${avisoId}/solicitar-info`, { mensaje });
}

/**
 * El comprobante es privado: se pide con el token del admin y se muestra
 * como blob (no hay URL pública que se pueda compartir).
 */
export async function verComprobante(avisoId: number): Promise<string> {
  const token = getAdminToken();
  const res = await fetch(`${API_URL}/admin/cobranza/avisos/${avisoId}/comprobante`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "No se pudo abrir el comprobante");
  return URL.createObjectURL(await res.blob());
}

export function cancelarSuscripcionAdmin(
  empresaId: number,
  motivo: string | null,
): Promise<{ estado: string; activa_hasta: string | null }> {
  return adminApi.post(`/admin/empresas/${empresaId}/cancelar`, { motivo, confirmo: true });
}

export function reactivarSuscripcionAdmin(empresaId: number): Promise<{ estado: string }> {
  return adminApi.post(`/admin/empresas/${empresaId}/reactivar`, { confirmo: true });
}

export interface FilaAuditoria {
  id: number;
  creado_en: string | null;
  admin_email: string;
  accion: string;
  accion_etiqueta: string;
  empresa_id: number | null;
  empresa_nombre: string | null;
  descripcion: string | null;
  antes: Record<string, unknown> | null;
  despues: Record<string, unknown> | null;
  ip: string | null;
}

export function listarAuditoria(empresaId?: number, limite = 100): Promise<FilaAuditoria[]> {
  const q = new URLSearchParams({ limite: String(limite) });
  if (empresaId) q.set("empresa_id", String(empresaId));
  return adminApi.get<FilaAuditoria[]>(`/admin/auditoria?${q}`);
}

export function listarAvisosPago(soloPendientes = true): Promise<AvisoPago[]> {
  return adminRequest<AvisoPago[]>(
    `/admin/cobranza/avisos?pendientes=${soloPendientes}`,
  );
}

/**
 * Rechaza el aviso: sale de la bandeja SIN registrar cuota.
 *
 * El motivo viaja porque es lo que se le contesta al negocio cuando pregunta
 * por qué no le acreditaron el mes. Sin él, el aviso desaparecía y no quedaba
 * nada: ni quién lo rechazó, ni cuándo, ni por qué.
 */
export function descartarAvisoPago(
  avisoId: number,
  motivo?: string,
): Promise<{ ok: boolean }> {
  return adminRequest(`/admin/cobranza/avisos/${avisoId}/descartar`, {
    method: "POST",
    body: JSON.stringify({ motivo: motivo || null }),
  });
}

export function historialAjustes(empresaId: number): Promise<AjusteSuscripcion[]> {
  return adminRequest<AjusteSuscripcion[]>(`/admin/empresas/${empresaId}/ajustes`);
}

export function revertirAjuste(
  empresaId: number,
  ajusteId: number,
  motivo: string,
): Promise<{ ok: boolean; vence: string | null }> {
  return adminRequest(`/admin/empresas/${empresaId}/ajustes/${ajusteId}/revertir`, {
    method: "POST",
    body: JSON.stringify({ motivo }),
  });
}

export function darProrroga(
  empresaId: number,
  dias: number,
  motivo: string,
  categoria: "cortesia" | "incidencia",
): Promise<EmpresaCobranza> {
  return adminRequest<EmpresaCobranza>(`/admin/empresas/${empresaId}/prorroga`, {
    method: "POST",
    body: JSON.stringify({ dias, motivo, categoria }),
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
    limite_sucursales: number | null;
  }>,
): Promise<EmpresaCobranza> {
  return adminRequest<EmpresaCobranza>(`/admin/empresas/${empresaId}/ficha`, {
    method: "PUT",
    body: JSON.stringify(datos),
  });
}

/**
 * La ficha completa de un negocio: identidad, cobranza, uso y actividad.
 *
 * Viene todo junto y no en cuatro llamadas porque la pregunta es UNA —«¿cómo
 * está este cliente?»— y las respuestas parciales invitan a concluir con la
 * mitad de los datos: un negocio al día que hace tres meses no carga un turno
 * no es un buen cliente, es uno que se va a ir.
 */
export interface FichaEmpresa {
  id: number;
  nombre: string;
  slug: string;
  rubro: string | null;
  activa: boolean;
  creada_en: string | null;
  antiguedad_dias: number | null;
  plan: {
    codigo: string;
    etiqueta: string;
    resumen: string;
    /** null en los planes sin precio de lista (gratuito, a medida). */
    precio: number | null;
    /** El precio salió de la ficha comercial y no de la grilla. */
    precio_pactado: boolean;
  };
  suscripcion: {
    estado: string;
    vence: string | null;
    prueba_hasta: string | null;
    color: "verde" | "amarillo" | "rojo" | "gris" | "azul";
    detalle: string;
    dias_restantes: number | null;
    en_prorroga: boolean;
    estado_base: EstadoSuscripcion;
    etiqueta: string;
    tono: TonoEstado;
    reservas_abiertas: boolean;
    plan_programado: string | null;
    cancela_al_vencer: boolean;
    cancelacion_motivo: string | null;
    cancelacion_solicitada_en: string | null;
  };
  cobranza: {
    pagos: number;
    total_cobrado: number;
    ultimo_pago: { fecha: string; monto: number; metodo: string } | null;
    aviso_pendiente: {
      id: number;
      monto: number | null;
      referencia: string | null;
      creado_en: string | null;
    } | null;
  };
  uso: {
    profesionales: { usados: number; tope: number | null };
    usuarios: { usados: number; tope: number | null };
    sucursales: { usados: number; tope: number | null };
    clientes: number;
    servicios: number;
  };
  actividad: {
    turnos_30d: number;
    ultimo_turno: string | null;
    visitas_30d: number;
    visitas_por_dia: { dia: string; visitas: number }[];
  };
  contacto: {
    nombre: string | null;
    email: string | null;
    telefono: string | null;
    razon_social: string | null;
    cuit: string | null;
  };
  notas_admin: string | null;
}

export function fichaEmpresa(empresaId: number): Promise<FichaEmpresa> {
  return adminRequest<FichaEmpresa>(`/admin/empresas/${empresaId}/ficha`);
}


// ---------- La marca de Turnos360 ----------

/** El logo cargado por el super-admin. null = se usa el archivo del repo. */
export function leerMarca(): Promise<{ logo_url: string | null }> {
  return adminApi.get<{ logo_url: string | null }>("/admin/marca");
}

/** Guarda el logo. `null` o vacío borra el override y vuelve al del repo. */
export function guardarMarca(logoUrl: string | null): Promise<{ logo_url: string | null }> {
  return adminApi.put<{ logo_url: string | null }>("/admin/marca", {
    logo_url: logoUrl,
  });
}

// ══════════════════════════════════════════════════════════════════════
//  Finanzas del super-admin (routers/admin_finanzas.py)
// ══════════════════════════════════════════════════════════════════════

const qs = (p: Record<string, string | number | boolean | null | undefined>) => {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
};

export type EstadoOperacion =
  | "pendiente" | "en_revision" | "acreditado" | "rechazado" | "cancelado" | "anulado"
  | "reembolso_solicitado" | "reembolso_parcial" | "reembolso_total";

export interface Operacion {
  clave: string;
  tipo: "pago" | "transferencia_informada" | "intento_mp";
  id: number;
  empresa_id: number;
  empresa: string;
  concepto: string;
  monto: number;
  moneda: string;
  creado_en: string | null;
  fecha: string | null;
  acreditado_en: string | null;
  metodo: string;
  estado: EstadoOperacion;
  estado_etiqueta: string;
  id_proveedor: string | null;
  referencia: string | null;
  devuelto: number;
  conciliado: boolean;
  comision: number | null;
  motivo?: string | null;
}

export interface FiltrosCobros {
  desde?: string;
  hasta?: string;
  empresa_id?: number | null;
  metodo?: string;
  estado?: string;
  monto_min?: number | null;
  monto_max?: number | null;
  buscar?: string;
  pagina?: number;
  limite?: number;
}

export interface ListaCobros {
  total: number;
  pagina: number;
  limite: number;
  filas: Operacion[];
  sumas: { acreditado: number; en_revision: number; pendiente: number; rechazado: number; devuelto: number };
}

export function listarCobros(f: FiltrosCobros): Promise<ListaCobros> {
  return adminApi.get<ListaCobros>(`/admin/cobros${qs({ ...f })}`);
}

/** Descarga el CSV con la sesión de admin (no es un link público). */
export async function descargarCsv(ruta: string, nombre: string): Promise<void> {
  const res = await fetch(`${API_URL}${ruta}`, { headers: { Authorization: `Bearer ${getAdminToken() ?? ""}` } });
  if (!res.ok) throw new ApiError(res.status, "No se pudo exportar.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function exportarCobros(f: FiltrosCobros): Promise<void> {
  const { pagina: _p, limite: _l, ...resto } = f;
  void _p;
  void _l;
  return descargarCsv(`/admin/cobros/exportar${qs({ ...resto })}`, "turnos360-cobros.csv");
}

export interface Devolucion {
  id: number;
  monto: number;
  metodo: "mercadopago" | "manual";
  estado: "solicitada" | "en_proceso" | "aprobada" | "rechazada";
  motivo: string;
  referencia: string | null;
  mp_refund_id: string | null;
  error: string | null;
  origen: string;
  solicitada_por: string | null;
  solicitada_en: string | null;
  confirmada_en: string | null;
}

export interface DetallePago {
  id: number;
  empresa_id: number;
  empresa: string;
  concepto: string;
  monto: number;
  moneda: string;
  metodo: string;
  fecha: string | null;
  creado_en: string | null;
  registrado_por: string | null;
  periodo_desde: string | null;
  periodo_hasta: string | null;
  notas: string | null;
  mp_payment_id: string | null;
  comision: number | null;
  neto: number | null;
  estado: EstadoOperacion;
  estado_etiqueta: string;
  anulado: boolean;
  anulado_en: string | null;
  anulado_por: string | null;
  anulado_motivo: string | null;
  conciliado: boolean;
  conciliado_en: string | null;
  conciliado_por: string | null;
  referencia_banco: string | null;
  devuelto: number;
  devolucion_pendiente: number;
  devolvible: number;
  devoluciones: Devolucion[];
  historial: { fecha: string | null; tipo: string; detalle: string | null; hecho_por: string | null; revertido: boolean }[];
  aviso: { id: number; referencia: string | null; resuelto_por: string | null; resuelto_en: string | null; tiene_comprobante: boolean } | null;
  acciones: { devolver_mp: boolean; devolver_manual: boolean; conciliar: boolean; anular: boolean };
}

export const verPago = (id: number) => adminApi.get<DetallePago>(`/admin/pagos/${id}`);
export const devolverPago = (
  id: number,
  d: { monto: number; motivo: string; referencia?: string; confirmada?: boolean; clave: string },
) => adminApi.post<DetallePago>(`/admin/pagos/${id}/devolver`, d);
export const confirmarDevolucion = (id: number, referencia: string) =>
  adminApi.post<DetallePago>(`/admin/devoluciones/${id}/confirmar`, { referencia });
export const refrescarDevolucion = (id: number) => adminApi.post<DetallePago>(`/admin/devoluciones/${id}/refrescar`, {});
export const conciliarPago = (id: number, conciliado: boolean, referencia?: string) =>
  adminApi.post<DetallePago>(`/admin/pagos/${id}/conciliar`, { conciliado, referencia: referencia ?? null });
export const anularPago = (id: number, motivo: string) => adminApi.post<DetallePago>(`/admin/pagos/${id}/anular`, { motivo });
export const anularIntento = (id: number, motivo: string) =>
  adminApi.post<{ id: number; estado: string }>(`/admin/intentos/${id}/anular`, { motivo });

export interface TotalesCaja {
  cobros: number;
  transferencias_verificadas: number;
  mercadopago: number;
  devoluciones: number;
  comisiones: number;
  pagos_mp_sin_comision: number;
  neto: number;
  sin_conciliar: { cantidad: number; monto: number };
  conciliado: number;
  por_metodo: Record<string, { cobros: number; devoluciones: number }>;
  cantidad_cobros: number;
  cantidad_devoluciones: number;
}

export interface Cierre {
  id: number;
  desde: string;
  hasta: string;
  estado: "borrador" | "cerrado" | "reabierto" | "anulado";
  totales: TotalesCaja & { saldo_inicial: number; saldo_final: number };
  observaciones: string | null;
  preparado_por: string;
  preparado_en: string | null;
  cerrado_por: string | null;
  cerrado_en: string | null;
  reabierto_por: string | null;
  reabierto_en: string | null;
  motivo_reapertura: string | null;
}

export interface Caja {
  desde: string;
  hasta: string;
  saldo_inicial: number;
  totales: TotalesCaja;
  saldo_final: number;
  es_calculado: boolean;
  ingresos: { pago_id: number; fecha: string; empresa: string; concepto: string; metodo: string; monto: number; comision: number | null; conciliado: boolean; referencia: string | null }[];
  devoluciones: { devolucion_id: number; pago_id: number; fecha: string; empresa: string; metodo: string; monto: number; referencia: string | null }[];
  cierre: Cierre | null;
  diferencias_con_cierre: Record<string, number> | null;
}

export const verCaja = (desde: string, hasta: string) => adminApi.get<Caja>(`/admin/caja${qs({ desde, hasta })}`);
export const listarCierres = () => adminApi.get<Cierre[]>("/admin/cierres");
export const prepararCierre = (desde: string, hasta: string, observaciones?: string) =>
  adminApi.post<Cierre>("/admin/cierres", { desde, hasta, observaciones: observaciones || null });
export const confirmarCierre = (id: number, observaciones?: string) =>
  adminApi.post<Cierre>(`/admin/cierres/${id}/confirmar`, { observaciones: observaciones ?? null });
export const reabrirCierre = (id: number, motivo: string) => adminApi.post<Cierre>(`/admin/cierres/${id}/reabrir`, { motivo });
export const descartarCierre = (id: number) => adminApi.post<Cierre>(`/admin/cierres/${id}/descartar`, {});

export interface PuntoEstadistica {
  periodo: string;
  bruto: number;
  devoluciones: number;
  comisiones: number;
  neto: number;
  cobros: number;
  renovaciones: number;
  altas: number;
  pendientes: number;
  rechazados: number;
  cancelaciones: number;
}

export interface Estadisticas {
  granularidad: "semana" | "mes";
  desde: string;
  hasta: string;
  serie: PuntoEstadistica[];
  total: Omit<PuntoEstadistica, "periodo">;
  anterior: Omit<PuntoEstadistica, "periodo">;
  variacion: Record<string, number | null>;
  suscripciones_activas_hoy: number;
  definiciones: Record<string, string>;
  /** Días dados sin cobrar. Indicador comercial: no es plata. */
  beneficios?: {
    serie: { periodo: string; dias_cortesia: number; dias_incidencia: number; dias_sin_clasificar: number; ajustes: number; empresas: number }[];
    total: { dias_cortesia: number; dias_incidencia: number; dias_sin_clasificar: number; ajustes: number; empresas: number };
    nota: string;
  };
}

export const verEstadisticas = (granularidad: string, desde?: string, hasta?: string) =>
  adminApi.get<Estadisticas>(`/admin/estadisticas${qs({ granularidad, desde, hasta })}`);
export const exportarEstadisticas = (granularidad: string, desde?: string, hasta?: string) =>
  descargarCsv(`/admin/estadisticas/exportar${qs({ granularidad, desde, hasta })}`, `turnos360-estadisticas-${granularidad}.csv`);

export interface EventoMPAdmin {
  recibido_en: string;
  tipo: string;
  accion: string | null;
  resultado: string;
  detalle: string | null;
}

export interface EstadoMP {
  configurado: boolean;
  entorno: "pruebas" | "produccion_o_usuario_de_prueba" | null;
  webhook_secreto: boolean;
  firma_modo: string;
  webhook_url: string;
  ultimo_evento: EventoMPAdmin | null;
  ultimo_procesado: EventoMPAdmin | null;
  errores_recientes: EventoMPAdmin[];
  intentos_pendientes_24h: number;
  pagos_mp_sin_conciliar: number;
  devoluciones_abiertas: number;
  comprobado: boolean;
  falta_comprobar: string[];
}

export const estadoMercadoPago = () => adminApi.get<EstadoMP>("/admin/integraciones/mercadopago");

export interface PlanAdmin {
  codigo: string;
  etiqueta: string;
  precio: number | null;
  profesionales: number | null;
  usuarios: number | null;
  sucursales: number;
  se_vende_solo: boolean;
  funciones: string[];
  empresas: number;
  por_estado: Record<string, number>;
}

export const listarPlanes = () => adminApi.get<PlanAdmin[]>("/admin/planes");

export interface ResumenGeneral {
  desde: string;
  hasta: string;
  empresas: { total: number; activas: number; inactivas: number };
  suscripciones: { por_estado: Record<string, number>; activas: number; por_vencer_7d: number };
  periodo: {
    acreditado: number;
    cantidad_cobros: number;
    devoluciones: number;
    comisiones: number;
    neto: number;
    en_revision: number;
    pendiente: number;
    rechazado: number;
  };
  transferencias_en_revision: number;
  devoluciones_pendientes: { cantidad: number; monto: number };
  serie_semanal: PuntoEstadistica[];
  alertas: { tipo: "aviso" | "info" | "error"; texto: string; href: string }[];
}

export const resumenGeneral = (desde?: string, hasta?: string) =>
  adminApi.get<ResumenGeneral>(`/admin/resumen${qs({ desde, hasta })}`);

export interface UsuarioGlobal {
  id: number;
  nombre: string;
  email: string;
  rol: RolUsuario;
  activo: boolean;
  email_verificado: boolean;
  empresa_id: number;
  empresa: string;
  sucursal: string | null;
  restablecimiento_pendiente: boolean;
  activacion_pendiente?: boolean;
  ultimo_ingreso_en?: string | null;
}

export const listarUsuariosGlobal = (f: { buscar?: string; empresa_id?: number; rol?: string; activo?: boolean; pagina?: number }) =>
  adminApi.get<{ total: number; pagina: number; limite: number; filas: UsuarioGlobal[] }>(`/admin/usuarios${qs({ ...f })}`);
export const cambiarAccesoUsuario = (id: number, activo: boolean, motivo?: string) =>
  adminApi.post<{ id: number; activo: boolean }>(`/admin/usuarios/${id}/acceso`, { activo, motivo: motivo || null });
export const restablecerClaveUsuario = (id: number, cerrar_sesiones: boolean) =>
  adminApi.post<{ ok: boolean; detalle: string; sesiones_cerradas: boolean }>(`/admin/usuarios/${id}/restablecer`, { cerrar_sesiones });

export function listarAuditoriaFiltrada(f: {
  empresa_id?: number;
  accion?: string;
  admin_email?: string;
  desde?: string;
  hasta?: string;
  limite?: number;
}): Promise<FilaAuditoria[]> {
  return adminApi.get<FilaAuditoria[]>(`/admin/auditoria${qs({ ...f })}`);
}

// ---------- Sesiones, actividad e invitaciones ----------
export interface SesionAdmin {
  id: number;
  creada_en: string | null;
  ultimo_uso_en: string | null;
  expira_en: string | null;
  dispositivo: string | null;
  estado: "activa" | "revocada" | "invalidada" | "vencida";
  revocada_en: string | null;
  motivo: string | null;
  revocada_por: string | null;
}
export interface ActividadUsuario {
  usuario: {
    id: number; nombre: string; email: string; rol: RolUsuario; activo: boolean;
    empresa_id: number; empresa: string | null; ultimo_ingreso_en: string | null; activacion_pendiente: boolean;
  };
  invitacion: EstadoInvitacion | null;
  activas: number;
  sesiones: SesionAdmin[];
  historial: { fecha: string | null; tipo: "ingreso" | "cierre"; detalle: string; por: string | null }[];
  notas: string[];
}
export const verActividad = (id: number) => adminApi.get<ActividadUsuario>(`/admin/usuarios/${id}/sesiones`);
export const revocarSesion = (id: number, sesionId: number, motivo: string) =>
  adminApi.post<ActividadUsuario>(`/admin/usuarios/${id}/sesiones/${sesionId}/revocar`, { motivo });
export const cerrarTodasLasSesiones = (id: number, motivo: string) =>
  adminApi.post<ActividadUsuario>(`/admin/usuarios/${id}/cerrar-sesiones`, { motivo });
export const reenviarInvitacion = (id: number) =>
  adminApi.post<EstadoInvitacion>(`/admin/usuarios/${id}/invitacion/reenviar`, {});
export const revocarInvitacion = (id: number) =>
  adminApi.post<EstadoInvitacion>(`/admin/usuarios/${id}/invitacion/revocar`, {});

// ---------- Evolución de suscripciones y ajustes administrativos ----------
export interface PuntoEvolucion {
  periodo: string; desde: string; hasta: string;
  activas_al_cierre: number | null;
  nuevas: number; reactivadas: number; vencimientos: number; cancelaciones: number; pruebas_vencidas: number; cambios_de_plan: number;
  dias_con_datos: number; dias: number; dias_reconstruidos: number;
}
export interface EvolucionSuscripciones {
  granularidad: "dia" | "semana" | "mes";
  desde: string; hasta: string;
  confiable_desde: string | null;
  serie: PuntoEvolucion[];
  total: Record<string, number | null>;
  anterior: Record<string, number | null>;
  variacion: Record<string, number | null>;
  cambios_de_plan: { cambio: string; cantidad: number }[];
  definiciones: Record<string, string>;
}
export const verEvolucion = (granularidad: string, desde?: string, hasta?: string) =>
  adminApi.get<EvolucionSuscripciones>(`/admin/suscripciones/evolucion${qs({ granularidad, desde, hasta })}`);
export const tomarFotoSuscripciones = () =>
  adminApi.post<{ fecha: string; fotos: number; reconstruidas: number; transiciones: number }>("/admin/suscripciones/foto", {});

export interface AjusteAdmin {
  id: number; empresa_id: number; empresa: string | null; fecha: string | null;
  tipo: string; tipo_etiqueta: string; categoria: string | null; categoria_etiqueta: string; clasificado: boolean;
  vence_antes: string | null; vence_despues: string | null; dias: number | null;
  plan_antes: string | null; plan_despues: string | null;
  hecho_por: string | null; actor: string | null; motivo: string | null; detalle: string | null;
  estado: "vigente" | "revertido"; revertido_por: string | null; pago_id: number | null;
}
export const listarAjustesAdmin = (f: {
  empresa_id?: number; admin_email?: string; categoria?: string; desde?: string; hasta?: string; pagina?: number;
}) => adminApi.get<{ total: number; pagina: number; limite: number; filas: AjusteAdmin[]; categorias: Record<string, string> }>(
  `/admin/ajustes${qs({ ...f })}`,
);
