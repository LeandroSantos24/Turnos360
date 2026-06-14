"use client";

/**
 * Componente de paginación reutilizable.
 *
 * No sabe nada de clientes ni de ninguna entidad: recibe la página actual,
 * el total de ítems y cuántos por página, y avisa cuando el usuario quiere
 * cambiar de página. Sirve para cualquier tabla.
 */

import { Button } from "@/components/ui/button";

interface PaginacionProps {
  /** Página actual (empieza en 0, como el offset del backend). */
  pagina: number;
  /** Total de ítems (lo devuelve el backend). */
  total: number;
  /** Cuántos ítems por página. */
  porPagina: number;
  /** Se llama cuando el usuario elige otra página. */
  onCambiar: (nuevaPagina: number) => void;
}

export function Paginacion({
  pagina,
  total,
  porPagina,
  onCambiar,
}: PaginacionProps) {
  const totalPaginas = Math.ceil(total / porPagina);

  // Si entra todo en una página, no mostramos los controles.
  if (totalPaginas <= 1) return null;

  // Rango que se está mostrando: "11–20 de 47"
  const desde = pagina * porPagina + 1;
  const hasta = Math.min((pagina + 1) * porPagina, total);

  return (
    <div className="mt-4 flex items-center justify-between">
      <p className="text-sm text-muted-foreground">
        {desde}–{hasta} de {total}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onCambiar(pagina - 1)}
          disabled={pagina === 0}
        >
          Anterior
        </Button>
        <span className="text-sm text-muted-foreground">
          Página {pagina + 1} de {totalPaginas}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onCambiar(pagina + 1)}
          disabled={pagina >= totalPaginas - 1}
        >
          Siguiente
        </Button>
      </div>
    </div>
  );
}