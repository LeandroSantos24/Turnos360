"use client";

/** Diálogo para crear un recurso nuevo (persona, box o equipo). */

import { useState } from "react";
import { crearRecurso, TipoRecurso } from "@/lib/recursos-api";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SelectorUsuarioVinculado } from "./selector-usuario-vinculado";

export function NuevoRecursoDialog({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<TipoRecurso>("persona");
  const [usuarioId, setUsuarioId] = useState<number | null>(null);

  function limpiar() {
    setNombre("");
    setTipo("persona");
    setUsuarioId(null);
  }

  function cambiarTipo(v: string) {
    const t = v as TipoRecurso;
    setTipo(t);
    // un box o equipo no tiene login: limpiamos el vínculo
    if (t !== "persona") setUsuarioId(null);
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    try {
      await crearRecurso({
        nombre,
        tipo,
        usuario_id: tipo === "persona" ? usuarioId : null,
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
            Una persona (barbero, médico), un box o un equipo.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="nombre">Nombre *</Label>
            <Input
              id="nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Juan, Box 1, Sillón 3…"
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label>Tipo *</Label>
            <Select value={tipo} onValueChange={cambiarTipo}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="persona">Persona</SelectItem>
                <SelectItem value="box">Box</SelectItem>
                <SelectItem value="equipo">Equipo</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {tipo === "persona" && (
            <SelectorUsuarioVinculado value={usuarioId} onChange={setUsuarioId} />
          )}

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
