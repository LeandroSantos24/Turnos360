"use client";

/**
 * Pantalla de Membresías (/membresias).
 * Resumen de rentabilidad arriba + planes con sus números + CRUD.
 */

import { useEffect, useState, useCallback } from "react";
import {
  listarPlanes,
  borrarPlan,
  estadisticasMembresias,
  PlanAbono,
  EstadisticasMembresias,
} from "@/lib/membresias-api";
import { ApiError } from "@/lib/api";
import { PlanDialog } from "./plan-dialog";
import { AsignarAClienteDialog } from "./asignar-a-cliente-dialog";
import { toast } from "sonner";
import {
  MoreVertical,
  Pencil,
  Trash2,
  Plus,
  Infinity as InfinityIcon,
  UserPlus,
  Users,
  Scissors,
  TrendingUp,
} from "lucide-react";

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
import { SoloDueno } from "@/components/si-rol";

const NUM_STYLE: React.CSSProperties = {
  fontFamily: "Syne, sans-serif",
  fontVariantNumeric: "lining-nums tabular-nums",
};

/** Formatea un número como precio en pesos. */
function pesos(n: number | null): string {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString("es-AR")}`;
}

export default function MembresiasPage() {
  const [planes, setPlanes] = useState<PlanAbono[]>([]);
  const [stats, setStats] = useState<EstadisticasMembresias | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [editando, setEditando] = useState<PlanAbono | null>(null);
  const [aBorrar, setABorrar] = useState<PlanAbono | null>(null);
  const [asignandoACliente, setAsignandoACliente] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [planesData, statsData] = await Promise.all([
        listarPlanes(),
        estadisticasMembresias(),
      ]);
      setPlanes(planesData);
      setStats(statsData);
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

  /** Busca las estadísticas de un plan puntual. */
  function statsDePlan(planId: number) {
    return stats?.planes.find((p) => p.plan_id === planId);
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
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setAsignandoACliente(true)}>
            <UserPlus size={16} className="mr-1" />
            Asignar a cliente
          </Button>
          <SoloDueno>
            <Button onClick={abrirCrear}>
              <Plus size={16} className="mr-1" />
              Nuevo plan
            </Button>
          </SoloDueno>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {cargando && !error && (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      )}

      {!cargando && !error && (
        <>
          {/* Resumen general de rentabilidad */}
          {stats && (
            <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div className="rounded-2xl border bg-card p-5">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Users size={16} />
                  <p className="text-xs uppercase tracking-wide">Abonados</p>
                </div>
                <p className="mt-1 text-2xl font-bold" style={NUM_STYLE}>
                  {stats.resumen.total_abonados}
                </p>
              </div>
              <div className="rounded-2xl border bg-card p-5">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <TrendingUp size={16} />
                  <p className="text-xs uppercase tracking-wide">Ingreso</p>
                </div>
                <p
                  className="mt-1 text-2xl font-bold"
                  style={{ ...NUM_STYLE, color: "#10b981" }}
                >
                  {pesos(stats.resumen.total_ingreso)}
                </p>
              </div>
              <div className="rounded-2xl border bg-card p-5">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Scissors size={16} />
                  <p className="text-xs uppercase tracking-wide">
                    Cortes por abono
                  </p>
                </div>
                <p className="mt-1 text-2xl font-bold" style={NUM_STYLE}>
                  {stats.resumen.total_cortes}
                </p>
              </div>
              <div className="rounded-2xl border bg-card p-5">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Precio efectivo / corte
                </p>
                <p className="mt-1 text-2xl font-bold" style={NUM_STYLE}>
                  {pesos(stats.resumen.precio_efectivo_promedio)}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  lo que te queda por corte
                </p>
              </div>
            </div>
          )}

          {/* Planes */}
          {planes.length === 0 ? (
            <div className="rounded-2xl border bg-card p-12 text-center">
              <p className="text-sm text-muted-foreground">
                Todavía no hay planes de abono. Creá el primero (ej.
                &quot;PRO&quot;).
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {planes.map((plan) => {
                const ps = statsDePlan(plan.id);
                return (
                  <div
                    key={plan.id}
                    className="relative rounded-2xl border bg-card p-5"
                  >
                    {/* Menú de acciones (catálogo del plan: solo el dueño) */}
                    <SoloDueno>
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
                    </SoloDueno>

                    {/* Nombre + precio */}
                    <h3
                      className="text-lg font-bold"
                      style={{ fontFamily: "Syne, sans-serif" }}
                    >
                      {plan.nombre}
                    </h3>
                    <p
                      className="mt-1 text-2xl font-bold text-primary"
                      style={NUM_STYLE}
                    >
                      ${plan.precio.toLocaleString("es-AR")}
                    </p>

                    {plan.descripcion && (
                      <p className="mt-2 text-sm text-muted-foreground">
                        {plan.descripcion}
                      </p>
                    )}

                    {/* Tipo */}
                    <div className="mt-3 flex items-center gap-1.5 text-sm">
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

                    {/* Estadísticas del plan */}
                    {ps && (
                      <div className="mt-4 space-y-2 border-t pt-4 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">
                            Abonados activos
                          </span>
                          <span className="font-medium tabular-nums">
                            {ps.abonados_activos}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">
                            Cortes realizados
                          </span>
                          <span className="font-medium tabular-nums">
                            {ps.cortes_realizados}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Ingreso</span>
                          <span
                            className="font-medium tabular-nums"
                            style={{ color: "#10b981" }}
                          >
                            {pesos(ps.ingreso)}
                          </span>
                        </div>
                        <div className="flex justify-between border-t pt-2">
                          <span className="text-muted-foreground">
                            Precio efectivo / corte
                          </span>
                          <span className="font-bold tabular-nums">
                            {pesos(ps.precio_efectivo_por_corte)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Diálogo crear/editar */}
      <PlanDialog
        plan={editando}
        abierto={dialogAbierto}
        onCerrar={() => setDialogAbierto(false)}
        onGuardado={cargar}
      />

      {/* Diálogo de asignar a cliente */}
      <AsignarAClienteDialog
        abierto={asignandoACliente}
        onCerrar={() => setAsignandoACliente(false)}
        onAsignada={cargar}
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