"use client";

/**
 * Pantalla de Clientes (/clientes).
 *
 * Lista los clientes de la empresa con búsqueda. Maneja los 4 estados:
 * cargando, error, vacío y con datos. Crear/editar se suman después.
 */

import { useEffect, useState, useCallback } from "react";
import { listarClientes, Cliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function ClientesPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [total, setTotal] = useState(0);
  const [buscar, setBuscar] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Función para cargar clientes. useCallback evita recrearla en cada render.
  const cargar = useCallback(async (texto: string) => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarClientes(texto || undefined);
      setClientes(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  // Cargar al montar la pantalla.
  useEffect(() => {
    cargar("");
  }, [cargar]);

  // Buscar con un pequeño retraso (debounce): espera 300ms tras dejar de tipear,
  // así no dispara una búsqueda por cada tecla.
  useEffect(() => {
    const t = setTimeout(() => cargar(buscar), 300);
    return () => clearTimeout(t);
  }, [buscar, cargar]);

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Clientes</h1>
          <p className="text-sm text-muted-foreground">
            {total} {total === 1 ? "cliente" : "clientes"}
          </p>
        </div>
      </div>

      <div className="mb-4 max-w-sm">
        <Input
          placeholder="Buscar por nombre, teléfono, DNI…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {/* Estado: error */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Estado: cargando */}
      {cargando && !error && (
        <p className="text-sm text-muted-foreground">Cargando clientes…</p>
      )}

      {/* Estado: vacío */}
      {!cargando && !error && clientes.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {buscar
            ? "No se encontraron clientes con ese criterio."
            : "Todavía no hay clientes cargados."}
        </p>
      )}

      {/* Estado: con datos */}
      {!cargando && !error && clientes.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
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
                  <TableCell>{c.telefono ?? "—"}</TableCell>
                  <TableCell>{c.email ?? "—"}</TableCell>
                  <TableCell>{c.canal_adquisicion ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}