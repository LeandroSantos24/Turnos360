"use client";

/**
 * Selector de cliente "buscar o crear".
 *
 * Escribís un nombre → busca clientes que coincidan (contra la API).
 * - Si existe, lo seleccionás de la lista.
 * - Si no existe, ofrece crearlo al vuelo con ese nombre.
 *
 * Avisa al padre con onSeleccion(cliente) cuál quedó elegido.
 */

import { useState, useEffect, useCallback } from "react";
import { Check, ChevronsUpDown, UserPlus } from "lucide-react";
import {
  listarClientes,
  crearCliente,
  Cliente,
} from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface SelectorClienteProps {
  clienteElegido: Cliente | null;
  onSeleccion: (cliente: Cliente | null) => void;
}

export function SelectorCliente({
  clienteElegido,
  onSeleccion,
}: SelectorClienteProps) {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<Cliente[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [creando, setCreando] = useState(false);

  // Buscar clientes con debounce cuando cambia el texto
  const buscar = useCallback(async (q: string) => {
    if (q.trim().length === 0) {
      setResultados([]);
      return;
    }
    setBuscando(true);
    try {
      const data = await listarClientes(q, 0, 8);
      setResultados(data.items);
    } catch {
      setResultados([]);
    } finally {
      setBuscando(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => buscar(texto), 250);
    return () => clearTimeout(t);
  }, [texto, buscar]);

  // ¿Hay un cliente exacto con ese nombre? (para decidir si ofrecer crear)
  const nombreExacto = resultados.some(
    (c) =>
      `${c.nombre} ${c.apellido ?? ""}`.trim().toLowerCase() ===
      texto.trim().toLowerCase(),
  );

  async function crearAlVuelo() {
    const limpio = texto.trim();
    if (!limpio) return;
    // Partimos el texto en nombre y apellido (lo que sobra va al apellido)
    const partes = limpio.split(" ");
    const nombre = partes[0];
    const apellido = partes.slice(1).join(" ") || undefined;

    setCreando(true);
    try {
      const nuevo = await crearCliente({ nombre, apellido });
      toast.success(`Cliente "${limpio}" creado`);
      onSeleccion(nuevo);
      setAbierto(false);
      setTexto("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo crear");
    } finally {
      setCreando(false);
    }
  }

  function elegir(cliente: Cliente) {
    onSeleccion(cliente);
    setAbierto(false);
    setTexto("");
  }

  const etiqueta = clienteElegido
    ? `${clienteElegido.nombre} ${clienteElegido.apellido ?? ""}`.trim()
    : "Elegí o creá un cliente";

  return (
    <Popover open={abierto} onOpenChange={setAbierto}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={abierto}
          className="w-full justify-between font-normal"
        >
          <span className={clienteElegido ? "" : "text-muted-foreground"}>
            {etiqueta}
          </span>
          <ChevronsUpDown size={16} className="ml-2 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Escribí un nombre…"
            value={texto}
            onValueChange={setTexto}
          />
          <CommandList>
            {/* Resultados de la búsqueda */}
            {resultados.length > 0 && (
              <CommandGroup heading="Clientes">
                {resultados.map((c) => {
                  const nom = `${c.nombre} ${c.apellido ?? ""}`.trim();
                  const elegido = clienteElegido?.id === c.id;
                  return (
                    <CommandItem
                      key={c.id}
                      value={String(c.id)}
                      onSelect={() => elegir(c)}
                    >
                      <Check
                        size={16}
                        className={`mr-2 ${elegido ? "opacity-100" : "opacity-0"}`}
                      />
                      <span className="flex-1">{nom}</span>
                      {c.telefono && (
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {c.telefono}
                        </span>
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            )}

            {/* Estado: buscando */}
            {buscando && (
              <div className="px-3 py-2 text-sm text-muted-foreground">
                Buscando…
              </div>
            )}

            {/* Vacío: sin texto */}
            {!buscando && texto.trim().length === 0 && (
              <CommandEmpty>Escribí para buscar un cliente.</CommandEmpty>
            )}

            {/* Ofrecer crear si hay texto y no existe uno exacto */}
            {!buscando && texto.trim().length > 0 && !nombreExacto && (
              <CommandGroup>
                <CommandItem
                  value={`crear-${texto}`}
                  onSelect={crearAlVuelo}
                  disabled={creando}
                  className="text-primary"
                >
                  <UserPlus size={16} className="mr-2" />
                  {creando ? "Creando…" : `Crear "${texto.trim()}"`}
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}