"use client";

/**
 * Ficha del cliente (/clientes/[id]).
 *
 * Datos del cliente + resumen (turnos, gasto, servicio favorito) + el
 * historial completo de turnos. Botón "Editar", asignar/cancelar membresía.
 * Estilo uniforme: títulos Syne, tarjetas rounded-2xl, números tabulares,
 * modo claro/oscuro.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { ArrowLeft, Pencil } from "lucide-react";
import { toast } from "sonner";

import { obtenerCliente, Cliente } from "@/lib/clientes-api";
import { listarTurnosDeCliente, Turno } from "@/lib/turnos-api";
import { calcularResumen, ResumenCliente } from "@/lib/cliente-historial";
import {
  membresiaDeCliente,
  cancelarMembresia,
  Membresia,
} from "@/lib/membresias-api";
import {
  colorEstadoHex,
  labelEstado,
  horaDe,
  inicialDe,
} from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { EditarClienteDialog } from "../editar-cliente-dialog";
import { AsignarMembresiaDialog } from "../asignar-membresia-dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

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
  const [editando, setEditando] = useState(false);
  const [membresia, setMembresia] = useState<Membresia | null>(null);
  const [asignando, setAsignando] = useState(false);
  const [cancelandoMembresia, setCancelandoMembresia] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [c, t, m] = await Promise.all([
        obtenerCliente(clienteId),
        listarTurnosDeCliente(clienteId),
        membresiaDeCliente(clienteId),
      ]);
      setCliente(c);
      setMembresia(m);
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

  /** Cancela la membresía (tras confirmar en el cartel). */
  async function confirmarCancelarMembresia() {
    if (!membresia) return;
    try {
      await cancelarMembresia(membresia.id);
      toast.success("Membresía cancelada");
      setMembresia(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cancelar");
    } finally {
      setCancelandoMembresia(false);
    }
  }

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
      {/* Barra superior: volver + editar */}
      <div className="mb-4 flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => router.back()}
        >
          <ArrowLeft size={16} className="mr-1" /> Volver
        </Button>
        <Button variant="outline" size="sm" onClick={() => setEditando(true)}>
          <Pencil size={14} className="mr-1.5" /> Editar
        </Button>
      </div>

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
          {/* Etiquetas del cliente */}
          {cliente.etiquetas && cliente.etiquetas.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {cliente.etiquetas.map((etiqueta) => (
                <span
                  key={etiqueta}
                  className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
                >
                  {etiqueta}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Datos personales extra (DNI, nacimiento, observaciones, membresía) */}
      {(cliente.dni ||
        cliente.fecha_nacimiento ||
        cliente.observaciones ||
        membresia) && (
        <div className="mb-8 rounded-2xl border bg-card p-5">
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-3">
            {cliente.dni && (
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  DNI
                </p>
                <p className="mt-0.5 text-sm font-medium tabular-nums">
                  {cliente.dni}
                </p>
              </div>
            )}
            {cliente.fecha_nacimiento && (
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Nacimiento
                </p>
                <p className="mt-0.5 text-sm font-medium tabular-nums">
                  {fechaCorta(cliente.fecha_nacimiento)}
                </p>
              </div>
            )}
          </div>
          {cliente.observaciones && (
            <div className="mt-4 border-t pt-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Observaciones
              </p>
              <p className="mt-1 text-sm">{cliente.observaciones}</p>
            </div>
          )}
          {/* Membresía / abono */}
          <div className="mt-4 border-t pt-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Membresía
            </p>
            {membresia && membresia.vigente ? (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="inline-block rounded-full bg-amber-400/20 px-2.5 py-0.5 text-sm font-bold text-amber-600 dark:text-amber-400">
                  {membresia.plan_nombre}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  vigente hasta {fechaCorta(membresia.fecha_hasta)}
                </span>
                <button
                  onClick={() => setCancelandoMembresia(true)}
                  className="ml-1 text-xs text-muted-foreground underline hover:text-destructive"
                >
                  cancelar
                </button>
              </div>
            ) : (
              <div className="mt-1.5 flex items-center gap-3">
                <span className="text-sm text-muted-foreground">No tiene</span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setAsignando(true)}
                >
                  Asignar membresía
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

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

      {/* Diálogo de editar */}
      <EditarClienteDialog
        cliente={cliente}
        abierto={editando}
        onCerrar={() => setEditando(false)}
        onEditado={() => {
          setEditando(false);
          cargar();
        }}
      />

      {/* Diálogo de asignar membresía */}
      <AsignarMembresiaDialog
        clienteId={clienteId}
        abierto={asignando}
        onCerrar={() => setAsignando(false)}
        onAsignada={cargar}
      />

      {/* Confirmación de cancelar membresía */}
      <AlertDialog
        open={cancelandoMembresia}
        onOpenChange={(o) => !o && setCancelandoMembresia(false)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cancelar la membresía?</AlertDialogTitle>
            <AlertDialogDescription>
              El cliente dejará de tener el abono{" "}
              <span className="font-medium">{membresia?.plan_nombre}</span> activo.
              Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>No, mantener</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmarCancelarMembresia}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Sí, cancelar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}