"use client";

/**
 * Pantalla de Recursos (/recursos).
 *
 * Arriba la lista (buscador + orden + editar/borrar); abajo, el horario de
 * atención del recurso que esté seleccionado. Antes había que salir a otra
 * pantalla por un menú de tres puntos para tocar los horarios, volver, y
 * repetir para el siguiente: cargar la semana de tres barberos eran nueve
 * navegaciones. Acá se elige uno, se carga la semana, se elige el otro.
 *
 * La página suelta /recursos/[id]/horarios sigue existiendo para los links
 * directos, y usa el mismo componente <HorarioSemanal>.
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { listarRecursos, borrarRecurso, Recurso } from "@/lib/recursos-api";
import { ApiError } from "@/lib/api";
import { NuevoRecursoDialog } from "./nuevo-recurso-dialog";
import { EditarRecursoDialog } from "./editar-recurso-dialog";
import { SoloDueno } from "@/components/si-rol";
import { HorarioSemanal } from "./horario-semanal";
import { toast } from "sonner";
import { Building2, CalendarClock, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { useSucursales } from "@/lib/use-sucursales";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

function BotonFiltro({
  activo,
  onClick,
  children,
}: {
  activo: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
        activo
          ? "border-transparent bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

const TIPO_LABEL: Record<string, string> = {
  persona: "Persona",
  box: "Box",
  equipo: "Equipo",
};

export default function RecursosPage() {
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [buscar, setBuscar] = useState("");
  const [orden, setOrden] = useState<"asc" | "desc">("asc");
  // "todos" mientras el negocio tenga un solo local: el filtro ni se dibuja.
  const [filtroSucursal, setFiltroSucursal] = useState<string>("todas");
  const { abiertas, multi, nombreDe } = useSucursales();

  // Recurso cuyo horario se muestra abajo. Se guarda el id y no el objeto
  // entero para que al recargar la lista (crear, editar, borrar) el panel
  // siga apuntando al mismo recurso, ya actualizado.
  const [seleccionadoId, setSeleccionadoId] = useState<number | null>(null);

  const [editando, setEditando] = useState<Recurso | null>(null);
  const [aBorrar, setABorrar] = useState<Recurso | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarRecursos();
      setRecursos(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const visibles = useMemo(() => {
    const texto = buscar.trim().toLowerCase();
    return recursos
      .filter((r) => r.nombre.toLowerCase().includes(texto))
      .filter(
        (r) =>
          filtroSucursal === "todas" || String(r.sucursal_id) === filtroSucursal,
      )
      .sort((a, b) => {
        const cmp = a.nombre.localeCompare(b.nombre, "es");
        return orden === "asc" ? cmp : -cmp;
      });
  }, [recursos, buscar, orden, filtroSucursal]);

  const seleccionado = useMemo(
    () => recursos.find((r) => r.id === seleccionadoId) ?? null,
    [recursos, seleccionadoId],
  );

  // La columna "Tipo" solo aparece si queda algún box o equipo de los de
  // antes. Con todos los recursos en "persona" era una columna que repetía
  // la misma palabra en cada fila.
  const hayTiposViejos = useMemo(
    () => recursos.some((r) => r.tipo !== "persona"),
    [recursos],
  );

  function alternarOrden() {
    setOrden((o) => (o === "asc" ? "desc" : "asc"));
  }

  async function confirmarBorrar() {
    if (!aBorrar) return;
    try {
      await borrarRecurso(aBorrar.id);
      toast.success(`"${aBorrar.nombre}" eliminado`);
      if (seleccionadoId === aBorrar.id) setSeleccionadoId(null);
      setABorrar(null);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo borrar");
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Recursos</h1>
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums">{visibles.length}</span> de{" "}
            <span className="tabular-nums">{recursos.length}</span>{" "}
            {recursos.length === 1 ? "recurso" : "recursos"}
          </p>
        </div>
        <SoloDueno>
          <NuevoRecursoDialog onCreado={cargar} />
        </SoloDueno>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input
          placeholder="Buscar recurso…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="max-w-sm"
        />
        {/* El filtro por local solo existe si hay más de uno. */}
        {multi && (
          <div className="flex flex-wrap gap-1.5">
            <BotonFiltro
              activo={filtroSucursal === "todas"}
              onClick={() => setFiltroSucursal("todas")}
            >
              Todos los locales
            </BotonFiltro>
            {abiertas.map((s) => (
              <BotonFiltro
                key={s.id}
                activo={filtroSucursal === String(s.id)}
                onClick={() => setFiltroSucursal(String(s.id))}
              >
                {s.nombre}
              </BotonFiltro>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {cargando && !error && (
        <p className="text-sm text-muted-foreground">Cargando recursos…</p>
      )}

      {!cargando && !error && visibles.length === 0 && (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            {buscar
              ? "No se encontraron recursos con ese nombre."
              : "Todavía no hay recursos. Creá el primero."}
          </p>
        </div>
      )}

      {!cargando && !error && visibles.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead
                  className="cursor-pointer select-none hover:text-foreground"
                  onClick={alternarOrden}
                >
                  Nombre {orden === "asc" ? "↑" : "↓"}
                </TableHead>
                {hayTiposViejos && <TableHead>Tipo</TableHead>}
                {multi && <TableHead>Local</TableHead>}
                <TableHead>Especialidades</TableHead>
                <TableHead className="w-12"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibles.map((r) => (
                <TableRow
                  key={r.id}
                  onClick={() => setSeleccionadoId(r.id)}
                  className={`cursor-pointer ${
                    r.id === seleccionadoId ? "bg-muted/60 hover:bg-muted/60" : ""
                  }`}
                >
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-2">
                      {r.color && (
                        <span
                          className="inline-block h-3 w-3 rounded-full"
                          style={{ backgroundColor: r.color }}
                        />
                      )}
                      {r.nombre}
                    </span>
                  </TableCell>
                  {hayTiposViejos && (
                    <TableCell>{TIPO_LABEL[r.tipo] ?? r.tipo}</TableCell>
                  )}
                  {multi && (
                    <TableCell className="text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <Building2 size={13} className="shrink-0 opacity-60" />
                        {nombreDe(r.sucursal_id) ?? "—"}
                      </span>
                    </TableCell>
                  )}
                  <TableCell className="text-muted-foreground">
                    {r.especialidades.length > 0
                      ? r.especialidades.map((e) => e.nombre).join(", ")
                      : "—"}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <SoloDueno>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical size={16} />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setEditando(r)}>
                            <Pencil size={14} className="mr-2" />
                            Editar
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setABorrar(r)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 size={14} className="mr-2" />
                            Borrar
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </SoloDueno>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* ── Horario del recurso elegido ─────────────────────────────── */}
      {!cargando && !error && visibles.length > 0 && (
        <SoloDueno>
          <div className="mt-8">
            {seleccionado ? (
              <>
                <div className="mb-4 flex items-baseline gap-2">
                  <h2 className="text-lg font-semibold">
                    Horario de {seleccionado.nombre}
                  </h2>
                  <button
                    type="button"
                    onClick={() => setSeleccionadoId(null)}
                    className="text-sm text-muted-foreground underline-offset-4 hover:underline"
                  >
                    cerrar
                  </button>
                </div>
                <p className="mb-4 text-sm text-muted-foreground">
                  Agregá una o varias franjas por día (por ejemplo 9–13 y 16–20
                  si cierra al mediodía). Un día sin franjas queda cerrado.
                </p>
                <HorarioSemanal recursoId={seleccionado.id} />
              </>
            ) : (
              <div className="flex items-center justify-center gap-2 rounded-2xl border border-dashed p-8 text-sm text-muted-foreground">
                <CalendarClock size={16} />
                Elegí un recurso de la lista para ver y editar su horario.
              </div>
            )}
          </div>
        </SoloDueno>
      )}

      <EditarRecursoDialog
        recurso={editando}
        abierto={editando !== null}
        onCerrar={() => setEditando(null)}
        onEditado={cargar}
      />

      <AlertDialog open={aBorrar !== null} onOpenChange={(o) => !o && setABorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Borrar este recurso?</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a eliminar &quot;{aBorrar?.nombre}&quot;. Esta acción no se
              puede deshacer.
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
