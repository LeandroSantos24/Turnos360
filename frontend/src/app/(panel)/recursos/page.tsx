"use client";

/**
 * Pantalla de Recursos (/recursos). Buscador + orden + editar/borrar.
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { listarRecursos, borrarRecurso, Recurso } from "@/lib/recursos-api";
import { ApiError } from "@/lib/api";
import { NuevoRecursoDialog } from "./nuevo-recurso-dialog";
import { EditarRecursoDialog } from "./editar-recurso-dialog";
import { toast } from "sonner";
import { Clock, MoreVertical, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";

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
      .sort((a, b) => {
        const cmp = a.nombre.localeCompare(b.nombre, "es");
        return orden === "asc" ? cmp : -cmp;
      });
  }, [recursos, buscar, orden]);

  function alternarOrden() {
    setOrden((o) => (o === "asc" ? "desc" : "asc"));
  }

  async function confirmarBorrar() {
    if (!aBorrar) return;
    try {
      await borrarRecurso(aBorrar.id);
      toast.success(`"${aBorrar.nombre}" eliminado`);
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
        <NuevoRecursoDialog onCreado={cargar} />
      </div>

      <div className="mb-4 max-w-sm">
        <Input
          placeholder="Buscar recurso…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
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
        <div className="overflow-hidden rounded-2xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead
                  className="cursor-pointer select-none hover:text-foreground"
                  onClick={alternarOrden}
                >
                  Nombre {orden === "asc" ? "↑" : "↓"}
                </TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Especialidades</TableHead>
                <TableHead className="w-12"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibles.map((r) => (
                <TableRow key={r.id}>
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
                  <TableCell>{TIPO_LABEL[r.tipo] ?? r.tipo}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {r.especialidades.length > 0
                      ? r.especialidades.map((e) => e.nombre).join(", ")
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreVertical size={16} />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link href={`/recursos/${r.id}/horarios`}>
                            <Clock size={14} className="mr-2" />
                            Horarios
                          </Link>
                        </DropdownMenuItem>
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
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
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