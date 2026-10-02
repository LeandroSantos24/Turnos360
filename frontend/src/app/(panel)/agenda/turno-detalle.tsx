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
import { ArrowRight, Check, Plus, Star, X } from "lucide-react";
import { toast } from "sonner";

import { Turno, EstadoTurno, cambiarEstadoTurno, aplicarDescuento, pedirResena } from "@/lib/turnos-api";
import { TRANSICIONES, labelAccion, esReapertura } from "@/lib/turno-estados";
import { colorEstadoHex, labelEstado, horaDe, inicialDe } from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { CobroDialog } from "./cobro-dialog";
import {
  anularCobro,
  pagosDeTurno,
  listarMetodos,
  MetodoPago,
  Pago,
} from "@/lib/finanzas-api";
import { esDueno, useRol } from "@/lib/roles";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listarItems, agregarItem, quitarItem, ItemTurno } from "@/lib/items-api";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import { moverTurno } from "@/lib/turnos-api";
import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { CalendarClock } from "lucide-react";
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
//
// "ausente" faltaba, y es el PEOR de los tres: en el backend es un estado
// terminal de verdad (services/turno.py, EstadoTurno.AUSENTE: set()), así que
// cualquier intento de salir de ahí devuelve 409. Un click de más dejaba el
// turno de un cliente real muerto para siempre, sin preguntar nada.
const ESTADOS_PELIGROSOS: EstadoTurno[] = ["finalizado", "cancelado", "ausente"];

