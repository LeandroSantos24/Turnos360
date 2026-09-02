"use client";

/**
 * En qué locales se ofrece este servicio, y a qué precio en cada uno.
 *
 * No se muestra si el negocio tiene un solo local: todo servicio nace ofrecido
 * en todos, y con uno solo no hay nada que elegir ni ningún precio que
 * diferenciar.
 *
 * El precio por local va vacío por defecto, y vacío significa "el del
 * servicio". Es a propósito: si al tildar un local se copiara el precio
 * general, subir el precio después obligaría a tocar cada local uno por uno, y
 * el que se olvidara quedaría vendiendo al precio viejo sin que nadie se
 * entere.
 */

import { Check } from "lucide-react";

import { SucursalDeServicio } from "@/lib/servicios-api";
import { useSucursales } from "@/lib/use-sucursales";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function SelectorSucursalesServicio({
  seleccionadas,
  onCambio,
  precioBase,
}: {
  seleccionadas: SucursalDeServicio[];
  onCambio: (s: SucursalDeServicio[]) => void;
  /** El precio general del servicio, para mostrarlo como referencia. */
  precioBase: number | null;
}) {
  const { abiertas, multi } = useSucursales();

  if (!multi) return null;

  function toggle(sucursalId: number) {
    const esta = seleccionadas.some((s) => s.sucursal_id === sucursalId);
    onCambio(
      esta
        ? seleccionadas.filter((s) => s.sucursal_id !== sucursalId)
        : [...seleccionadas, { sucursal_id: sucursalId, precio: null }],
    );
  }

  function cambiarPrecio(sucursalId: number, texto: string) {
    const valor = texto.trim() === "" ? null : Number(texto);
    onCambio(
      seleccionadas.map((s) =>
        s.sucursal_id === sucursalId ? { ...s, precio: valor } : s,
      ),
    );
  }

  return (
    <div className="space-y-2">
      <Label>Locales donde se ofrece *</Label>
      <div className="space-y-1.5">
        {abiertas.map((suc) => {
          const elegida = seleccionadas.find((s) => s.sucursal_id === suc.id);
          return (
            <div
              key={suc.id}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2 transition-colors ${
                elegida ? "border-primary/40 bg-primary/5" : ""
              }`}
            >
              <button
                type="button"
                onClick={() => toggle(suc.id)}
                className="flex min-w-0 flex-1 items-center gap-2.5 text-left text-sm"
              >
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                    elegida
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/40"
                  }`}
                >
                  {elegida && <Check size={11} strokeWidth={3} />}
                </span>
                <span className="truncate">{suc.nombre}</span>
              </button>

              {elegida && (
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  value={elegida.precio ?? ""}
                  onChange={(e) => cambiarPrecio(suc.id, e.target.value)}
                  placeholder={
                    precioBase != null ? `$${precioBase}` : "Precio general"
                  }
                  className="h-8 w-32 text-sm"
                  aria-label={`Precio en ${suc.nombre}`}
                />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Dejá el precio vacío para usar el general. Si lo completás, ese local
        cobra ese importe.
      </p>
      {seleccionadas.length === 0 && (
        <p className="text-xs text-destructive">
          Elegí al menos uno: un servicio que no se ofrece en ningún local no le
          aparece a nadie.
        </p>
      )}
    </div>
  );
}
