/**
 * Finanzas (E10): métodos de pago, categorías, caja, cobros y gastos.
 * Refleja los endpoints de app/routers/finanzas.py.
 */

import { api } from "./api";

/* ─────────── Métodos de pago ─────────── */

export interface MetodoPago {
  id: number;
  nombre: string;
  comision_pct: number;
  activo: boolean;
}

export interface MetodoPagoCrear {
  nombre: string;
  comision_pct?: number;
}

export interface MetodoPagoEditar {
  nombre?: string;
  comision_pct?: number;
  activo?: boolean;
}

export function listarMetodos(): Promise<MetodoPago[]> {
  return api.get<MetodoPago[]>("/metodos-pago");
}
export function crearMetodo(datos: MetodoPagoCrear): Promise<MetodoPago> {
  return api.post<MetodoPago>("/metodos-pago", datos);
}
export function editarMetodo(id: number, datos: MetodoPagoEditar): Promise<MetodoPago> {
  return api.patch<MetodoPago>(`/metodos-pago/${id}`, datos);
}
export function borrarMetodo(id: number): Promise<void> {
  return api.delete<void>(`/metodos-pago/${id}`);
}

/* ─────────── Categorías de gasto ─────────── */

export interface Categoria {
  id: number;
  nombre: string;
  tipo: string;
}

export function listarCategorias(): Promise<Categoria[]> {
  return api.get<Categoria[]>("/categorias-financieras");
}
export function crearCategoria(datos: { nombre: string; tipo?: string }): Promise<Categoria> {
  return api.post<Categoria>("/categorias-financieras", datos);
}

/* ─────────── Caja ─────────── */

export interface Caja {
  id: number;
  fecha_apertura: string;
  fecha_cierre: string | null;
  saldo_inicial: number;
  saldo_final: number | null;
  estado: string;
}

export interface EgresoMetodoResumen {
  metodo: string;
  cantidad: number;
  total: number;
}

export interface MetodoResumen {
  metodo: string;
  cantidad: number;
  total: number;     // bruto
  comision: number;  // lo que se come el método
  neto: number;      // total − comisión
}
export interface CajaResumen {
  caja: Caja;
  total_ingresos: number;
  total_egresos: number;
  saldo_esperado: number;
  saldo_real: number | null;
  diferencia: number | null;
  cantidad_movimientos: number;
  por_metodo: MetodoResumen[];
  egresos_por_metodo: EgresoMetodoResumen[];
  total_comisiones: number;
  total_neto: number;
  efectivo_esperado: number; // lo que tiene que haber en el cajón físico
}

export function cajaActual(): Promise<CajaResumen | null> {
  return api.get<CajaResumen | null>("/caja/actual");
}
export function listarCajas(): Promise<Caja[]> {
  return api.get<Caja[]>("/cajas");
}
export interface CajaDetalle {
  resumen: CajaResumen;
  movimientos: Movimiento[];
}
export function detalleCaja(cajaId: number): Promise<CajaDetalle> {
  return api.get<CajaDetalle>(`/cajas/${cajaId}/detalle`);
}
export function abrirCaja(datos: { saldo_inicial?: number; observaciones?: string }): Promise<Caja> {
  return api.post<Caja>("/caja/abrir", datos);
}
export function cerrarCaja(datos: { saldo_real: number; observaciones?: string }): Promise<CajaResumen> {
  return api.post<CajaResumen>("/caja/cerrar", datos);
}

/* ─────────── Cobro de un turno ─────────── */

export interface PagoLinea {
  metodo_pago_id: number | null;
  monto: number;
}

export interface Pago {
  id: number;
  turno_id: number | null;
  cliente_id: number;
  metodo_pago_id: number | null;
  metodo_pago_nombre: string | null;
  monto: number;
  comision_aplicada: number | null;
  fecha: string;
}

export interface Cobro {
  turno_id: number;
  total_cobrado: number;
  total_comision: number;
  neto: number;
  pagos: Pago[];
}

export function registrarCobro(turnoId: number, pagos: PagoLinea[]): Promise<Cobro> {
  return api.post<Cobro>(`/turnos/${turnoId}/cobro`, { pagos });
}
export function pagosDeTurno(turnoId: number): Promise<Pago[]> {
  return api.get<Pago[]>(`/turnos/${turnoId}/pagos`);
}

/* ─────────── Gastos / movimientos ─────────── */

export interface Movimiento {
  id: number;
  fecha: string;
  tipo: string;
  concepto: string | null;
  descripcion: string | null;
  monto: number;
  metodo_pago_id: number | null;
  metodo_pago: string | null;
  categoria_id: number | null;
}

export interface GastoCrear {
  concepto: string;
  monto: number;
  categoria_id?: number | null;
  metodo_pago_id?: number | null;
  descripcion?: string;
}

export function registrarGasto(datos: GastoCrear): Promise<Movimiento> {
  return api.post<Movimiento>("/gastos", datos);
}
export function listarMovimientos(tipo?: "ingreso" | "egreso"): Promise<Movimiento[]> {
  return api.get<Movimiento[]>(tipo ? `/movimientos?tipo=${tipo}` : "/movimientos");
}

/* ─────────── Historial comercial del cliente ─────────── */

export interface CobradoCliente {
  total_cobrado: number;
  cantidad_pagos: number;
}

export function cobradoDeCliente(clienteId: number): Promise<CobradoCliente> {
  return api.get<CobradoCliente>(`/clientes/${clienteId}/cobrado`);
}