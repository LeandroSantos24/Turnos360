"use client";

/**
 * Selector "Local" para el formulario de un profesional.
 *
 * No se muestra si el negocio tiene un solo local: en ese caso no hay nada
 * que elegir, el alta cae sola en el único que existe, y agregar un campo
 * con una única opción sería trabajo inventado para el dueño de una silla.
 *
 * Un profesional pertenece a UN local. Si la misma persona atiende en dos, se
 * carga dos veces — es lo que hace el mercado y evita que el motor de
 * disponibilidad tenga que adivinar a qué local corresponde cada hueco.
 */

import { useSucursales } from "@/lib/use-sucursales";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function SelectorSucursal({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (sucursalId: number | null) => void;
}) {
  const { abiertas, multi } = useSucursales();

  if (!multi) return null;

  return (
    <div className="space-y-2">
      <Label>Local *</Label>
      <Select
        value={value != null ? String(value) : ""}
        onValueChange={(v) => onChange(v ? Number(v) : null)}
      >
        <SelectTrigger>
          <SelectValue placeholder="Elegí en qué local atiende" />
        </SelectTrigger>
        <SelectContent>
          {abiertas.map((s) => (
            <SelectItem key={s.id} value={String(s.id)}>
              {s.nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">
        Si atiende en dos locales, cargalo una vez en cada uno.
      </p>
    </div>
  );
}
