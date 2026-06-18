"use client";

/** Diálogo para editar un recurso existente (nombre + tipo). */

import { useState, useEffect } from "react";
import { editarRecurso, Recurso, TipoRecurso } from "@/lib/recursos-api";
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
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface EditarRecursoDialogProps {
  recurso: Recurso | null;
  abierto: boolean;
  onCerrar: () => void;
  onEditado: () => void;
}

export function EditarRecursoDialog({
  recurso,
  abierto,
  onCerrar,
  onEditado,
}: EditarRecursoDialogProps) {
  const [guardando, setGuardando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<TipoRecurso>("persona");

  useEffect(() => {
    if (!recurso) return;
    setNombre(recurso.nombre);
    setTipo(recurso.tipo);
  }, [recurso]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!recurso) return;
    setGuardando(true);
    try {
      await editarRecurso(recurso.id, { nombre, tipo });
      toast.success("Recurso actualizado");
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
          <DialogTitle>Editar recurso</DialogTitle>
          <DialogDescription>Modificá los datos del recurso.</DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="er-nombre">Nombre *</Label>
            <Input
              id="er-nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label>Tipo *</Label>
            <Select value={tipo} onValueChange={(v) => setTipo(v as TipoRecurso)}>
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