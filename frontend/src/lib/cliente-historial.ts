/**
 * Cálculos sobre el historial de turnos de un cliente:
 * resumen (total, gastado, servicio favorito) para la ficha.
 */

import { Turno } from "./turnos-api";

export interface ResumenCliente {
  totalTurnos: number;
  turnosCompletados: number;
  gastoTotal: number;
  servicioFavorito: string | null;
  ultimaVisita: string | null; // fecha ISO del último turno finalizado
}

/** Calcula el resumen a partir de la lista de turnos del cliente. */
export function calcularResumen(turnos: Turno[]): ResumenCliente {
  const completados = turnos.filter((t) => t.estado === "finalizado");

  // Gasto total: suma de importes de los turnos finalizados.
  const gastoTotal = completados.reduce(
    (acc, t) => acc + (t.importe_previsto ? Number(t.importe_previsto) : 0),
    0,
  );

  // Servicio favorito: el que más se repite (entre todos los turnos).
  const conteo: Record<string, number> = {};
  for (const t of turnos) {
    if (t.servicio_nombre) {
      conteo[t.servicio_nombre] = (conteo[t.servicio_nombre] ?? 0) + 1;
    }
  }
  let servicioFavorito: string | null = null;
  let maxConteo = 0;
  for (const [nombre, n] of Object.entries(conteo)) {
    if (n > maxConteo) {
      maxConteo = n;
      servicioFavorito = nombre;
    }
  }

  // Última visita: el turno finalizado más reciente.
  const finalizadosOrdenados = [...completados]
    .filter((t) => t.fecha_inicio)
    .sort(
      (a, b) =>
        new Date(b.fecha_inicio!).getTime() -
        new Date(a.fecha_inicio!).getTime(),
    );
  const ultimaVisita = finalizadosOrdenados[0]?.fecha_inicio ?? null;

  return {
    totalTurnos: turnos.length,
    turnosCompletados: completados.length,
    gastoTotal,
    servicioFavorito,
    ultimaVisita,
  };
}