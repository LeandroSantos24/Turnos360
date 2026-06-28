"use client";

/**
 * "Mi día" (/mi-dia): la pantalla del profesional.
 *
 * Reemplaza al dashboard de Inicio para el rol profesional (que no debe ver la
 * plata del negocio). Muestra SUS turnos de hoy (el backend ya filtra por su
 * recurso) y le deja marcar Empezar / Finalizar. Si todavía no está vinculado
 * a un recurso, muestra el cartel para que el dueño lo vincule.
 */

import { useEffect, useState, useCallback } from "react";
import { format, startOfDay, endOfDay } from "date-fns";
import { es } from "date-fns/locale";
import Link from "next/link";
import { Play, CheckCircle2, Link2Off } from "lucide-react";

import {
  listarTurnosDelDia,
  cambiarEstadoTurno,
  Turno,
} from "@/lib/turnos-api";
import { miRecurso } from "@/lib/recursos-api";
import { colorEstadoHex, labelEstado, horaDe } from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

function ordenarPorHora(turnos: Turno[]): Turno[] {
  return [...turnos].sort((a, b) => {
    const ta = a.fecha_inicio ? new Date(a.fecha_inicio).getTime() : 0;
    const tb = b.fecha_inicio ? new Date(b.fecha_inicio).getTime() : 0;
    return ta - tb;
  });
}

export default function MiDiaPage() {
  // null = todavía cargando; true/false = ya sabemos si está vinculado
  const [vinculado, setVinculado] = useState<boolean | null>(null);
  const [recursoNombre, setRecursoNombre] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const rec = await miRecurso();
      if (rec === null) {
        setVinculado(false);
        setTurnos([]);
        return;
      }
      setVinculado(true);
      setRecursoNombre(rec.nombre);

      const desde = startOfDay(new Date()).toISOString();
      const hasta = endOfDay(new Date()).toISOString();
      const data = await listarTurnosDelDia(desde, hasta);
      setTurnos(ordenarPorHora(data.items));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function cambiar(t: Turno, estado: "en_curso" | "finalizado") {
    try {
      await cambiarEstadoTurno(t.id, estado);
      toast.success(estado === "en_curso" ? "Turno iniciado" : "Turno finalizado");
      cargar();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo actualizar el turno",
      );
    }
  }

  const hoy = format(new Date(), "EEEE d 'de' MMMM", { locale: es });

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Mi día</h1>
        <p className="text-sm capitalize text-muted-foreground">
          {hoy}
          {recursoNombre ? ` · ${recursoNombre}` : ""}
          {cargando && " · cargando…"}
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* No vinculado: cartel para pedirle al dueño */}
      {vinculado === false && (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
            <Link2Off size={22} className="text-muted-foreground" />
          </div>
          <p className="mb-1 font-medium">Todavía no estás vinculado a una agenda</p>
          <p className="mx-auto max-w-sm text-sm text-muted-foreground">
            Pedile al dueño que te asigne tu silla (recurso) para ver tus turnos
            del día acá.
          </p>
        </div>
      )}

      {/* Vinculado, sin turnos hoy */}
      {vinculado && !cargando && turnos.length === 0 && (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            No tenés turnos para hoy.
          </p>
        </div>
      )}

      {/* Vinculado, con turnos */}
      {vinculado && turnos.length > 0 && (
        <div className="overflow-hidden rounded-2xl border bg-card">
          {turnos.map((t, i) => {
            const color = colorEstadoHex(t.estado);
            const inactivo =
              t.estado === "cancelado" || t.estado === "ausente";
            return (
              <div
                key={t.id}
                className={`flex items-center gap-3 px-4 py-4 ${
                  i > 0 ? "border-t" : ""
                }`}
                style={{ opacity: inactivo ? 0.55 : 1 }}
              >
                {/* Hora */}
                <div
                  className="w-16 shrink-0 text-sm font-bold tabular-nums"
                  style={{
                    fontFamily: "Syne, sans-serif",
                    fontVariantNumeric: "lining-nums tabular-nums",
                  }}
                >
                  {t.fecha_inicio && horaDe(t.fecha_inicio)}
                </div>

                {/* Barra de color */}
                <div
                  className="h-10 w-1 shrink-0 rounded-full"
                  style={{ backgroundColor: color }}
                />

                {/* Cliente + servicio */}
                <div className="flex min-w-0 flex-1 flex-col">
                  <Link
                    href={`/clientes/${t.cliente_id}`}
                    className="truncate text-sm font-semibold hover:underline"
                  >
                    {t.cliente_nombre ?? "Cliente"}
                  </Link>
                  <span className="truncate text-xs text-muted-foreground">
                    {t.servicio_nombre ?? "Sin servicio"}
                    {t.es_sobreturno && " · sobreturno"}
                  </span>
                </div>

                {/* Estado */}
                <span
                  className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
                  style={{ backgroundColor: `${color}22`, color }}
                >
                  {labelEstado(t.estado)}
                </span>

                {/* Acciones del profesional */}
                {t.estado === "confirmado" && (
                  <Button size="sm" onClick={() => cambiar(t, "en_curso")}>
                    <Play size={15} className="mr-1" />
                    Empezar
                  </Button>
                )}
                {t.estado === "en_curso" && (
                  <Button size="sm" onClick={() => cambiar(t, "finalizado")}>
                    <CheckCircle2 size={15} className="mr-1" />
                    Finalizar
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {vinculado && turnos.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          Los turnos pendientes los confirma recepción. Vos podés empezar y
          finalizar los tuyos.
        </p>
      )}
    </div>
  );
}
