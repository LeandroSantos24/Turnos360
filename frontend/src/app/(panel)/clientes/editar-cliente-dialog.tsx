"use client";

/**
 * Diálogo para editar un cliente existente.
 *
 * Usa el componente compartido CamposCliente. Precarga los valores del cliente
 * y al guardar manda todos los campos (el backend actualiza lo que cambió).
 */

import { useState, useEffect } from "react";
import { editarCliente, Cliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { CamposCliente, DatosCliente } from "./campos-cliente";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface EditarClienteDialogProps {
  cliente: Cliente | null;
  abierto: boolean;
  onCerrar: () => void;
  onEditado: () => void;
}

export function EditarClienteDialog({
  cliente,
  abierto,
  onCerrar,
  onEditado,
}: EditarClienteDialogProps) {
  const [guardando, setGuardando] = useState(false);
  const [datos, setDatos] = useState<DatosCliente | null>(null);

  // Precargar los datos del cliente al abrir
  useEffect(() => {
    if (!cliente) return;
    setDatos({
      nombre: cliente.nombre,
      apellido: cliente.apellido ?? "",
      dni: cliente.dni ?? "",
      email: cliente.email ?? "",
      telefono: cliente.telefono ?? "",
      fecha_nacimiento: cliente.fecha_nacimiento ?? "",
      canal_adquisicion: cliente.canal_adquisicion ?? "",
      etiquetas: cliente.etiquetas ?? [],
      observaciones: cliente.observaciones ?? "",
    });
  }, [cliente]);

  function cambiar<K extends keyof DatosCliente>(campo: K, valor: DatosCliente[K]) {
    setDatos((d) => (d ? { ...d, [campo]: valor } : d));
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!cliente || !datos) return;
    if (!datos.nombre.trim()) {
      toast.error("El nombre es obligatorio");
      return;
    }

    setGuardando(true);
    try {
      await editarCliente(cliente.id, {
        nombre: datos.nombre,
        apellido: datos.apellido || undefined,
        dni: datos.dni || undefined,
        email: datos.email || undefined,
        telefono: datos.telefono || undefined,
        fecha_nacimiento: datos.fecha_nacimiento || undefined,
        canal_adquisicion: datos.canal_adquisicion || undefined,
        etiquetas: datos.etiquetas,
        observaciones: datos.observaciones || undefined,
      });
      toast.success("Cliente actualizado");
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
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Editar cliente</DialogTitle>
          <DialogDescription>Modificá los datos del cliente.</DialogDescription>
        </DialogHeader>

        {datos && (
          <form onSubmit={guardar}>
            <CamposCliente datos={datos} onCambio={cambiar} />
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" onClick={onCerrar}>
                Cancelar
              </Button>
              <Button type="submit" disabled={guardando}>
                {guardando ? "Guardando…" : "Guardar cambios"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}