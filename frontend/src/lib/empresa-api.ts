/**
 * Configuración de la empresa logueada: su rubro y el preset.
 * El preset define qué módulos se muestran y cómo se nombran las cosas.
 */

import { api } from "./api";
import type { TemaVidriera } from "./tema-vidriera";

export interface PresetRubro {
  terminologia?: Record<string, string>;
  modulos?: Record<string, boolean>;
  campos_cliente?: Array<{ clave: string; etiqueta: string; tipo: string }>;
  [clave: string]: unknown;
}

export interface ConfigEmpresa {
  id: number;
  nombre: string;
  slug: string;
  rubro_codigo: string;
  rubro_nombre: string;
  preset: PresetRubro;
  /**
   * Cuántos locales permite el plan. Con 1, el panel esconde TODO lo de
   * sucursales: el menú, los selectores y el paso de la reserva pública.
   * Por debajo el sistema ya es multisucursal — esto es lo único que decide
   * si la palabra aparece en pantalla.
   */
  limite_sucursales: number;
  /** El plan contratado, para el pie de la barra lateral. */
  plan_codigo: string;
  plan_etiqueta: string;
  /**
   * Las funciones que ese plan incluye. Lo que NO está acá se muestra con
   * candado y con a dónde ir para tenerlo — esconderlo no lo vende, y además
   * deja al dueño sin saber que existe.
   */
  funciones: FuncionDePlan[];
}

/** Espejo de `Funcion` en backend/app/core/planes.py. */
export type FuncionDePlan =
  | "membresias"
  | "gift_cards"
  | "cupones"
  | "campanas"
  | "comisiones"
  | "whatsapp"
  | "multisucursal"
  | "estadisticas_avanzadas";

/** Trae la empresa actual + el preset de su rubro (GET /empresa/actual). */
export function obtenerConfigEmpresa(): Promise<ConfigEmpresa> {
  return api.get<ConfigEmpresa>("/empresa/actual");
}

// === Landing pública ("Mi página") ===

/** Una franja horaria: [abre, cierra], ej. ["09:00", "13:00"]. */
export type Franja = [string, string];

/** Horarios visibles por día (clave: lun..dom). Día ausente o [] = cerrado.
 *  Solo para mostrar en la landing; NO calcula huecos reservables. */
export type HorariosAtencion = Record<string, Franja[]>;

/** Links de redes. Claves conocidas + libres (sumar una red = agregar clave). */
export interface Redes {
  instagram?: string;
  facebook?: string;
  tiktok?: string;
  linkedin?: string;
  sitio_web?: string;
  [red: string]: string | undefined;
}

export interface LandingConfig {
  descripcion: string | null;
  direccion: string | null;
  telefono_publico: string | null;
  email_publico: string | null;
  logo_url: string | null;
  /** Foto de fondo de la cabecera de la vidriera. */
  portada_url: string | null;
  color_marca: string | null;
  horarios_atencion: HorariosAtencion | null;
  redes: Redes;
  /** Galería de la landing: lista de URLs de fotos (máx. 12). */
  galeria: string[];  /** El look de la página (ver lib/tema-vidriera.ts). */
  tema?: Partial<TemaVidriera>;
}

/** Contenido actual de la landing del negocio (GET /empresa/landing). */
export function obtenerLanding(): Promise<LandingConfig> {
  return api.get<LandingConfig>("/empresa/landing");
}

/** Guarda el contenido de la landing (PUT /empresa/landing). Solo dueño. */
export function guardarLanding(datos: LandingConfig): Promise<LandingConfig> {
  return api.put<LandingConfig>("/empresa/landing", datos);
}

// ============================================================
// Reglas de la reserva pública (solo dueño)
// ============================================================

export interface ReglasReserva {
  /** Minutos mínimos entre "ahora" y el turno. 0 = sin restricción. */
  anticipacion_min: number;
  /** Días hacia adelante que se puede reservar. */
  dias_max: number;
  /** Cierre fijo de agenda (yyyy-MM-dd). Manda la más restrictiva. */
  fecha_limite: string | null;
  permite_cancelar: boolean;
  pide_telefono: boolean;
  pide_nacimiento: boolean;
}

export function leerReglasReserva(): Promise<ReglasReserva> {
  return api.get<ReglasReserva>("/empresa/reglas-reserva");
}

export function guardarReglasReserva(datos: ReglasReserva): Promise<ReglasReserva> {
  return api.put<ReglasReserva>("/empresa/reglas-reserva", datos);
}

