"use client";

/**
 * Pantalla de Clientes (/clientes). Búsqueda + paginación + editar/borrar.
 */

import { useEffect, useState, useCallback } from "react";
import { listarClientes, borrarCliente, Cliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { NuevoClienteDialog } from "./nuevo-cliente-dialog";
import { useTermino } from "@/lib/config-rubro";
import { EditarClienteDialog } from "./editar-cliente-dialog";
import { Paginacion } from "@/components/paginacion";
import { toast } from "sonner";
import { MoreVertical, Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";

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

const POR_PAGINA = 10;

export default function ClientesPage() {
  // Terminología del rubro: "cliente" o "paciente" según el preset.
  const termino = useTermino()("cliente", "cliente");
  const Termino = termino.charAt(0).toUpperCase() + termino.slice(1);

  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(0);
  const [buscar, setBuscar] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editando, setEditando] = useState<Cliente | null>(null);
  const [aBorrar, setABorrar] = useState<Cliente | null>(null);
  const router = useRouter();

  const cargar = useCallback(async (texto: string, pag: number) => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarClientes(
        texto || undefined,
        pag * POR_PAGINA,
        POR_PAGINA,
      );
      setClientes(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar(buscar, pagina);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagina]);

  useEffect(() => {
    const t = setTimeout(() => {
      setPagina(0);
      cargar(buscar, 0);
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscar]);

  async function confirmarBorrar() {
    if (!aBorrar) return;
    try {
      await borrarCliente(aBorrar.id);
      toast.success("Cliente eliminado");
      setABorrar(null);
      cargar(buscar, pagina);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo borrar");
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{Termino}s</h1>
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums">{total}</span>{" "}
            {total === 1 ? termino : `${termino}s`}
          </p>
        </div>
        <NuevoClienteDialog onCreado={() => cargar(buscar, pagina)} />
      </div>

      <div className="mb-4 max-w-sm">
        <Input
          placeholder="Buscar por nombre, teléfono, DNI…"
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
        <p className="text-sm text-muted-foreground">{`Cargando ${termino}s…`}</p>
      )}

      {!cargando && !error && clientes.length === 0 && (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            {buscar
              ? "No se encontraron clientes con ese criterio."
              : "Todavía no hay clientes cargados."}
          </p>
        </div>
      )}

      {!cargando && !error && clientes.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Nombre</TableHead>
                  <TableHead>Teléfono</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Canal</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {clientes.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/clientes/${c.id}`)}
                  >
                    <TableCell className="font-medium">
                      {c.nombre} {c.apellido ?? ""}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {c.telefono ?? "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {c.email ?? "—"}
                    </TableCell>
                    <TableCell>{c.canal_adquisicion ?? "—"}</TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical size={16} />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setEditando(c)}>
                            <Pencil size={14} className="mr-2" />
                            Editar
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setABorrar(c)}
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

          <Paginacion
            pagina={pagina}
            total={total}
            porPagina={POR_PAGINA}
            onCambiar={setPagina}
          />
        </>
      )}

      <EditarClienteDialog
        cliente={editando}
        abierto={editando !== null}
        onCerrar={() => setEditando(null)}
        onEditado={() => cargar(buscar, pagina)}
      />

      <AlertDialog open={aBorrar !== null} onOpenChange={(o) => !o && setABorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Borrar este cliente?</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a eliminar a &quot;{aBorrar?.nombre} {aBorrar?.apellido ?? ""}
              &quot;. Esta acción no se puede deshacer.
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