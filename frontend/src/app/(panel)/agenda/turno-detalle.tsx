"use client";

/**
 * Panel lateral con el detalle de un turno.
 *
 * Muestra los datos del turno, botones para cambiar su estado (según las
 * transiciones válidas), y un acceso a la ficha del cliente. Las acciones
 * "peligrosas" (finalizar, cancelar) piden confirmación antes.
 */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Plus, X } from "lucide-react";
import { toast } from "sonner";

import { Turno, EstadoTurno, cambiarEstadoTurno, aplicarDescuento } from "@/lib/turnos-api";
import { TRANSICIONES, labelAccion, esReapertura } from "@/lib/turno-estados";
import { colorEstadoHex, labelEstado, horaDe, inicialDe } from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listarItems, agregarItem, quitarItem, ItemTurno } from "@/lib/items-api";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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

interface TurnoDetalleProps {
  turno: Turno | null;
  abierto: boolean;
  onCerrar: () => void;
  onCambio: () => void; // refrescar la agenda tras un cambio
}

// Estados que requieren confirmación antes de aplicarse (no se deshacen fácil).
const ESTADOS_PELIGROSOS: EstadoTurno[] = ["finalizado", "cancelado"];

export function TurnoDetalle({
  turno,
  abierto,
  onCerrar,
  onCambio,
}: TurnoDetalleProps) {
  const router = useRouter();
  const [procesando, setProcesando] = useState(false);
  const [confirmar, setConfirmar] = useState<EstadoTurno | null>(null);

  // Ítems adicionales del turno (perfilado, productos...).
  const [items, setItems] = useState<ItemTurno[]>([]);
  const [nuevoDesc, setNuevoDesc] = useState("");
  const [nuevoPrecio, setNuevoPrecio] = useState("");
  const [agregando, setAgregando] = useState(false);
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [servicioSel, setServicioSel] = useState("");
  const [descuentoActivo, setDescuentoActivo] = useState(false);
  const [descuentoPct, setDescuentoPct] = useState("");

  // Al abrir el panel, traer los adicionales del turno.
  useEffect(() => {
    if (!abierto || !turno) {
      setItems([]);
      return;
    }
    listarItems(turno.id)
      .then(setItems)
      .catch(() => setItems([]));
    const pct = Number(turno.descuento_pct ?? 0);
    setDescuentoActivo(pct > 0);
    setDescuentoPct(pct > 0 ? String(pct) : "");
  }, [abierto, turno]);

  // Catálogo de servicios (para precargar adicionales sin escribir).
  useEffect(() => {
    listarServicios()
      .then((r) => setServicios(r.items))
      .catch(() => setServicios([]));
  }, []);

  if (!turno) return null;

  const color = colorEstadoHex(turno.estado);
  const acciones = TRANSICIONES[turno.estado];

  // Total a cobrar = (servicio + adicionales) − descuento.
  const subtotalItems = items.reduce((acc, i) => acc + i.precio * i.cantidad, 0);
  const baseTurno = Number(turno.importe_previsto ?? 0) + subtotalItems;
  const pctDescuento = descuentoActivo
    ? Math.min(Math.max(Number(descuentoPct) || 0, 0), 100)
    : 0;
  const montoDescuento = baseTurno * (pctDescuento / 100);
  const totalTurno = baseTurno - montoDescuento;

  async function ejecutarAccion(destino: EstadoTurno) {
    if (!turno) return;
    setProcesando(true);
    try {
      await cambiarEstadoTurno(turno.id, destino);
      toast.success(`Turno ${labelEstado(destino).toLowerCase()}`);
      onCambio();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar");
    } finally {
      setProcesando(false);
      setConfirmar(null);
    }
  }

  function onAccion(destino: EstadoTurno) {
    if (ESTADOS_PELIGROSOS.includes(destino) || esReapertura(turno.estado)) {
      setConfirmar(destino);
    } else {
      ejecutarAccion(destino);
    }
  }

  /** Agrega un ítem adicional al turno. */
  async function agregarAdicional() {
    if (!turno || !nuevoDesc.trim()) return;
    setAgregando(true);
    try {
      const item = await agregarItem(turno.id, {
        descripcion: nuevoDesc.trim(),
        precio: Number(nuevoPrecio) || 0,
      });
      setItems((prev) => [...prev, item]);
      setNuevoDesc("");
      setNuevoPrecio("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo agregar");
    } finally {
      setAgregando(false);
    }
  }

  /** Quita un ítem del turno. */
  async function quitarAdicional(itemId: number) {
    if (!turno) return;
    try {
      await quitarItem(turno.id, itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo quitar");
    }
  }

  /** Precarga concepto y precio desde un servicio del catálogo. */
  function elegirServicio(servicioId: string) {
    const s = servicios.find((x) => String(x.id) === servicioId);
    if (!s) return;
    setNuevoDesc(s.nombre);
    setNuevoPrecio(s.precio != null ? String(s.precio) : "");
    setServicioSel("");
  }

  /** Activa o desactiva el descuento. Al desactivar, lo pone en 0. */
  async function toggleDescuento(on: boolean) {
    setDescuentoActivo(on);
    if (!on && turno) {
      setDescuentoPct("");
      try {
        await aplicarDescuento(turno.id, 0);
      } catch {
        /* si falla, el switch ya quedó visualmente apagado */
      }
    }
  }

  /** Guarda el % de descuento (al salir del campo o con Enter). */
  async function guardarDescuento() {
    if (!turno) return;
    const pct = Math.min(Math.max(Number(descuentoPct) || 0, 0), 100);
    try {
      await aplicarDescuento(turno.id, pct);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo aplicar el descuento",
      );
    }
  }

  return (
    <>
      <Sheet open={abierto} onOpenChange={(o) => !o && onCerrar()}>
        <SheetContent className="w-full overflow-y-auto p-6 sm:max-w-md">
          <SheetHeader className="space-y-0 text-left">
            <SheetTitle
              className="text-xl font-bold"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Detalle del turno
            </SheetTitle>
          </SheetHeader>

          <div className="mt-6 space-y-7">
            {/* Cliente */}
            <div className="flex items-center gap-4">
              <div
                className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-xl font-bold text-white"
                style={{ backgroundColor: color, fontFamily: "Syne, sans-serif" }}
              >
                {inicialDe(turno.cliente_nombre)}
              </div>
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold leading-tight">
                  {turno.cliente_nombre}
                </p>
                <span
                  className="mt-1.5 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
                  style={{ backgroundColor: `${color}1a`, color }}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {labelEstado(turno.estado)}
                </span>
              </div>
            </div>

            {/* Datos del turno */}
            <div className="divide-y overflow-hidden rounded-2xl border bg-card">
              <Fila label="Horario">
                <span className="tabular-nums">
                  {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                  {turno.fecha_fin && ` – ${horaDe(turno.fecha_fin)}`}
                </span>
              </Fila>
              <Fila label="Servicio">{turno.servicio_nombre ?? "—"}</Fila>
              <Fila label="Profesional">{turno.recurso_nombre ?? "—"}</Fila>
              {turno.es_sobreturno && <Fila label="Sobreturno">Sí</Fila>}
              {turno.importe_previsto != null && (
                <div className="flex items-center justify-between bg-muted/30 px-4 py-3.5">
                  <span className="text-sm text-muted-foreground">Importe</span>
                  <span className="flex items-center gap-2">
                    {turno.cubierto_por_abono && (
                      <span className="inline-block rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                        PRO
                      </span>
                    )}
                    <span
                      className="text-lg font-bold tabular-nums"
                      style={{ fontFamily: "Syne, sans-serif" }}
                    >
                      ${Number(turno.importe_previsto).toLocaleString("es-AR")}
                    </span>
                  </span>
                </div>
              )}
            </div>

            {/* Adicionales */}
            <div className="space-y-2.5">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Adicionales
              </p>
              {items.length > 0 && (
                <div className="divide-y overflow-hidden rounded-2xl border bg-card text-sm">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-2 px-4 py-2.5"
                    >
                      <span className="min-w-0 truncate">
                        {item.descripcion}
                        {item.cantidad > 1 && (
                          <span className="text-muted-foreground"> ×{item.cantidad}</span>
                        )}
                      </span>
                      <span className="flex shrink-0 items-center gap-3">
                        <span className="font-medium tabular-nums">
                          ${(item.precio * item.cantidad).toLocaleString("es-AR")}
                        </span>
                        <button
                          onClick={() => quitarAdicional(item.id)}
                          className="text-muted-foreground transition-colors hover:text-destructive"
                          aria-label="Quitar"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Cargar desde el catálogo de servicios */}
              {servicios.length > 0 && (
                <Select value={servicioSel} onValueChange={elegirServicio}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Cargar desde un servicio…" />
                  </SelectTrigger>
                  <SelectContent>
                    {servicios.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.nombre}
                        {s.precio != null &&
                          ` — $${Number(s.precio).toLocaleString("es-AR")}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              {/* Agregar uno nuevo (o ajustar lo precargado) */}
              <div className="flex gap-2">
                <Input
                  placeholder="Concepto (ej. Perfilado)"
                  value={nuevoDesc}
                  onChange={(e) => setNuevoDesc(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && agregarAdicional()}
                  className="flex-1"
                />
                <Input
                  type="number"
                  inputMode="numeric"
                  placeholder="$"
                  value={nuevoPrecio}
                  onChange={(e) => setNuevoPrecio(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && agregarAdicional()}
                  className="w-24"
                />
                <Button
                  size="icon"
                  variant="outline"
                  onClick={agregarAdicional}
                  disabled={agregando || !nuevoDesc.trim()}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>

            </div>

            {/* Descuento */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between rounded-2xl border bg-card px-4 py-3">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium">Aplicar descuento</p>
                  <p className="text-xs text-muted-foreground">
                    Para estudiantes, jubilados, etc.
                  </p>
                </div>
                <Switch checked={descuentoActivo} onCheckedChange={toggleDescuento} />
              </div>

              {descuentoActivo && (
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Input
                      type="number"
                      inputMode="numeric"
                      min="0"
                      max="100"
                      placeholder="15"
                      value={descuentoPct}
                      onChange={(e) => setDescuentoPct(e.target.value)}
                      onBlur={guardarDescuento}
                      onKeyDown={(e) => e.key === "Enter" && guardarDescuento()}
                      className="pr-8"
                    />
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                      %
                    </span>
                  </div>
                  <Button variant="outline" size="sm" onClick={guardarDescuento}>
                    Aplicar
                  </Button>
                </div>
              )}

              {/* Total */}
              {(items.length > 0 || pctDescuento > 0) && (
                <div className="space-y-1.5 rounded-2xl bg-muted/40 px-4 py-3">
                  {pctDescuento > 0 && (
                    <>
                      <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>Subtotal</span>
                        <span className="tabular-nums">
                          ${baseTurno.toLocaleString("es-AR")}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>Descuento ({pctDescuento}%)</span>
                        <span className="tabular-nums">
                          −${montoDescuento.toLocaleString("es-AR")}
                        </span>
                      </div>
                    </>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Total</span>
                    <span
                      className="text-lg font-bold tabular-nums"
                      style={{ fontFamily: "Syne, sans-serif" }}
                    >
                      ${totalTurno.toLocaleString("es-AR")}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Acciones de estado */}
            {acciones.length > 0 && (
              <div className="space-y-2.5">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Acciones
                </p>
                <div className="flex flex-wrap gap-2">
                  {acciones.map((destino) => (
                    <Button
                      key={destino}
                      variant={destino === "cancelado" ? "outline" : "default"}
                      className="flex-1"
                      disabled={procesando}
                      onClick={() => onAccion(destino)}
                    >
                      {labelAccion(turno.estado, destino)}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Acceso a la ficha del cliente */}
            <Button
              variant="ghost"
              className="w-full justify-between rounded-xl border bg-card hover:bg-muted/50"
              onClick={() => router.push(`/clientes/${turno.cliente_id}`)}
            >
              <span>Ver ficha del cliente</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Confirmación para acciones peligrosas */}
      <AlertDialog open={confirmar !== null} onOpenChange={(o) => !o && setConfirmar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {esReapertura(turno.estado)
                ? "¿Reabrir el turno?"
                : confirmar === "cancelado"
                  ? "¿Cancelar el turno?"
                  : "¿Finalizar el turno?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {esReapertura(turno.estado)
                ? "El turno volverá a estar activo. Usalo para corregir un error."
                : confirmar === "cancelado"
                  ? "El turno se cancelará y el horario quedará libre. Esta acción no se puede deshacer."
                  : "El turno se marcará como finalizado. Esta acción no se puede deshacer."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={procesando}>No, volver</AlertDialogCancel>
            <AlertDialogAction
              disabled={procesando}
              onClick={() => confirmar && ejecutarAccion(confirmar)}
              className={
                confirmar === "cancelado"
                  ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  : ""
              }
            >
              {esReapertura(turno.estado)
                ? "Sí, reabrir"
                : confirmar === "cancelado"
                  ? "Sí, cancelar"
                  : "Sí, finalizar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

/** Una fila de dato: etiqueta a la izquierda, valor a la derecha. */
function Fila({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{children}</span>
    </div>
  );
}