// ============================================================
// Mi suscripción (solo dueño)
// ============================================================

export interface PagoSuscripcion {
  fecha: string | null;
  monto: number;
  metodo: string;
  periodo_desde: string | null;
  periodo_hasta: string | null;
}

export interface DatosCobro {
  cbu: string | null;
  alias: string | null;
  titular: string | null;
  cuit: string | null;
  banco: string | null;
  mp_link: string | null;
  whatsapp: string | null;
  /** ¿El servidor tiene la cuenta de Mercado Pago de Turnos360 configurada? */
  mp_checkout: boolean;
}

export interface MiSuscripcion {
  plan: string;
  /** activa | prorroga | vencida | sin_vencimiento */
  estado: string;
  vence: string | null;
  dias_restantes: number | null;
  en_prorroga: boolean;
  mensaje: string;
  /** Hasta cuándo puede pagar sin que se corte (vencimiento + gracia). */
  corte: string | null;
  dias_hasta_corte: number | null;
  /**
   * LA CUOTA, resuelta por el servidor: el precio pactado si lo hay, y si no
   * el del plan. La pantalla NO tiene que volver a resolver esa regla — lo
   * hacía, y por eso mostraba «$14.990» arriba de una grilla que decía otra
   * cosa. null = no le corresponde pagar (prueba, o Enterprise sin pactar).
   */
  cuota: number | null;
  /** De dónde salió `cuota`: "pactada" | "plan" | "sin_precio". */
  cuota_origen: string;
  /** Alias histórico de `cuota`. Dice lo mismo. */
  precio_mensual: number | null;
  /** ¿Tiene un precio especial cargado? Si no, paga simplemente el de su plan. */
  precio_pactado: boolean;
  dias_prorroga: number;
  ultimo_monto: number | null;
  /** Precio de lista vigente (config del servidor). Solo para el aviso de la prueba. */
  precio_lista: number | null;
  /** El precio del plan de entrada: a lo que cae quien termina la prueba. */
  precio_entrada: number | null;
  pagos: PagoSuscripcion[];
  cobro: DatosCobro;
  /** Qué incluye el plan actual y cuánto se está usando. */
  plan_etiqueta: string | null;
  plan_resumen: string | null;
  profesionales_usados: number;
  /** null = sin tope (plan Multi). */
  profesionales_tope: number | null;
  grilla: PlanDeLaGrilla[];
  /** El plan en código: con esto la pantalla sabe cuál columna es la suya. */
  plan_codigo: string;
  /** Baja anotada para el fin del ciclo. null = no hay ninguna. */
  plan_programado: string | null;
  plan_programado_etiqueta: string | null;
  /** Sin token del SaaS no hay botón de pago: solo transferencia. */
  mp_disponible: boolean;
  /** null = no tiene débito automático, y la pantalla ofrece activarlo. */
  debito: DebitoAutomatico | null;
  /** ¿Se puede activar el débito automático en este entorno? */
  debito_disponible: boolean;
}

/**
 * El débito automático: la cuota se cobra sola todos los meses.
 *
 * Nunca trae datos de la tarjeta —ni los últimos cuatro dígitos—: la tarjeta
 * vive en Mercado Pago y ahí se queda.
 */
export interface DebitoAutomatico {
  /** pending | authorized | paused | cancelled, tal cual lo dice Mercado Pago. */
  estado: string;
  etiqueta: string;
  color: string;
  detalle: string;
  plan: string | null;
  plan_etiqueta: string | null;
  monto: number | null;
  proximo_cobro: string | null;
  desde: string | null;
  /** Cobros seguidos que salieron rechazados. > 0 = hay que avisar YA. */
  cobros_fallidos: number;
  /** El motivo del último rechazo, en las palabras de Mercado Pago. */
  ultimo_error: string | null;
}

export interface PlanDeLaGrilla {
  codigo: string;
  etiqueta: string;
  precio: number;
  /** null = ilimitados. */
  profesionales: number | null;
  usuarios: number | null;
  sucursales: number;
  resumen: string;
  para_quien: string;
  /**
   * Sin precio de lista: no se contrata online. La pantalla muestra
   * «Hablemos» con el link a WhatsApp en vez de un botón de pago.
   */
  a_convenir: boolean;
}

