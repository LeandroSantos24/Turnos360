"use client";

/**
 * Diálogo para editar un servicio existente.
 *
 * Recibe el servicio a editar, precarga sus valores, y al guardar manda solo
 * los cambios (PATCH). Traduce los campos de carril igual que el de crear.
 */

import { useState, useEffect } from "react";
import { editarServicio, Servicio } from "@/lib/servicios-api";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function aSlug(texto: string): string {
  return texto
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

interface EditarServicioDialogProps {
  servicio: Servicio | null;
  abierto: boolean;
  onCerrar: () => void;
  onEditado: () => void;
}

export function EditarServicioDialog({
  servicio,
  abierto,
  onCerrar,
  onEditado,
}: EditarServicioDialogProps) {
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [duracion, setDuracion] = useState("30");
  const [paso, setPaso] = useState("15");
  const [precio, setPrecio] = useState("");
  const [agendable, setAgendable] = useState(true);
  const [enParalelo, setEnParalelo] = useState(false);
  const [grupo, setGrupo] = useState("");

  // Precargar los valores del servicio cuando se abre
  useEffect(() => {
    if (!servicio) return;
    setNombre(servicio.nombre);
    setDuracion(String(servicio.duracion_min));
    setPaso(String(servicio.paso_turno_min));
    setPrecio(servicio.precio != null ? String(servicio.precio) : "");
    setAgendable(servicio.agendable);
    // Deducir el estado del carril desde grupo_agenda
    const g = servicio.grupo_agenda ?? "";
    if (g.startsWith("solo-")) {
      setEnParalelo(true);
      setGrupo("");
    } else {
      setEnParalelo(false);
      setGrupo(g);
    }
  }, [servicio]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!servicio) return;

    let grupoAgenda: string;
    if (enParalelo) {
      grupoAgenda = `solo-${aSlug(nombre) || "servicio"}`;
    } else {
      grupoAgenda = aSlug(grupo) || `solo-${aSlug(nombre) || "servicio"}`;
    }

    setGuardando(true);
    try {
      await editarServicio(servicio.id, {
        nombre,
        duracion_min: agendable ? Number(duracion) : 1,
        paso_turno_min: agendable ? Number(paso) : 1,
        precio: precio ? Number(precio) : undefined,
        grupo_agenda: agendable ? grupoAgenda : null,
        agendable,
      });
      toast.success("Servicio actualizado");
      onEditado();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al guardar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar servicio</DialogTitle>
          <DialogDescription>Modificá los datos del servicio.</DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="e-nombre">Nombre *</Label>
            <Input
              id="e-nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              required
              autoFocus
            />
          </div>

          {/* ¿Ocupa un turno o es solo para vender? */}
          <div className="flex items-start justify-between gap-3 rounded-xl border bg-muted/30 p-4">
            <div className="space-y-0.5">
              <Label htmlFor="e-agendable">¿Ocupa un turno en la agenda?</Label>
              <p className="text-xs text-muted-foreground">
                Activado: se reserva como turno (corte, color). Desactivado: solo
                se vende como adicional (perfilado, productos) y no aparece al agendar.
              </p>
            </div>
            <Switch id="e-agendable" checked={agendable} onCheckedChange={setAgendable} />
          </div>

          {agendable && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="e-duracion">Duración (min) *</Label>
                <Input
                  id="e-duracion"
                  type="number"
                  min="1"
                  value={duracion}
                  onChange={(e) => setDuracion(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="e-paso">Turno cada (min)</Label>
                <Input
                  id="e-paso"
                  type="number"
                  min="1"
                  value={paso}
                  onChange={(e) => setPaso(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="e-precio">Precio</Label>
            <Input
              id="e-precio"
              type="number"
              min="0"
              value={precio}
              onChange={(e) => setPrecio(e.target.value)}
            />
          </div>

          {agendable && (
            <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="e-paralelo">
                  ¿Se puede dar en paralelo a otros servicios?
                </Label>
                <p className="text-xs text-muted-foreground">
                  Como la barba: se puede hacer aunque el barbero esté con otro
                  servicio al mismo tiempo.
                </p>
              </div>
              <Switch
                id="e-paralelo"
                checked={enParalelo}
                onCheckedChange={setEnParalelo}
              />
            </div>

            {!enParalelo && (
              <div className="space-y-2 border-t pt-3">
                <Label htmlFor="e-grupo">Grupo de bloqueo</Label>
                <Input
                  id="e-grupo"
                  value={grupo}
                  onChange={(e) => setGrupo(e.target.value)}
                  placeholder="corte, tintura…"
                />
                <p className="text-xs text-muted-foreground">
                  Servicios con el mismo grupo no pueden coincidir en horario.
                </p>
              </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar cambios"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}