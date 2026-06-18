"use client";

/**
 * Diálogo para crear o editar un plan de abono.
 *
 * Si recibe un `plan`, edita; si no, crea. El dueño define nombre, precio,
 * si es ilimitado o por cantidad, y qué servicios cubre (de los ya creados).
 */

import { useState, useEffect } from "react";
import { crearPlan, editarPlan, PlanAbono } from "@/lib/membresias-api";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface PlanDialogProps {
  plan: PlanAbono | null; // null = crear, con valor = editar
  abierto: boolean;
  onCerrar: () => void;
  onGuardado: () => void;
}

export function PlanDialog({ plan, abierto, onCerrar, onGuardado }: PlanDialogProps) {
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [precio, setPrecio] = useState("");
  const [ilimitado, setIlimitado] = useState(true);
  const [cantidadCupos, setCantidadCupos] = useState("");
  const [cubiertos, setCubiertos] = useState<number[]>([]);

  // Cargar servicios al abrir
  useEffect(() => {
    if (!abierto) return;
    listarServicios().then((d) => setServicios(d.items)).catch(() => {});
  }, [abierto]);

  // Precargar valores si es editar
  useEffect(() => {
    if (plan) {
      setNombre(plan.nombre);
      setDescripcion(plan.descripcion ?? "");
      setPrecio(String(plan.precio));
      setIlimitado(plan.ilimitado);
      setCantidadCupos(plan.cantidad_cupos != null ? String(plan.cantidad_cupos) : "");
      setCubiertos(plan.servicios_cubiertos ?? []);
    } else {
      // Reset para crear
      setNombre("");
      setDescripcion("");
      setPrecio("");
      setIlimitado(true);
      setCantidadCupos("");
      setCubiertos([]);
    }
  }, [plan, abierto]);

  function toggleServicio(id: number) {
    setCubiertos((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!nombre.trim()) return toast.error("El nombre es obligatorio");
    if (!precio) return toast.error("El precio es obligatorio");

    const datos = {
      nombre,
      descripcion: descripcion || undefined,
      precio: Number(precio),
      ilimitado,
      cantidad_cupos: !ilimitado && cantidadCupos ? Number(cantidadCupos) : undefined,
      servicios_cubiertos: cubiertos,
    };

    setGuardando(true);
    try {
      if (plan) {
        await editarPlan(plan.id, datos);
        toast.success("Plan actualizado");
      } else {
        await crearPlan(datos);
        toast.success("Plan creado");
      }
      onGuardado();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al guardar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{plan ? "Editar plan" : "Nuevo plan de abono"}</DialogTitle>
          <DialogDescription>
            Definí el abono: precio, qué incluye y qué servicios cubre.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="p-nombre">Nombre *</Label>
            <Input
              id="p-nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="PRO, Básico…"
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="p-desc">Descripción</Label>
            <Textarea
              id="p-desc"
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              placeholder="Cortes ilimitados durante el mes…"
              rows={2}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="p-precio">Precio *</Label>
            <Input
              id="p-precio"
              type="number"
              min="0"
              value={precio}
              onChange={(e) => setPrecio(e.target.value)}
              placeholder="50000"
              required
            />
          </div>

          {/* Ilimitado o por cantidad */}
          <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="p-ilimitado">¿Cortes ilimitados?</Label>
                <p className="text-xs text-muted-foreground">
                  Si está activo, el cliente viene las veces que quiera.
                </p>
              </div>
              <Switch
                id="p-ilimitado"
                checked={ilimitado}
                onCheckedChange={setIlimitado}
              />
            </div>
            {!ilimitado && (
              <div className="space-y-2 border-t pt-3">
                <Label htmlFor="p-cupos">Cantidad de cortes incluidos</Label>
                <Input
                  id="p-cupos"
                  type="number"
                  min="1"
                  value={cantidadCupos}
                  onChange={(e) => setCantidadCupos(e.target.value)}
                  placeholder="4"
                />
              </div>
            )}
          </div>

          {/* Servicios cubiertos */}
          <div className="space-y-2">
            <Label>Servicios que cubre</Label>
            <p className="text-xs text-muted-foreground">
              Marcá los servicios incluidos. Si no marcás ninguno, cubre todos.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {servicios.map((s) => {
                const activo = cubiertos.includes(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => toggleServicio(s.id)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      activo
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-border text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {s.nombre}
                  </button>
                );
              })}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : plan ? "Guardar cambios" : "Crear plan"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}