/** Qué pasó al pedir un cambio de plan. */
export interface CambioDePlan {
  /**
   * - `pagar`: subió, hay que ir al checkout (viene `url`).
   * - `pagar_transferencia`: subió pero MP está apagado; paga por transferencia.
   * - `programada`: bajó; se aplica al vencer el ciclo pago (viene `desde`).
   * - `aplicada`: bajó y no había ciclo pago que respetar.
   * - `cancelada`: eligió el plan que ya tiene y se anuló la baja anotada.
   * - `ninguna`: ya estaba en ese plan.
   */
  accion:
    | "pagar"
    | "pagar_transferencia"
    | "programada"
    | "aplicada"
    | "cancelada"
    | "ninguna";
  url?: string;
  desde?: string;
  detalle?: string;
}

/**
 * Pide el cambio de plan.
 *
 * SUBIR no activa nada acá: devuelve el link de pago y el plan se activa
 * cuando la plata entra de verdad, por el webhook de Mercado Pago. Si se
 * activara al pedirlo, cualquiera subiría a Multi, cerraría el checkout y se
 * quedaría con el plan gratis.
 */
export function cambiarPlan(plan: string): Promise<CambioDePlan> {
  return api.post<CambioDePlan>("/empresa/suscripcion/cambiar-plan", { plan });
}

export function leerMiSuscripcion(): Promise<MiSuscripcion> {
  return api.get<MiSuscripcion>("/empresa/mi-suscripcion");
}

/** Arranca el pago de la cuota con Checkout de Mercado Pago. Devuelve la URL. */
export function pagarSuscripcionMP(plan?: string): Promise<{ url: string }> {
  const q = plan ? `?plan=${encodeURIComponent(plan)}` : "";
  return api.post<{ url: string }>(`/empresa/suscripcion/pagar-mp${q}`, {});
}

/**
 * Activa el débito automático. Devuelve la URL del checkout de Mercado Pago
 * donde el dueño carga la tarjeta — que nunca pasa por acá.
 */
export function activarDebitoAutomatico(plan: string): Promise<{ url: string }> {
  return api.post<{ url: string }>(
    `/empresa/suscripcion/debito-automatico?plan=${encodeURIComponent(plan)}`,
    {},
  );
}

/**
 * Le pregunta a Mercado Pago cómo quedó la suscripción, ahora. Se llama al
 * volver del checkout: sin esto, el que acaba de poner la tarjeta vuelve y la
 * pantalla le dice que le falta ponerla.
 */
export function sincronizarDebitoAutomatico(): Promise<{ estado: string | null }> {
  return api.post<{ estado: string | null }>(
    "/empresa/suscripcion/debito-automatico/sincronizar",
    {},
  );
}

/** Corta el débito. El servicio sigue hasta el final del mes ya cobrado. */
export function cancelarDebitoAutomatico(): Promise<{ ok: boolean }> {
  return api.delete<{ ok: boolean }>("/empresa/suscripcion/debito-automatico");
}

/** "Ya te transferí". Queda pendiente de que lo confirmemos contra el banco. */
export function avisarPagoSuscripcion(datos: {
  monto?: number | null;
  referencia?: string | null;
}): Promise<{ detalle: string }> {
  return api.post<{ detalle: string }>("/empresa/suscripcion/aviso-pago", datos);
}

export function leerAvisoPago(): Promise<{
  pendiente: boolean;
  creado_en?: string | null;
  monto?: number | null;
}> {
  return api.get("/empresa/suscripcion/aviso-pago");
}

// ============================================================
// Seguimiento publicitario (Meta Pixel / Google Tag, solo dueño)
// ============================================================

export interface SeguimientoConfig {
  meta_pixel_id: string | null;
  google_tag_id: string | null;
  /**
   * Etiqueta de conversión de Google Ads. Solo aplica con un tag AW-.
   * Sin ella, Ads mide visitas pero no cuenta una sola conversión.
   */
  google_conversion_label: string | null;
}

export function leerSeguimiento(): Promise<SeguimientoConfig> {
  return api.get<SeguimientoConfig>("/empresa/seguimiento");
}

export function guardarSeguimiento(
  datos: SeguimientoConfig,
): Promise<SeguimientoConfig> {
  return api.put<SeguimientoConfig>("/empresa/seguimiento", datos);
}

// ============================================================
// Señas con Mercado Pago (config del negocio, solo dueño)
// ============================================================

export interface CuentaMP {
  id: number | null;
  nombre: string;
  email: string;
  pais: string;
}

export interface SenasConfig {
  sena_activa: boolean;
  sena_monto: number | null;
  cobro_modo: "ninguno" | "sena" | "total";
  mp_conectado: boolean;
  /**
   * A qué cuenta de Mercado Pago quedó conectado. "Conectado ✓" a secas no
   * dice nada: el dueño tiene que poder ver que es SU cuenta y no otra.
   */
  mp_cuenta: CuentaMP | null;
}

