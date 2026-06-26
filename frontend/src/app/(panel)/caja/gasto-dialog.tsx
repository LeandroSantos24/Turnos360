"use client";

/**
 * Diálogo para registrar un gasto (E10 · N-56).
 * Permite elegir una categoría existente o crear una nueva al vuelo.
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  registrarGasto,
  listarCategorias,
  crearCategoria,
  listarMetodos,
  Categoria,
  MetodoPago,
} from "@/lib/finanzas-api";
import { ApiError } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface GastoDialogProps {
  abierto: boolean;
  onCerrar: () => void;
  onRegistrado: () => void;
}

export function GastoDialog({ abierto, onCerrar, onRegistrado }: GastoDialogProps) {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [metodos, setMetodos] = useState<MetodoPago[]>([]);
  const [concepto, setConcepto] = useState("");
  const [monto, setMonto] = useState("");
  const [categoriaId, setCategoriaId] = useState("");
  const [nuevaCategoria, setNuevaCategoria] = useState("");
  const [metodoId, setMetodoId] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    listarCategorias().then(setCategorias).catch(() => setCategorias([]));
    listarMetodos()
      .then((m) => setMetodos(m.filter((x) => x.activo)))
      .catch(() => setMetodos([]));
    setConcepto("");
    setMonto("");
    setCategoriaId("");
    setNuevaCategoria("");
    setMetodoId("");
  }, [abierto]);

  async function guardar() {
    if (!concepto.trim() || !(Number(monto) > 0)) {
      toast.error("Completá concepto y monto");
      return;
    }
    setGuardando(true);
    try {
      let catId: number | null = categoriaId ? Number(categoriaId) : null;
      if (nuevaCategoria.trim()) {
        const cat = await crearCategoria({ nombre: nuevaCategoria.trim(), tipo: "egreso" });
        catId = cat.id;
      }
      await registrarGasto({
        concepto: concepto.trim(),
        monto: Number(monto),
        categoria_id: catId,
        metodo_pago_id: metodoId ? Number(metodoId) : null,
      });
      toast.success("Gasto registrado");
      onRegistrado();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo registrar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Registrar gasto</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-2">
            <Label htmlFor="g-concepto">Concepto *</Label>
            <Input
              id="g-concepto"
              value={concepto}
              onChange={(e) => setConcepto(e.target.value)}
              placeholder="Compra de productos, alquiler…"
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="g-monto">Monto *</Label>
            <Input
              id="g-monto"
              type="number"
              inputMode="numeric"
              value={monto}
              onChange={(e) => setMonto(e.target.value)}
              placeholder="$"
            />
          </div>

          <div className="space-y-2">
            <Label>Categoría</Label>
            {categorias.length > 0 && (
              <Select value={categoriaId} onValueChange={setCategoriaId}>
                <SelectTrigger>
                  <SelectValue placeholder="Elegí una categoría (opcional)" />
                </SelectTrigger>
                <SelectContent>
                  {categorias.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Input
              value={nuevaCategoria}
              onChange={(e) => setNuevaCategoria(e.target.value)}
              placeholder={
                categorias.length > 0 ? "…o creá una nueva" : "Nueva categoría (ej. Insumos)"
              }
            />
          </div>

          {metodos.length > 0 && (
            <div className="space-y-2">
              <Label>¿Con qué lo pagaste?</Label>
              <Select value={metodoId} onValueChange={setMetodoId}>
                <SelectTrigger>
                  <SelectValue placeholder="Método (opcional)" />
                </SelectTrigger>
                <SelectContent>
                  {metodos.map((m) => (
                    <SelectItem key={m.id} value={String(m.id)}>
                      {m.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCerrar}>
            Cancelar
          </Button>
          <Button onClick={guardar} disabled={guardando}>
            {guardando ? "Guardando…" : "Registrar gasto"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}