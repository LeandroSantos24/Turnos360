"use client";

/** Diálogo para crear un servicio nuevo. */

import { useState } from "react";
import { crearServicio } from "@/lib/servicios-api";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function NuevoServicioDialog({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [duracion, setDuracion] = useState("30");
  const [paso, setPaso] = useState("15");
  const [precio, setPrecio] = useState("");

  function limpiar() {
    setNombre("");
    setDuracion("30");
    setPaso("15");
    setPrecio("");
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    try {
      await crearServicio({
        nombre,
        duracion_min: Number(duracion),
        paso_turno_min: Number(paso),
        precio: precio ? Number(precio) : undefined,
      });
      toast.success("Servicio creado");
      limpiar();
      setAbierto(false);
      onCreado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al crear");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button>Nuevo servicio</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo servicio</DialogTitle>
          <DialogDescription>
            Definí qué ofrecés, cuánto dura y cada cuánto se da turno.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="nombre">Nombre *</Label>
            <Input
              id="nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Corte, Color, Barba…"
              required
              autoFocus
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="duracion">Duración (min) *</Label>
              <Input
                id="duracion"
                type="number"
                min="1"
                value={duracion}
                onChange={(e) => setDuracion(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="paso">Turno cada (min)</Label>
              <Input
                id="paso"
                type="number"
                min="1"
                value={paso}
                onChange={(e) => setPaso(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="precio">Precio</Label>
            <Input
              id="precio"
              type="number"
              min="0"
              value={precio}
              onChange={(e) => setPrecio(e.target.value)}
              placeholder="9000"
            />
          </div>

          <DialogFooter>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Crear servicio"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}