"use client";

/**
 * Pantalla de Clientes (/clientes).
 * Lista con búsqueda y paginación servidor (de a 10). Estilo uniforme.
 */

import { useEffect, useState, useCallback } from "react";
import { listarClientes, Cliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { NuevoClienteDialog } from "./nuevo-cliente-dialog";
import { Paginacion } from "@/components/paginacion";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const POR_PAGINA = 10;

export default function ClientesPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(0);
  const [buscar, setBuscar] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Clientes</h1>
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums">{total}</span>{" "}
            {total === 1 ? "cliente" : "clientes"}
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
        <p className="text-sm text-muted-foreground">Cargando clientes…</p>
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
          <div className="overflow-hidden rounded-2xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Nombre</TableHead>
                  <TableHead>Teléfono</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Canal</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {clientes.map((c) => (
                  <TableRow key={c.id}>
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
    </div>
  );
}