"use client";

/**
 * Alta y edición de un local. El mismo diálogo para las dos cosas: cambia si
 * viene `sucursal`.
 *
 * La dirección y el teléfono son de acá y no de la empresa a propósito: con
 * dos locales, "la dirección del negocio" deja de existir como dato único, y
 * es lo que el cliente necesita ver en la reserva pública para saber a dónde ir.
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { crearSucursal, editarSucursal, Sucursal } from "@/lib/sucursales-api";
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

export function SucursalDialog({
  abierto,
  sucursal,
  onCerrar,
  onListo,
}: {
  abierto: boolean;
  /** null = alta. Con sucursal = edición. */
  sucursal: Sucursal | null;
  onCerrar: () => void;
  onListo: () => void;
}) {
  const editando = sucursal !== null;
  const [nombre, setNombre] = useState("");
  const [direccion, setDireccion] = useState("");
  const [telefono, setTelefono] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setNombre(sucursal?.nombre ?? "");
    setDireccion(sucursal?.direccion ?? "");
    setTelefono(sucursal?.telefono ?? "");
  }, [abierto, sucursal]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    const datos = {
      nombre: nombre.trim(),
      direccion: direccion.trim() || null,
      telefono: telefono.trim() || null,
    };
    try {
      if (editando) {
        await editarSucursal(sucursal.id, datos);
        toast.success("Cambios guardados");
      } else {
        await crearSucursal(datos);
        toast.success(`«${datos.nombre}» ya es parte del negocio`);
      }
      onListo();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editando ? "Editar local" : "Nuevo local"}</DialogTitle>
          <DialogDescription>
            {editando
              ? "El nombre es el que van a ver tus clientes al elegir dónde reservar."
              : "Después vas a poder asignarle profesionales y servicios."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="s-nombre">Nombre *</Label>
            <Input
              id="s-nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Centro"
              required
              maxLength={120}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="s-direccion">Dirección</Label>
            <Input
              id="s-direccion"
              value={direccion}
              onChange={(e) => setDireccion(e.target.value)}
              placeholder="San Martín 1234"
              maxLength={200}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="s-telefono">Teléfono</Label>
            <Input
              id="s-telefono"
              value={telefono}
              onChange={(e) => setTelefono(e.target.value)}
              placeholder="261 400 0000"
              maxLength={40}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={guardando || !nombre.trim()}>
              {guardando ? "Guardando…" : editando ? "Guardar" : "Crear local"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
