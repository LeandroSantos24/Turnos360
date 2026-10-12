"use client";

/**
 * Diálogo para las acciones que mueven una suscripción sin plata (prórroga,
 * renovación sin pago, cambio de vencimiento o de plan, reversión).
 *
 * Pide el motivo (obligatorio, también lo exige el backend) y, cuando
 * corresponde, el tipo de ajuste. Así queda separado lo que es un regalo
 * comercial de lo que es corregir un error.
 *
 *     const { pedir, dialogo } = usePedirMotivo();
 *     const r = await pedir({ titulo: "...", categorias: ["cortesia", "incidencia"] });
 *     if (!r) return;           // canceló
 *     await darProrroga(id, dias, r.motivo, r.categoria);
 *     ...
 *     return <>{dialogo}...</>;
 */

import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export type CategoriaAjuste = "cortesia" | "incidencia" | "correccion";

export const CATEGORIAS_AJUSTE: Record<CategoriaAjuste, { titulo: string; ayuda: string }> = {
  cortesia: { titulo: "Días de cortesía", ayuda: "Un beneficio comercial: promo, cliente nuevo, fidelización." },
  incidencia: { titulo: "Extensión por incidencia", ayuda: "Compensa un problema: el sistema no anduvo, un error nuestro." },
  correccion: { titulo: "Corrección administrativa", ayuda: "Arregla un dato mal cargado. No es un beneficio." },
};

type Pedido = {
  titulo: string;
  descripcion?: string;
  categorias?: CategoriaAjuste[];
  textoAccion?: string;
  destructivo?: boolean;
};
type Respuesta = { motivo: string; categoria: CategoriaAjuste | null };

export function usePedirMotivo() {
  const [pedido, setPedido] = useState<Pedido | null>(null);
  const [motivo, setMotivo] = useState("");
  const [categoria, setCategoria] = useState<CategoriaAjuste | null>(null);
  const resolver = useRef<((r: Respuesta | null) => void) | null>(null);

  const pedir = useCallback((p: Pedido) => {
    setMotivo("");
    setCategoria(p.categorias?.length === 1 ? p.categorias[0] : null);
    setPedido(p);
    return new Promise<Respuesta | null>((r) => {
      resolver.current = r;
    });
  }, []);

  function cerrar(r: Respuesta | null) {
    resolver.current?.(r);
    resolver.current = null;
    setPedido(null);
  }

  const faltaCategoria = !!pedido?.categorias?.length && categoria === null;
  const motivoOk = motivo.trim().length >= 4;

  const dialogo = (
    <Dialog open={pedido !== null} onOpenChange={(o) => !o && cerrar(null)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{pedido?.titulo}</DialogTitle>
          {pedido?.descripcion && <DialogDescription>{pedido.descripcion}</DialogDescription>}
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (motivoOk && !faltaCategoria) cerrar({ motivo: motivo.trim(), categoria });
          }}
        >
          {!!pedido?.categorias?.length && (
            <fieldset className="space-y-2">
              <legend className="mb-1 text-sm font-medium">Tipo de ajuste</legend>
              {pedido.categorias.map((c) => (
                <label key={c} className={`flex cursor-pointer gap-3 rounded-xl border p-3 text-sm ${categoria === c ? "border-primary bg-primary/5" : ""}`}>
                  <input type="radio" name="categoria-ajuste" className="mt-0.5" checked={categoria === c} onChange={() => setCategoria(c)} />
                  <span>
                    <span className="font-medium">{CATEGORIAS_AJUSTE[c].titulo}</span>
                    <span className="block text-xs text-muted-foreground">{CATEGORIAS_AJUSTE[c].ayuda}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          <label className="block text-sm font-medium">
            Motivo
            <textarea
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              maxLength={300}
              rows={3}
              required
              aria-describedby="motivo-ayuda"
              className="mt-1 block w-full rounded-lg border bg-background px-3 py-2 text-sm font-normal"
              placeholder="Ej.: compensación por el corte del lunes"
            />
            <span id="motivo-ayuda" className="mt-1 block text-xs font-normal text-muted-foreground">
              Queda en el historial y en la auditoría. Al menos 4 letras.
            </span>
          </label>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => cerrar(null)}>Volver</Button>
            <Button type="submit" variant={pedido?.destructivo ? "destructive" : "default"} disabled={!motivoOk || faltaCategoria}>
              {pedido?.textoAccion ?? "Confirmar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  return { pedir, dialogo };
}
