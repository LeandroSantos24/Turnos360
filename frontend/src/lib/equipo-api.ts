/**
 * El equipo del negocio: quién tiene cuenta y quién puede recuperar su clave.
 *
 * Solo el dueño. El candado real está en el backend (gate_dueno en el router
 * de equipo); esto es la puerta de entrada desde el panel.
 */

import { api } from "./api";

export type RolUsuario = "dueno" | "admin" | "recepcion" | "profesional";

export interface MiembroEquipo {
  id: number;
  nombre: string;
  email: string;
  rol: RolUsuario;
  activo: boolean;
  /**
   * false cuando el email no sirve para recibir un link: está vacío, o es uno
   * de esos "barbero1" que se cargan cuando el empleado no quiere dar el suyo.
   * Es el dato que le dice al dueño quién depende de él para poder entrar.
   */
  email_recuperable: boolean;
  /** El recurso (silla) que opera, si es un profesional vinculado. */
  recurso: string | null;
}

export interface LinkRestablecer {
  url: string;
  usuario: string;
  vence_en_minutos: number;
}

export function listarEquipo(): Promise<MiembroEquipo[]> {
  return api.get<MiembroEquipo[]>("/equipo/usuarios");
}

/**
 * Roles que el dueño puede asignar desde su panel.
 *
 * No están "dueno" ni "admin" a propósito: son los que tocan la facturación.
 * El backend rechaza igual si alguien los manda a mano — esto es solo lo que
 * se ofrece en el formulario.
 */
export const ROLES_ASIGNABLES = [
  { valor: "profesional" as const, label: "Profesional", ayuda: "Atiende turnos. Ve su día." },
  { valor: "recepcion" as const, label: "Recepción", ayuda: "Agenda, clientes y caja." },
];

export function crearMiembro(datos: {
  nombre: string;
  email: string;
  clave: string;
  rol: "recepcion" | "profesional";
}): Promise<MiembroEquipo> {
  return api.post<MiembroEquipo>("/equipo/usuarios", datos);
}

export function editarMiembro(
  usuarioId: number,
  datos: Partial<{
    nombre: string;
    email: string;
    rol: "recepcion" | "profesional";
    activo: boolean;
  }>,
): Promise<MiembroEquipo> {
  return api.patch<MiembroEquipo>(`/equipo/usuarios/${usuarioId}`, datos);
}

/** Genera un link de un solo uso para que ese usuario elija contraseña nueva. */
export function generarLinkRestablecer(
  usuarioId: number,
): Promise<LinkRestablecer> {
  return api.post<LinkRestablecer>(
    `/equipo/usuarios/${usuarioId}/link-restablecer`,
    {},
  );
}

/** Etiqueta en castellano para mostrar el rol. */
export const ROL_LABEL: Record<RolUsuario, string> = {
  dueno: "Dueño",
  admin: "Administrador",
  recepcion: "Recepción",
  profesional: "Profesional",
};
