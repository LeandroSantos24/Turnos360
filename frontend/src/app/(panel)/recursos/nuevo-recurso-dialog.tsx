"use client";

/**
 * Diálogo para crear un recurso nuevo.
 *
 * Todo recurso nuevo nace como PERSONA. Los tipos "box" y "equipo" siguen
 * existiendo en la base (y se pueden ver y editar en los recursos viejos que
 * ya los tengan), pero se sacaron del alta: no se agendan, no aparecen en la
 * página de reservas y no se les puede asignar un turno. Ofrecerlos en el
 * alta era invitar al dueño a cargar algo que después no le sirve.
 */

import { useState } from "react";
import { crearRecurso } from "@/lib/recursos-api";
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
import { SelectorUsuarioVinculado } from "./selector-usuario-vinculado";
import { SelectorSucursal } from "./selector-sucursal";

export function NuevoRecursoDialog({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [usuarioId, setUsuarioId] = useState<number | null>(null);
  // null = "el que decida el backend", que es el local principal. Es lo que
  // pasa siempre en un negocio de un solo local, donde el selector ni aparece.
  const [sucursalId, setSucursalId] = useState<number | null>(null);

  function limpiar() {
    setNombre("");
    setUsuarioId(null);
    setSucursalId(null);
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    try {
      await crearRecurso({
        nombre,
        tipo: "persona",
        usuario_id: usuarioId,
        sucursal_id: sucursalId,
      });
      toast.success("Recurso creado");
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
        <Button>Nuevo recurso</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo recurso</DialogTitle>
          <DialogDescription>
            La persona que atiende: barbero, médico, manicura, profesional.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="nombre">Nombre *</Label>
            <Input
              id="nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Juan, Ana, Dr. Pérez…"
              required
              autoFocus
            />
          </div>
          <SelectorSucursal value={sucursalId} onChange={setSucursalId} />

          <SelectorUsuarioVinculado value={usuarioId} onChange={setUsuarioId} />

          <DialogFooter>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Crear recurso"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
