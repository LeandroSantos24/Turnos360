"use client";

/**
 * Cupones de descuento: el negocio crea códigos (INAUGURACION20) y elige
 * tipo (porcentaje o monto), a qué servicios aplica (vacío = todos),
 * vencimiento y tope de usos. El cliente lo carga al reservar online.
 */

import { useCallback, useEffect, useState } from "react";
import {
  TicketPercent,
  Plus,
  MoreVertical,
  Pencil,
  Trash2,
  Check,
  CalendarClock,
  Hash,
} from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  listarCupones,
  crearCupon,
  editarCupon,
  borrarCupon,
  type Cupon,
  type CuponDatos,
} from "@/lib/cupones-api";
import { listarServicios, type Servicio } from "@/lib/servicios-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NUM = { fontVariantNumeric: "tabular-nums" } as const;

function pesos(n: number): string {
  return `$${n.toLocaleString("es-AR")}`;
}

const VACIO: CuponDatos = {
  codigo: "",
  tipo: "porcentaje",
  valor: 10,
  vence_el: null,
  max_usos: null,
  servicios_ids: [],
  activo: true,
};

export default function CuponesPage() {
  const [cupones, setCupones] = useState<Cupon[]>([]);
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState(false);
  const [editando, setEditando] = useState<Cupon | null>(null);
  const [borrando, setBorrando] = useState<Cupon | null>(null);

  const cargar = useCallback(() => {
    listarCupones()
      .then(setCupones)
      .catch(() => toast.error("No se pudieron cargar los cupones"))
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => {
    cargar();
    listarServicios()
      .then((r) => setServicios(r.items))
      .catch(() => setServicios([]));
  }, [cargar]);

  function nombreServicios(ids: number[]): string {
    if (!ids.length) return "Todos los servicios";
    const nombres = ids
      .map((id) => servicios.find((s) => s.id === id)?.nombre)
      .filter(Boolean);
    return nombres.length ? nombres.join(", ") : `${ids.length} servicios`;
  }

  async function confirmarBorrado() {
    if (!borrando) return;
    try {
      await borrarCupon(borrando.id);
      toast.success(`Cupón ${borrando.codigo} eliminado`);
      setBorrando(null);
      cargar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo eliminar");
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cupones</h1>
          <p className="text-sm text-muted-foreground">
            Códigos de descuento para la reserva online.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditando(null);
            setAbierto(true);
          }}
        >
          <Plus className="mr-1.5 h-4 w-4" /> Nuevo cupón
        </Button>
      </div>

      {cargando ? (
        <p className="py-16 text-center text-sm text-muted-foreground">Cargando…</p>
      ) : cupones.length === 0 ? (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <TicketPercent className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="mt-3 font-medium">Todavía no hay cupones</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Creá un código (ej. INAUGURACION20) y compartilo en tu Instagram: el
            cliente lo carga al reservar y el descuento se aplica solo.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cupones.map((c) => {
            const vencido = c.vence_el != null && new Date(c.vence_el + "T23:59:59") < new Date();
            const agotado = c.max_usos != null && c.usos >= c.max_usos;
            const vigente = c.activo && !vencido && !agotado;
            return (
              <div
                key={c.id}
                className={`flex flex-col rounded-2xl border bg-card p-5 ${vigente ? "" : "opacity-60"}`}
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <p className="font-mono text-lg font-bold tracking-wide">{c.codigo}</p>
                    <p className="mt-0.5 text-2xl font-extrabold tabular-nums text-primary" style={NUM}>
                      {c.tipo === "porcentaje" ? `${c.valor}% OFF` : `${pesos(c.valor)} OFF`}
                    </p>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-accent">
                      <MoreVertical className="h-4 w-4" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => {
                          setEditando(c);
                          setAbierto(true);
                        }}
                      >
                        <Pencil className="mr-2 h-4 w-4" /> Editar
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-red-600 focus:text-red-600"
                        onClick={() => setBorrando(c)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" /> Eliminar
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <p
                  className="mt-2 text-xs text-muted-foreground"
                  style={{
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                    minHeight: "2rem",
                  }}
                  title={nombreServicios(c.servicios_ids)}
                >
                  {nombreServicios(c.servicios_ids)}
                </p>

                <div className="mb-3 mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Hash className="h-3 w-3" />
                    <span className="tabular-nums" style={NUM}>
                      {c.usos}
                      {c.max_usos != null ? ` / ${c.max_usos}` : ""} usos
                    </span>
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <CalendarClock className="h-3 w-3" />
                    {c.vence_el
                      ? `Vence ${new Date(c.vence_el + "T00:00:00").toLocaleDateString("es-AR")}`
                      : "Sin vencimiento"}
                  </span>
                </div>

                <div className="mt-auto border-t pt-2.5">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      vigente
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {!c.activo ? "Inactivo" : vencido ? "Vencido" : agotado ? "Agotado" : "Vigente"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <CuponDialog
        abierto={abierto}
        cupon={editando}
        servicios={servicios}
        onCerrar={() => setAbierto(false)}
        onGuardado={() => {
          setAbierto(false);
          cargar();
        }}
      />

      <AlertDialog open={borrando != null} onOpenChange={(o) => !o && setBorrando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar el cupón {borrando?.codigo}?</AlertDialogTitle>
            <AlertDialogDescription>
              Los clientes ya no van a poder usarlo. Si preferís pausarlo sin
              perderlo, editalo y desactivalo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={confirmarBorrado}
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/* ── Diálogo crear / editar ─────────────────────────────────────────────── */

function CuponDialog({
  abierto,
  cupon,
  servicios,
  onCerrar,
  onGuardado,
}: {
  abierto: boolean;
  cupon: Cupon | null;
  servicios: Servicio[];
  onCerrar: () => void;
  onGuardado: () => void;
}) {
  const [datos, setDatos] = useState<CuponDatos>(VACIO);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setDatos(
        cupon
          ? {
              codigo: cupon.codigo,
              tipo: cupon.tipo,
              valor: cupon.valor,
              vence_el: cupon.vence_el,
              max_usos: cupon.max_usos,
              servicios_ids: cupon.servicios_ids,
              activo: cupon.activo,
            }
          : VACIO,
      );
    }
  }, [abierto, cupon]);

  function set<K extends keyof CuponDatos>(campo: K, valor: CuponDatos[K]) {
    setDatos((d) => ({ ...d, [campo]: valor }));
  }

  function toggleServicio(id: number) {
    set(
      "servicios_ids",
      datos.servicios_ids.includes(id)
        ? datos.servicios_ids.filter((x) => x !== id)
        : [...datos.servicios_ids, id],
    );
  }

  async function guardar() {
    if (datos.codigo.trim().length < 3) {
      toast.error("El código necesita al menos 3 caracteres");
      return;
    }
    if (!datos.valor || datos.valor <= 0) {
      toast.error("Poné el valor del descuento");
      return;
    }
    if (datos.tipo === "porcentaje" && datos.valor > 100) {
      toast.error("Un porcentaje no puede superar 100");
      return;
    }
    setGuardando(true);
    try {
      if (cupon) {
        await editarCupon(cupon.id, datos);
        toast.success("Cupón actualizado");
      } else {
        await crearCupon(datos);
        toast.success(`Cupón ${datos.codigo.toUpperCase()} creado`);
      }
      onGuardado();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{cupon ? "Editar cupón" : "Nuevo cupón"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label htmlFor="cup-codigo">Código</Label>
            <Input
              id="cup-codigo"
              value={datos.codigo}
              onChange={(e) => set("codigo", e.target.value.toUpperCase().replace(/\s/g, ""))}
              placeholder="INAUGURACION20"
              className="font-mono uppercase"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Es lo que el cliente escribe al reservar. Corto y fácil de recordar.
            </p>
          </div>

          {/* Tipo de descuento */}
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                { id: "porcentaje", t: "Porcentaje", d: "Ej: 20% del precio" },
                { id: "monto", t: "Monto fijo", d: "Ej: $2.000 menos" },
              ] as const
            ).map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => set("tipo", o.id)}
                className={`rounded-xl border p-3 text-left transition-colors ${
                  datos.tipo === o.id
                    ? "border-primary bg-primary/5"
                    : "hover:border-muted-foreground/40"
                }`}
              >
                <p className="text-sm font-medium">{o.t}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{o.d}</p>
              </button>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="cup-valor">
                {datos.tipo === "porcentaje" ? "Porcentaje (%)" : "Monto (ARS)"}
              </Label>
              <Input
                id="cup-valor"
                type="number"
                inputMode="numeric"
                min={1}
                max={datos.tipo === "porcentaje" ? 100 : undefined}
                value={datos.valor || ""}
                onChange={(e) => set("valor", Number(e.target.value))}
                placeholder={datos.tipo === "porcentaje" ? "20" : "2000"}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cup-vence">Vence el (opcional)</Label>
              <Input
                id="cup-vence"
                type="date"
                value={datos.vence_el ?? ""}
                onChange={(e) => set("vence_el", e.target.value || null)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cup-usos">Límite de usos (opcional)</Label>
            <Input
              id="cup-usos"
              type="number"
              inputMode="numeric"
              min={1}
              value={datos.max_usos ?? ""}
              onChange={(e) => set("max_usos", e.target.value ? Number(e.target.value) : null)}
              placeholder="Ej: 20 (los primeros 20 clientes)"
            />
          </div>

          {/* Servicios cubiertos */}
          <div className="space-y-2">
            <Label>¿Para qué servicios vale?</Label>
            <p className="-mt-1 text-xs text-muted-foreground">
              Si no marcás ninguno, vale para <b>todos</b> los servicios.
            </p>
            <div className="flex flex-wrap gap-2">
              {servicios.map((s) => {
                const sel = datos.servicios_ids.includes(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggleServicio(s.id)}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors ${
                      sel
                        ? "border-primary bg-primary/10 text-primary"
                        : "hover:border-muted-foreground/40"
                    }`}
                  >
                    {sel && <Check className="h-3.5 w-3.5" />}
                    {s.nombre}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-xl border p-3">
            <div>
              <p className="text-sm font-medium">Cupón activo</p>
              <p className="text-xs text-muted-foreground">
                Desactivalo para pausarlo sin borrarlo.
              </p>
            </div>
            <Switch checked={datos.activo} onCheckedChange={(v) => set("activo", v)} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCerrar}>
            Cancelar
          </Button>
          <Button onClick={guardar} disabled={guardando}>
            {guardando ? "Guardando…" : cupon ? "Guardar cambios" : "Crear cupón"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
