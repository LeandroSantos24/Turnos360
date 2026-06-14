"use client";

/**
 * Pantalla de Servicios (/servicios).
 * Lista lo que ofrece el negocio, con buscador y orden alfabético por clic.
 *
 * Como los servicios son pocos por negocio, el filtrado y el orden se hacen
 * en el navegador (instantáneo, sin volver a llamar a la API).
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import { ApiError } from "@/lib/api";
import { NuevoServicioDialog } from "./nuevo-servicio-dialog";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function ServiciosPage() {
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Estado del buscador y del orden (asc = A→Z, desc = Z→A)
  const [buscar, setBuscar] = useState("");
  const [orden, setOrden] = useState<"asc" | "desc">("asc");

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarServicios();
      setServicios(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Lista filtrada + ordenada. useMemo la recalcula solo cuando cambia
  // algo de lo que depende (los servicios, el texto o el orden), no en cada render.
  const visibles = useMemo(() => {
    const texto = buscar.trim().toLowerCase();
    return servicios
      .filter((s) => s.nombre.toLowerCase().includes(texto))
      .sort((a, b) => {
        const cmp = a.nombre.localeCompare(b.nombre, "es");
        return orden === "asc" ? cmp : -cmp;
      });
  }, [servicios, buscar, orden]);

  // Alterna el orden al hacer clic en el encabezado "Servicio"
  function alternarOrden() {
    setOrden((o) => (o === "asc" ? "desc" : "asc"));
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Servicios</h1>
          <p className="text-sm text-muted-foreground">
            {visibles.length} de {servicios.length}{" "}
            {servicios.length === 1 ? "servicio" : "servicios"}
          </p>
        </div>
        <NuevoServicioDialog onCreado={cargar} />
      </div>

      <div className="mb-4 max-w-sm">
        <Input
          placeholder="Buscar servicio…"
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
        />
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {cargando && !error && (
        <p className="text-sm text-muted-foreground">Cargando servicios…</p>
      )}

      {!cargando && !error && visibles.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {buscar
            ? "No se encontraron servicios con ese nombre."
            : "Todavía no hay servicios. Creá el primero."}
        </p>
      )}

      {!cargando && !error && visibles.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  className="cursor-pointer select-none hover:text-foreground"
                  onClick={alternarOrden}
                >
                  Servicio {orden === "asc" ? "↑" : "↓"}
                </TableHead>
                <TableHead>Duración</TableHead>
                <TableHead>Turno cada</TableHead>
                <TableHead className="text-right">Precio</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibles.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.nombre}</TableCell>
                  <TableCell>{s.duracion_min} min</TableCell>
                  <TableCell>{s.paso_turno_min} min</TableCell>
                  <TableCell className="text-right">
                    {s.precio != null
                      ? `$${Number(s.precio).toLocaleString("es-AR")}`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}