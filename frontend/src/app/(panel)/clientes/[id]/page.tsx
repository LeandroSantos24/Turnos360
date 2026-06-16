"use client";

/**
 * Ficha del cliente (/clientes/[id]).
 *
 * Datos del cliente + resumen (turnos, gasto, servicio favorito) + el
 * historial completo de turnos. Estilo uniforme: títulos Syne, tarjetas
 * rounded-2xl, números tabulares, modo claro/oscuro.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { ArrowLeft } from "lucide-react";

import { obtenerCliente, Cliente } from "@/lib/clientes-api";
import { listarTurnosDeCliente, Turno } from "@/lib/turnos-api";
import { calcularResumen, ResumenCliente } from "@/lib/cliente-historial";
import {
  colorEstadoHex,
  labelEstado,
  horaDe,
  inicialDe,
} from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

/** Formatea una fecha ISO como "12 de junio 2026". */
function fechaCorta(iso: string | null): string {
  if (!iso) return "—";
  return format(new Date(iso), "d 'de' MMMM yyyy", { locale: es });
}

/** Estilo reusable para los números grandes en Syne, parejos. */
const NUM_STYLE: React.CSSProperties = {
  fontFamily: "Syne, sans-serif",
  fontVariantNumeric: "lining-nums tabular-nums",
};

export default function FichaClientePage() {
  const params = useParams();
  const router = useRouter();
  const clienteId = Number(params.id);

  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [resumen, setResumen] = useState<ResumenCliente | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [c, t] = await Promise.all([
        obtenerCliente(clienteId),
        listarTurnosDeCliente(clienteId),
      ]);
      setCliente(c);
      // Ordenar turnos del más reciente al más antiguo
      const ordenados = [...t.items].sort(
        (a, b) =>
          new Date(b.fecha_inicio ?? 0).getTime() -
          new Date(a.fecha_inicio ?? 0).getTime(),
      );
      setTurnos(ordenados);
      setResumen(calcularResumen(t.items));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [clienteId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (cargando) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">Cargando ficha…</p>
      </div>
    );
  }

  if (error || !cliente) {
    return (
      <div className="p-8">
        <Button variant="outline" size="sm" onClick={() => router.back()}>
          <ArrowLeft size={16} className="mr-1" /> Volver
        </Button>
        <p className="mt-4 text-sm text-destructive">
          {error ?? "Cliente no encontrado"}
        </p>
      </div>
    );
  }

  const color = "#00d4aa"; // teal de la marca para el avatar del cliente
  const nombreCompleto = `${cliente.nombre} ${cliente.apellido ?? ""}`.trim();

  return (
    <div className="p-8">
      {/* Volver */}
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 -ml-2"
        onClick={() => router.back()}
      >
        <ArrowLeft size={16} className="mr-1" /> Volver
      </Button>

      {/* Cabecera: datos del cliente */}
      <div className="mb-6 flex items-start gap-4">
        <div
          className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-2xl font-bold text-white"
          style={{ backgroundColor: color, fontFamily: "Syne, sans-serif" }}
        >
          {inicialDe(nombreCompleto)}
        </div>
        <div className="min-w-0">
          <h1 className="text-2xl font-bold">{nombreCompleto}</h1>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {cliente.telefono && (
              <span className="tabular-nums">{cliente.telefono}</span>
            )}
            {cliente.email && <span>{cliente.email}</span>}
            {cliente.canal_adquisicion && (
              <span>Llegó por {cliente.canal_adquisicion}</span>
            )}
          </div>
        </div>
      </div>

      {/* Resumen (tarjetas) */}
      {resumen && (
        <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-2xl border bg-card p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Turnos totales
            </p>
            <p className="mt-1 text-2xl font-bold" style={NUM_STYLE}>
              {resumen.totalTurnos}
            </p>
          </div>
          <div className="rounded-2xl border bg-card p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Completados
            </p>
            <p className="mt-1 text-2xl font-bold" style={NUM_STYLE}>
              {resumen.turnosCompletados}
            </p>
          </div>
          <div className="rounded-2xl border bg-card p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Gastado
            </p>
            <p
              className="mt-1 text-2xl font-bold"
              style={{ ...NUM_STYLE, color: "#10b981" }}
            >
              ${resumen.gastoTotal.toLocaleString("es-AR")}
            </p>
          </div>
          <div className="rounded-2xl border bg-card p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Servicio favorito
            </p>
            <p className="mt-1 truncate text-lg font-bold">
              {resumen.servicioFavorito ?? "—"}
            </p>
          </div>
        </div>
      )}

      {/* Historial de turnos */}
      <h2 className="mb-3 text-lg font-bold">Historial de turnos</h2>
      {turnos.length === 0 ? (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            Este cliente todavía no tiene turnos.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border bg-card">
          {turnos.map((turno, i) => {
            const c = colorEstadoHex(turno.estado);
            return (
              <div
                key={turno.id}
                className={`flex items-center gap-4 px-4 py-3 ${
                  i > 0 ? "border-t" : ""
                }`}
              >
                {/* Fecha */}
                <div className="w-36 shrink-0">
                  <p className="text-sm font-medium tabular-nums">
                    {fechaCorta(turno.fecha_inicio)}
                  </p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                  </p>
                </div>
                {/* Servicio + profesional */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {turno.servicio_nombre ?? "Sin servicio"}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    con {turno.recurso_nombre ?? "—"}
                  </p>
                </div>
                {/* Importe */}
                <div className="shrink-0 text-right">
                  {turno.importe_previsto != null && (
                    <p className="text-sm font-medium tabular-nums">
                      ${Number(turno.importe_previsto).toLocaleString("es-AR")}
                    </p>
                  )}
                </div>
                {/* Estado */}
                <span
                  className="w-24 shrink-0 rounded-full px-2.5 py-1 text-center text-xs font-medium"
                  style={{ backgroundColor: `${c}22`, color: c }}
                >
                  {labelEstado(turno.estado)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}