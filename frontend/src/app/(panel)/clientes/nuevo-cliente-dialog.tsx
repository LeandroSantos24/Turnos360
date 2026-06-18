"use client";

/**
 * Diálogo para crear un cliente nuevo.
 *
 * Usa el componente compartido CamposCliente (los mismos campos que editar).
 * Acá solo vive el estado, la validación mínima y el guardado.
 */

import { useState } from "react";
import { crearCliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { CamposCliente, DatosCliente, CLIENTE_VACIO } from "./campos-cliente";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function NuevoClienteDialog({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [datos, setDatos] = useState<DatosCliente>(CLIENTE_VACIO);

  function cambiar<K extends keyof DatosCliente>(campo: K, valor: DatosCliente[K]) {
    setDatos((d) => ({ ...d, [campo]: valor }));
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!datos.nombre.trim()) {
      toast.error("El nombre es obligatorio");
      return;
    }

    setGuardando(true);
    try {
      await crearCliente({
        nombre: datos.nombre,
        apellido: datos.apellido || undefined,
        dni: datos.dni || undefined,
        email: datos.email || undefined,
        telefono: datos.telefono || undefined,
        fecha_nacimiento: datos.fecha_nacimiento || undefined,
        canal_adquisicion: datos.canal_adquisicion || undefined,
        etiquetas: datos.etiquetas.length > 0 ? datos.etiquetas : undefined,
        observaciones: datos.observaciones || undefined,
      });
      toast.success("Cliente creado");
      setDatos(CLIENTE_VACIO);
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
        <Button>Nuevo cliente</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nuevo cliente</DialogTitle>
          <DialogDescription>
            Cargá los datos del cliente. Solo el nombre es obligatorio.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar}>
          <CamposCliente datos={datos} onCambio={cambiar} />
          <DialogFooter className="mt-6">
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Crear cliente"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}