/** Revalida contra Mercado Pago el token ya guardado. */
export function probarSenas(): Promise<{ ok: boolean; cuenta: CuentaMP }> {
  return api.post<{ ok: boolean; cuenta: CuentaMP }>("/empresa/senas/probar", {});
}

export function obtenerSenas(): Promise<SenasConfig> {
  return api.get<SenasConfig>("/empresa/senas");
}

/** El token solo viaja si se está cargando uno nuevo (nunca se lee de vuelta). */
export function guardarSenas(datos: {
  sena_activa: boolean;
  sena_monto: number | null;
  cobro_modo: "ninguno" | "sena" | "total";
  mp_access_token?: string;
}): Promise<SenasConfig> {
  return api.put<SenasConfig>("/empresa/senas", datos);
}


// ============================================================
// Campañas / automatizaciones (solo dueño)
// ============================================================

export interface AutomSwitch {
  activa: boolean;
}

/**
 * Un recordatorio, con cuántas horas antes sale.
 *
 * Las horas vienen de una lista cerrada (HORAS_RECORDATORIO en el backend):
 * el barrido arma una consulta por cada valor en uso, y con un entero libre
 * serían tantas consultas como empresas.
 */
export interface AutomRecordatorio extends AutomSwitch {
  horas_antes: number;
}

export interface AutomCumple extends AutomSwitch {
  dias_antes: number;
  /** Vacío = el asunto que escribimos nosotros. */
  asunto: string;
  mensaje: string;
}

export interface AutomResena extends AutomSwitch {
  link: string;
  /** Cuánto esperar después del turno antes de pedirla. */
  horas_despues: number;
}

export interface AutomInactivos extends AutomSwitch {
  dias: number;
  asunto: string;
  mensaje: string;
  /** Visitas previas mínimas para entrar en la campaña. */
  min_visitas: number;
}

export interface Automatizaciones {
  /** Las claves son identificadores de ranura, no las horas: quedaron de
   *  cuando el recordatorio era fijo. Las horas están en `horas_antes`. */
  recordatorio_24h: AutomRecordatorio;
  recordatorio_2h: AutomRecordatorio;
  cumple: AutomCumple;
  resena_google: AutomResena;
  inactivos: AutomInactivos;
}

/** Las anticipaciones que se pueden elegir. Espejo del backend. */
export const HORAS_RECORDATORIO = [48, 24, 12, 6, 3, 2, 1];

export function obtenerAutomatizaciones(): Promise<Automatizaciones> {
  return api.get<Automatizaciones>("/empresa/automatizaciones");
}

export function guardarAutomatizaciones(datos: Automatizaciones): Promise<Automatizaciones> {
  return api.put<Automatizaciones>("/empresa/automatizaciones", datos);
}


/**
 * Manda una muestra de la campaña al email del usuario que la pide.
 *
 * Sin parámetro `destino`: el backend lo decide y lo ignora si viene. Cuando
 * era un campo libre, con una cuenta de prueba gratuita se podía mandar
 * cualquier contenido a cualquier casilla desde el remitente oficial de
 * Turnos360 —phishing con nuestra marca— y de paso quemar la cuota diaria de
 * envíos que comparten todos los negocios.
 */
export function probarCampana(tipo: string): Promise<{ detalle: string }> {
  return api.post<{ detalle: string }>(
    `/empresa/automatizaciones/probar?tipo=${encodeURIComponent(tipo)}`,
    {},
  );
}

export interface Suscripcion {
  plan: string;
  /**
   * Los CINCO estados que devuelve `estado_suscripcion()` en el backend.
   * "prueba" se evalúa PRIMERO allá (services/suscripcion.py). Si falta en
   * este union, TypeScript no avisa cuando una pantalla no lo contempla y
   * el error aparece recién en runtime.
   */
  estado: "prueba" | "activa" | "prorroga" | "vencida" | "sin_vencimiento";
  vence: string | null;
  dias_restantes: number | null;
  en_prorroga: boolean;
  mensaje: string;
  /** Hasta cuándo puede pagar sin que se corte (vencimiento + gracia). */
  corte: string | null;
  dias_hasta_corte: number | null;
}

export function obtenerSuscripcion(): Promise<Suscripcion> {
  return api.get<Suscripcion>("/empresa/suscripcion");
}