export function TurnoDetalle({
  turno,
  abierto,
  onCerrar,
  onCambio,
}: TurnoDetalleProps) {
  const router = useRouter();
  const rol = useRol();
  const [procesando, setProcesando] = useState(false);
  const [confirmarAnulacion, setConfirmarAnulacion] = useState(false);
  const [anulando, setAnulando] = useState(false);
  const [confirmar, setConfirmar] = useState<EstadoTurno | null>(null);

  // Reprogramar: fecha/hora nuevas y/o cambio de profesional.
  const [reprogramando, setReprogramando] = useState(false);
  const [nuevaFecha, setNuevaFecha] = useState("");
  const [nuevaHora, setNuevaHora] = useState("");
  const [nuevoRecurso, setNuevoRecurso] = useState<string>("");
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [moviendo, setMoviendo] = useState(false);
  const [pidiendoResena, setPidiendoResena] = useState(false);
  const [resenaEnviada, setResenaEnviada] = useState(false);

  function abrirReprogramar() {
    if (!turno?.fecha_inicio) return;
    setNuevaFecha(turno.fecha_inicio.slice(0, 10));
    setNuevaHora(turno.fecha_inicio.slice(11, 16));
    setNuevoRecurso(String(turno.recurso_id ?? ""));
    setReprogramando(true);
    if (recursos.length === 0) {
      listarRecursos()
        .then((r) => setRecursos(r.items.filter((x) => x.activo)))
        .catch(() => {});
    }
  }

  async function confirmarReprogramar() {
    if (!turno || !nuevaFecha || !nuevaHora) return;
    setMoviendo(true);
    try {
      const iso = `${nuevaFecha}T${nuevaHora}:00Z`;
      await moverTurno(
        turno.id,
        iso,
        nuevoRecurso ? Number(nuevoRecurso) : undefined,
      );
      toast.success("Turno reprogramado — le avisamos al cliente por email");
      setReprogramando(false);
      onCambio();
      onCerrar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo reprogramar");
    } finally {
      setMoviendo(false);
    }
  }

  // Ítems adicionales del turno (perfilado, productos...).
  const [items, setItems] = useState<ItemTurno[]>([]);
  const [nuevoDesc, setNuevoDesc] = useState("");
  const [nuevoPrecio, setNuevoPrecio] = useState("");
  const [agregando, setAgregando] = useState(false);
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [servicioSel, setServicioSel] = useState("");
  const [descuentoActivo, setDescuentoActivo] = useState(false);
  const [descuentoPct, setDescuentoPct] = useState("");
  // "%" o "$": el descuento fijo en pesos no se convierte a % (el redondeo
  // cobraba centavos de más).
  const [descuentoModo, setDescuentoModo] = useState<"%" | "$">("%");
  const [cobrando, setCobrando] = useState(false);
  const [pagos, setPagos] = useState<Pago[]>([]);
  const [metodosPago, setMetodosPago] = useState<MetodoPago[]>([]);

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
    const fijo = Number(turno.descuento_monto ?? 0);
    setDescuentoActivo(pct > 0 || fijo > 0);
    setDescuentoModo(fijo > 0 ? "$" : "%");
    setDescuentoPct(fijo > 0 ? String(fijo) : pct > 0 ? String(pct) : "");
    pagosDeTurno(turno.id)
      .then(setPagos)
      .catch(() => setPagos([]));
  }, [abierto, turno]);

  // Catálogo de servicios (para precargar adicionales sin escribir).
  useEffect(() => {
    listarServicios()
      .then((r) => setServicios(r.items))
      .catch(() => setServicios([]));
    listarMetodos()
      .then(setMetodosPago)
      .catch(() => setMetodosPago([]));
  }, []);

  if (!turno) return null;

  const color = colorEstadoHex(turno.estado);
  // Fallback: un estado nuevo deja el panel sin botones, no roto.
  const acciones = TRANSICIONES[turno.estado] ?? [];

  // Total a cobrar = (servicio + adicionales) − % − fijo. Misma cuenta que
  // el backend (services/turno.py::_total_con_items).
  const subtotalItems = items.reduce((acc, i) => acc + i.precio * i.cantidad, 0);
  const baseTurno = Number(turno.importe_previsto ?? 0) + subtotalItems;
  const valorDescuento = descuentoActivo ? Math.max(Number(descuentoPct) || 0, 0) : 0;
  const pctDescuento = descuentoModo === "%" ? Math.min(valorDescuento, 100) : 0;
  const fijoDescuento = descuentoModo === "$" ? Math.min(valorDescuento, baseTurno) : 0;
  const montoDescuento =
    Math.round((baseTurno * (pctDescuento / 100) + fijoDescuento) * 100) / 100;
  const totalTurno = Math.max(baseTurno - montoDescuento, 0);
  const totalCobrado = pagos.reduce((acc, p) => acc + p.monto, 0);
  const saldoTurno = Math.max(Math.round((totalTurno - totalCobrado) * 100) / 100, 0);
  // Con cobro registrado el precio queda congelado: se anula el cobro primero.
  const bloqueado = turno.cobrado;

  function nombreMetodo(p: Pago): string {
    if (p.origen === "giftcard_uso") return "Gift card";
    if (p.origen === "sena") return "Seña online";
    if (p.metodo_pago_id == null) return "Sin método";
    const m = metodosPago.find((x) => x.id === p.metodo_pago_id);
    return m ? m.nombre : "Pago";
  }

  async function ejecutarAnulacion() {
    if (!turno) return;
    setAnulando(true);
    try {
      const r = await anularCobro(turno.id);
      toast.success(`Cobro anulado: $${r.monto.toLocaleString("es-AR")} fuera de caja`);
      pagosDeTurno(turno.id).then(setPagos).catch(() => {});
      onCambio();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo anular el cobro");
    } finally {
      setAnulando(false);
      setConfirmarAnulacion(false);
    }
  }

  async function ejecutarAccion(destino: EstadoTurno) {
    if (!turno) return;
    setProcesando(true);
    try {
      await cambiarEstadoTurno(turno.id, destino);
      toast.success(`Turno ${labelEstado(destino).toLowerCase()}`);
      // No cerramos el panel: el usuario suele encadenar estados
      // (confirmar → iniciar → finalizar). Se cierra tocando afuera.
      onCambio();
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
        await aplicarDescuento(turno.id, 0, 0);
      } catch {
        /* si falla, el switch ya quedó visualmente apagado */
      }
    }
  }

  /** Guarda el % de descuento (al salir del campo o con Enter). */
  async function guardarDescuento() {
    if (!turno) return;
    try {
      if (descuentoModo === "%") {
        await aplicarDescuento(turno.id, pctDescuento, 0);
      } else {
        await aplicarDescuento(turno.id, 0, fijoDescuento);
      }
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
          {/* El cliente ES el encabezado: antes el título ocupaba una línea
              entera y el cliente vivía en un bloque aparte, dejando un hueco
              grande arriba y empujando los adicionales fuera de la pantalla. */}
          <SheetHeader className="gap-0 p-0 pr-8 text-left">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Detalle del turno
            </p>
            <div className="mt-3 flex items-center gap-3">
              <div
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-base font-bold text-white"
                style={{ backgroundColor: color, fontFamily: "var(--fuente-titulos)" }}
              >
                {inicialDe(turno.cliente_nombre)}
              </div>
              <div className="min-w-0 flex-1">
                <SheetTitle
                  className="truncate text-lg font-bold leading-tight"
                  style={{ fontFamily: "var(--fuente-titulos)" }}
                >
                  {turno.cliente_nombre}
                </SheetTitle>
                <span
                  className="mt-1 inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
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
          </SheetHeader>

          <div className="mt-4 space-y-5">
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
                <div className="flex flex-wrap items-center justify-between gap-2 bg-muted/30 px-3.5 py-3">
                  <span className="text-sm text-muted-foreground">Importe</span>
                  <span className="flex items-center gap-2">
                    {turno.cubierto_por_abono && (
                      <span className="inline-block rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                        PRO
                      </span>
                    )}
                    {turno.sena_estado === "pagada" && (
                      <span className="inline-block rounded-full bg-emerald-400/20 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                        SEÑADO{turno.sena_monto ? ` $${Number(turno.sena_monto).toLocaleString("es-AR")}` : ""}
                      </span>
                    )}
                    {turno.sena_estado === "pendiente" && (
                      <span className="inline-block rounded-full bg-orange-400/20 px-2 py-0.5 text-[10px] font-bold text-orange-600 dark:text-orange-400">
                        SEÑA PENDIENTE
                      </span>
                    )}
                    <span
                      className="text-lg font-bold tabular-nums"
                      style={{ fontFamily: "var(--fuente-titulos)" }}
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
                        {!bloqueado && (
                          <button
                            onClick={() => quitarAdicional(item.id)}
                            className="text-muted-foreground transition-colors hover:text-destructive"
                            aria-label="Quitar"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Cargar desde el catálogo de servicios */}
              {!bloqueado && servicios.length > 0 && (
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
              {!bloqueado && (
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
              )}

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
                <Switch
                  checked={descuentoActivo}
                  onCheckedChange={toggleDescuento}
                  disabled={bloqueado}
                />
              </div>

              {descuentoActivo && !bloqueado && (
                <div className="flex items-center gap-2">
                  <div className="flex shrink-0 overflow-hidden rounded-md border">
                    {(["%", "$"] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setDescuentoModo(m)}
                        className={`h-9 w-9 text-sm font-medium transition-colors ${
                          descuentoModo === m
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:bg-muted"
                        }`}
                        aria-pressed={descuentoModo === m}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                  <div className="relative flex-1">
                    <Input
                      type="number"
                      inputMode="numeric"
                      min="0"
                      max={descuentoModo === "%" ? "100" : undefined}
                      placeholder={descuentoModo === "%" ? "15" : "2000"}
                      value={descuentoPct}
                      onChange={(e) => setDescuentoPct(e.target.value)}
                      onBlur={guardarDescuento}
                      onKeyDown={(e) => e.key === "Enter" && guardarDescuento()}
                      className="pr-8"
                    />
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                      {descuentoModo}
                    </span>
                  </div>
                  <Button variant="outline" size="sm" onClick={guardarDescuento}>
                    Aplicar
                  </Button>
                </div>
              )}

              {/* Total */}
              {(items.length > 0 || montoDescuento > 0) && (
                <div className="space-y-1.5 rounded-2xl bg-muted/40 px-4 py-3">
                  {montoDescuento > 0 && (
                    <>
                      <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>Subtotal</span>
                        <span className="tabular-nums">
                          ${baseTurno.toLocaleString("es-AR")}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>
                          Descuento{pctDescuento > 0 ? ` (${pctDescuento}%)` : ""}
                        </span>
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
                      style={{ fontFamily: "var(--fuente-titulos)" }}
                    >
                      ${totalTurno.toLocaleString("es-AR")}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Cobro: lo ya pagado (seña, parcial, gift card) + lo que falta.
                Antes la sola existencia de un pago escondía el botón: un turno
                con la seña pagada mostraba «Cobrado $3.000» y el saldo no se
                cobraba nunca por el sistema. Ahora manda `turno.cobrado`. */}
            {pagos.length > 0 && (
              <div
                className={`space-y-2 rounded-2xl border p-4 ${
                  turno.cobrado
                    ? "border-emerald-500/30 bg-emerald-500/10"
                    : "bg-card"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`flex items-center gap-1.5 text-sm font-semibold ${
                      turno.cobrado ? "text-emerald-700 dark:text-emerald-400" : ""
                    }`}
                  >
                    {turno.cobrado && <Check className="h-4 w-4" />}
                    {turno.cobrado ? "Cobrado" : "Pagado hasta ahora"}
                  </span>
                  <span
                    className="font-bold tabular-nums"
                    style={{ fontFamily: "var(--fuente-titulos)" }}
                  >
                    ${totalCobrado.toLocaleString("es-AR")}
                  </span>
                </div>
                <div className="space-y-0.5">
                  {pagos.map((p) => (
                    <div
                      key={p.id}
                      className="flex justify-between text-xs text-muted-foreground"
                    >
                      <span>{nombreMetodo(p)}</span>
                      <span className="tabular-nums">
                        ${p.monto.toLocaleString("es-AR")}
                      </span>
                    </div>
                  ))}
                </div>
                {esDueno(rol) &&
                  pagos.some((p) => p.origen !== "sena") && (
                    <button
                      type="button"
                      onClick={() => setConfirmarAnulacion(true)}
                      className="pt-1 text-xs font-medium text-destructive hover:underline"
                    >
                      Anular cobro…
                    </button>
                  )}
              </div>
            )}
            {!turno.cobrado && turno.estado !== "cancelado" && saldoTurno > 0 && (
              <Button className="w-full" onClick={() => setCobrando(true)}>
                Cobrar ${saldoTurno.toLocaleString("es-AR")}
              </Button>
            )}

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

            {/* Reprogramar: nueva fecha/hora y/o cambio de profesional */}
            {/* Un turno cobrado no se reprograma: el backend lo rechaza (la
                plata ya quedó atribuida a ese día y ese profesional). */}
            {(turno.estado === "pendiente" || turno.estado === "confirmado") &&
              !turno.cobrado && (
              <div className="rounded-xl border bg-card p-3">
                {!reprogramando ? (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={abrirReprogramar}
                  >
                    <CalendarClock className="mr-1.5 h-4 w-4" />
                    Reprogramar / cambiar profesional
                  </Button>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Reprogramar turno
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        type="date"
                        value={nuevaFecha}
                        onChange={(e) => setNuevaFecha(e.target.value)}
                      />
                      <Input
                        type="time"
                        value={nuevaHora}
                        onChange={(e) => setNuevaHora(e.target.value)}
                      />
                    </div>
                    <select
                      value={nuevoRecurso}
                      onChange={(e) => setNuevoRecurso(e.target.value)}
                      className="w-full rounded-md border bg-transparent px-3 py-2 text-sm"
                    >
                      {recursos.length === 0 && (
                        <option value={String(turno.recurso_id ?? "")}>
                          {turno.recurso_nombre ?? "Mismo profesional"}
                        </option>
                      )}
                      {recursos.map((r) => (
                        <option key={r.id} value={String(r.id)}>
                          {r.nombre}
                        </option>
                      ))}
                    </select>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        className="flex-1"
                        onClick={() => setReprogramando(false)}
                      >
                        Cancelar
                      </Button>
                      <Button
                        className="flex-1"
                        disabled={moviendo}
                        onClick={confirmarReprogramar}
                      >
                        {moviendo ? "Moviendo…" : "Confirmar cambio"}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Pedir reseña: solo con el turno finalizado, que es cuando el
                cliente todavía está en el local y contento. Pedirla antes es
                pedirle opinión de algo que no terminó. */}
            {turno.estado === "finalizado" && (
              <Button
                variant="outline"
                className="w-full justify-between"
                disabled={pidiendoResena || resenaEnviada}
                onClick={async () => {
                  setPidiendoResena(true);
                  try {
                    const r = await pedirResena(turno.id);
                    setResenaEnviada(true);
                    toast.success(`Pedido de reseña enviado a ${r.email}`);
                  } catch (err) {
                    toast.error(
                      err instanceof ApiError
                        ? err.message
                        : "No se pudo enviar el pedido",
                    );
                  } finally {
                    setPidiendoResena(false);
                  }
                }}
              >
                <span>
                  {resenaEnviada
                    ? "Reseña pedida"
                    : pidiendoResena
                      ? "Enviando…"
                      : "Pedirle una reseña"}
                </span>
                <Star className="h-4 w-4" />
              </Button>
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
            {/* Plata ya registrada. El sistema NO la saca solo de la caja: si
                el cobro fue un error, hay que anular el movimiento a mano.
                Sin este aviso, el arqueo del día cierra con una diferencia
                que después nadie sabe de dónde salió. */}
            {(turno.pagado_total ?? 0) > 0 &&
              (esReapertura(turno.estado) || confirmar === "cancelado") && (
                <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  <p className="font-medium">
                    Este turno tiene ${(turno.pagado_total ?? 0).toLocaleString("es-AR")} ya
                    cobrados
                    {(turno.senado ?? 0) > 0 &&
                      ` (incluye $${(turno.senado ?? 0).toLocaleString("es-AR")} de seña)`}
                    .
                  </p>
                  <p className="mt-1">
                    {confirmar === "cancelado"
                      ? "Para cancelarlo, primero anulá el cobro (botón «Anular cobro…» del detalle). La seña online, si la hay, queda como ingreso."
                      : "Esa plata queda registrada. Si el cobro fue un error, usá «Anular cobro…» en el detalle del turno: saca la plata de la caja y de las estadísticas."}
                  </p>
                </div>
              )}
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

      {/* Anular cobro: revierte pagos, caja y saldo de gift card. */}
      <AlertDialog open={confirmarAnulacion} onOpenChange={setConfirmarAnulacion}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Anular el cobro de este turno?</AlertDialogTitle>
            <AlertDialogDescription>
              Los pagos quedan registrados como anulados (con tu usuario y la
              hora), salen de la caja y de las estadísticas, y si se usó una
              gift card se le devuelve el saldo. La seña online no se toca. Si
              la caja de ese día ya se cerró, no se puede: cargá un ajuste en
              la caja actual.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={anulando}>No, volver</AlertDialogCancel>
            <AlertDialogAction
              disabled={anulando}
              onClick={ejecutarAnulacion}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {anulando ? "Anulando…" : "Sí, anular cobro"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <CobroDialog
        turnoId={turno.id}
        total={totalTurno}
        senado={totalCobrado}
        abierto={cobrando}
        onCerrar={() => setCobrando(false)}
        onCobrado={() => {
          if (turno) pagosDeTurno(turno.id).then(setPagos).catch(() => {});
          onCambio();
        }}
      />
    </>
  );
}

/** Una fila de dato: etiqueta a la izquierda, valor a la derecha. */
function Fila({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-3.5 py-2.5 text-sm">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="truncate text-right font-medium">{children}</span>
    </div>
  );
}