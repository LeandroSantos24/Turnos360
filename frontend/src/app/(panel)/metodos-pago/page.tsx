"use client";

/**
 * Métodos de pago (/metodos-pago). ABM con comisión por método.
 * La comisión se usa al cobrar para calcular el neto real (N-55).
 */

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2 } from "lucide-react";

import {
  listarMetodos,
  crearMetodo,
  editarMetodo,
  borrarMetodo,
  MetodoPago,
} from "@/lib/finanzas-api";
import { ApiError } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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

export default function MetodosPagoPage() {
  const [metodos, setMetodos] = useState<MetodoPago[]>([]);
  const [cargando, setCargando] = useState(true);
  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [editando, setEditando] = useState<MetodoPago | null>(null);
  const [nombre, setNombre] = useState("");
  const [comision, setComision] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [aBorrar, setABorrar] = useState<MetodoPago | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setMetodos(await listarMetodos());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function abrirNuevo() {
    setEditando(null);
    setNombre("");
    setComision("");
    setDialogAbierto(true);
  }

  function abrirEditar(m: MetodoPago) {
    setEditando(m);
    setNombre(m.nombre);
    setComision(String(m.comision_pct));
    setDialogAbierto(true);
  }

  async function guardar() {
    if (!nombre.trim()) return;
    setGuardando(true);
    try {
      const datos = { nombre: nombre.trim(), comision_pct: Number(comision) || 0 };
      if (editando) {
        await editarMetodo(editando.id, datos);
        toast.success("Método actualizado");
      } else {
        await crearMetodo(datos);
        toast.success("Método creado");
      }
      setDialogAbierto(false);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  async function toggleActivo(m: MetodoPago) {
    try {
      await editarMetodo(m.id, { activo: !m.activo });
      setMetodos((prev) =>
        prev.map((x) => (x.id === m.id ? { ...x, activo: !x.activo } : x)),
      );
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar");
    }
  }

  async function confirmarBorrar() {
    if (!aBorrar) return;
    try {
      await borrarMetodo(aBorrar.id);
      toast.success("Método eliminado");
      setMetodos((prev) => prev.filter((x) => x.id !== aBorrar.id));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo eliminar");
    } finally {
      setABorrar(null);
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
            Métodos de pago
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Cómo cobrás. La comisión se descuenta del neto en cada cobro.
          </p>
        </div>
        <Button onClick={abrirNuevo}>
          <Plus className="mr-1.5 h-4 w-4" /> Nuevo método
        </Button>
      </div>

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : metodos.length === 0 ? (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            Todavía no cargaste métodos. Empezá con Efectivo, Débito, Transferencia…
          </p>
        </div>
      ) : (
        <div className="divide-y overflow-hidden rounded-2xl border bg-card">
          {metodos.map((m) => (
            <div key={m.id} className="flex items-center gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{m.nombre}</p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {m.comision_pct > 0 ? `${m.comision_pct}% de comisión` : "Sin comisión"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {m.activo ? "Activo" : "Inactivo"}
                </span>
                <Switch checked={m.activo} onCheckedChange={() => toggleActivo(m)} />
              </div>
              <Button variant="ghost" size="icon" onClick={() => abrirEditar(m)}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setABorrar(m)}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={dialogAbierto} onOpenChange={setDialogAbierto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editando ? "Editar método" : "Nuevo método de pago"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="m-nombre">Nombre *</Label>
              <Input
                id="m-nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Efectivo, Débito, Mercado Pago…"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="m-comision">Comisión (%)</Label>
              <Input
                id="m-comision"
                type="number"
                min="0"
                max="100"
                value={comision}
                onChange={(e) => setComision(e.target.value)}
                placeholder="0"
              />
              <p className="text-xs text-muted-foreground">
                Ej. crédito 6%, Mercado Pago 8%. Dejá 0 si no tiene.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogAbierto(false)}>
              Cancelar
            </Button>
            <Button onClick={guardar} disabled={guardando || !nombre.trim()}>
              {guardando ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={aBorrar !== null} onOpenChange={(o) => !o && setABorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar el método?</AlertDialogTitle>
            <AlertDialogDescription>
              Se eliminará <span className="font-medium">{aBorrar?.nombre}</span>. Los cobros
              ya registrados con este método no se modifican.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmarBorrar}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}