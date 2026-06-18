"use client";

/**
 * Pantalla de Membresías (/membresias).
 * Lista los planes de abono con crear/editar/borrar.
 */

import { useEffect, useState, useCallback } from "react";
import { listarPlanes, borrarPlan, PlanAbono } from "@/lib/membresias-api";
import { ApiError } from "@/lib/api";
import { PlanDialog } from "./plan-dialog";
import { toast } from "sonner";
import { MoreVertical, Pencil, Trash2, Plus, Infinity as InfinityIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

export default function MembresiasPage() {
  const [planes, setPlanes] = useState<PlanAbono[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [editando, setEditando] = useState<PlanAbono | null>(null);
  const [aBorrar, setABorrar] = useState<PlanAbono | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarPlanes();
      setPlanes(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function confirmarBorrar() {
    if (!aBorrar) return;
    try {
      await borrarPlan(aBorrar.id);
      toast.success(`"${aBorrar.nombre}" eliminado`);
      setABorrar(null);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo borrar");
    }
  }

  function abrirCrear() {
    setEditando(null);
    setDialogAbierto(true);
  }

  function abrirEditar(plan: PlanAbono) {
    setEditando(plan);
    setDialogAbierto(true);
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Membresías</h1>
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums">{planes.length}</span>{" "}
            {planes.length === 1 ? "plan de abono" : "planes de abono"}
          </p>
        </div>
        <Button onClick={abrirCrear}>
          <Plus size={16} className="mr-1" />
          Nuevo plan
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {cargando && !error && (
        <p className="text-sm text-muted-foreground">Cargando planes…</p>
      )}

      {!cargando && !error && planes.length === 0 && (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            Todavía no hay planes de abono. Creá el primero (ej. &quot;PRO&quot;).
          </p>
        </div>
      )}

      {!cargando && !error && planes.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {planes.map((plan) => (
            <div
              key={plan.id}
              className="relative rounded-2xl border bg-card p-5"
            >
              {/* Menú de acciones */}
              <div className="absolute right-3 top-3">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreVertical size={16} />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => abrirEditar(plan)}>
                      <Pencil size={14} className="mr-2" />
                      Editar
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setABorrar(plan)}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 size={14} className="mr-2" />
                      Borrar
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Nombre + precio */}
              <h3
                className="text-lg font-bold"
                style={{ fontFamily: "Syne, sans-serif" }}
              >
                {plan.nombre}
              </h3>
              <p
                className="mt-1 text-2xl font-bold text-primary"
                style={{
                  fontFamily: "Syne, sans-serif",
                  fontVariantNumeric: "lining-nums tabular-nums",
                }}
              >
                ${plan.precio.toLocaleString("es-AR")}
              </p>

              {plan.descripcion && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {plan.descripcion}
                </p>
              )}

              {/* Tipo: ilimitado o por cantidad */}
              <div className="mt-4 flex items-center gap-1.5 text-sm">
                {plan.ilimitado ? (
                  <>
                    <InfinityIcon size={16} className="text-primary" />
                    <span className="font-medium">Cortes ilimitados</span>
                  </>
                ) : (
                  <span className="font-medium tabular-nums">
                    {plan.cantidad_cupos} cortes incluidos
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Diálogo crear/editar */}
      <PlanDialog
        plan={editando}
        abierto={dialogAbierto}
        onCerrar={() => setDialogAbierto(false)}
        onGuardado={cargar}
      />

      {/* Confirmación de borrado */}
      <AlertDialog open={aBorrar !== null} onOpenChange={(o) => !o && setABorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Borrar este plan?</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a eliminar &quot;{aBorrar?.nombre}&quot;. Las membresías ya
              asignadas no se borran, pero no podrás asignar este plan de nuevo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmarBorrar}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}