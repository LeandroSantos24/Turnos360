"use client";

/**
 * Diálogo para crear un servicio nuevo, con configuración de carril de agenda.
 *
 * Dos campos simples para el dueño:
 * - "¿Se puede dar en paralelo a otros servicios?" (switch)
 *   · No → comparte carril: muestra el campo "Grupo de bloqueo"
 *   · Sí → convive con todo, se le da un grupo propio (no se duplica a sí mismo)
 *
 * Por detrás todo se traduce al campo grupo_agenda del backend.
 */

import { useState } from "react";
import { crearServicio } from "@/lib/servicios-api";
import { SelectorRecursos } from "./selector-recursos";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/** Convierte un texto a un identificador de grupo simple (sin espacios ni mayúsculas). */
function aSlug(texto: string): string {
  return texto
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // saca acentos
    .replace(/[^a-z0-9]+/g, "-") // espacios y símbolos → guion
    .replace(/^-+|-+$/g, "");
}

export function NuevoServicioDialog({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [duracion, setDuracion] = useState("30");
  const [paso, setPaso] = useState("15");
  const [precio, setPrecio] = useState("");
  const [agendable, setAgendable] = useState(true); // ¿ocupa turno?

  // Carril de agenda
  const [enParalelo, setEnParalelo] = useState(false); // ¿convive con todo?
  const [grupo, setGrupo] = useState(""); // nombre del carril (si NO es en paralelo)
  const [recursoIds, setRecursoIds] = useState<number[]>([]);

  function limpiar() {
    setNombre("");
    setDuracion("30");
    setPaso("15");
    setPrecio("");
    setAgendable(true);
    setEnParalelo(false);
    setGrupo("");
    setRecursoIds([]);
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();

    // Traducir la elección del dueño al grupo_agenda
    let grupoAgenda: string;
    if (enParalelo) {
      // Convive con todo, pero no se duplica: grupo propio derivado del nombre
      grupoAgenda = `solo-${aSlug(nombre) || "servicio"}`;
    } else {
      // Comparte carril: usa el grupo que escribió (o uno propio si lo dejó vacío)
      grupoAgenda = aSlug(grupo) || `solo-${aSlug(nombre) || "servicio"}`;
    }

    setGuardando(true);
    try {
      await crearServicio({
        nombre,
        duracion_min: agendable ? Number(duracion) : 1,
        paso_turno_min: agendable ? Number(paso) : 1,
        precio: precio ? Number(precio) : undefined,
        grupo_agenda: agendable ? grupoAgenda : null,
        agendable,
        recurso_ids: recursoIds,
      });
      toast.success("Servicio creado");
      limpiar();
      setAbierto(false);
      onCreado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al crear");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button>Nuevo servicio</Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nuevo servicio</DialogTitle>
          <DialogDescription>
            Definí qué ofrecés, cuánto dura y cómo ocupa la agenda.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="nombre">Nombre *</Label>
            <Input
              id="nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Corte, Color, Barba…"
              required
              autoFocus
            />
          </div>

          {/* ¿Ocupa un turno o es solo para vender? */}
          <div className="flex items-start justify-between gap-3 rounded-xl border bg-muted/30 p-4">
            <div className="space-y-0.5">
              <Label htmlFor="agendable">¿Ocupa un turno en la agenda?</Label>
              <p className="text-xs text-muted-foreground">
                Activado: se reserva como turno (corte, color). Desactivado: solo
                se vende como adicional (perfilado, productos) y no aparece al agendar.
              </p>
            </div>
            <Switch id="agendable" checked={agendable} onCheckedChange={setAgendable} />
          </div>

          {agendable && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="duracion">Duración (min) *</Label>
                <Input
                  id="duracion"
                  type="number"
                  min="1"
                  value={duracion}
                  onChange={(e) => setDuracion(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="paso">Turno cada (min)</Label>
                <Input
                  id="paso"
                  type="number"
                  min="1"
                  value={paso}
                  onChange={(e) => setPaso(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="precio">Precio</Label>
            <Input
              id="precio"
              type="number"
              min="0"
              value={precio}
              onChange={(e) => setPrecio(e.target.value)}
              placeholder="9000"
            />
          </div>

          {/* Carril de agenda (solo si ocupa turno) */}
          {agendable && (
            <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-0.5">
                <Label htmlFor="paralelo">
                  ¿Se puede dar en paralelo a otros servicios?
                </Label>
                <p className="text-xs text-muted-foreground">
                  Como la barba: se puede hacer aunque el barbero esté con otro
                  corte o color al mismo tiempo.
                </p>
              </div>
              <Switch
                id="paralelo"
                checked={enParalelo}
                onCheckedChange={setEnParalelo}
              />
            </div>

            {/* Solo si NO es en paralelo: con qué grupo se bloquea */}
            {!enParalelo && (
              <div className="space-y-2 border-t pt-3">
                <Label htmlFor="grupo">Grupo de bloqueo</Label>
                <Input
                  id="grupo"
                  value={grupo}
                  onChange={(e) => setGrupo(e.target.value)}
                  placeholder="corte, tintura…"
                />
                <p className="text-xs text-muted-foreground">
                  Servicios con el mismo grupo no pueden coincidir en horario.
                  Ej: &quot;Corte&quot; y &quot;Corte + barba&quot; comparten el
                  grupo <span className="font-medium">corte</span>.
                </p>
              </div>
              )}

              <SelectorRecursos seleccionados={recursoIds} onCambio={setRecursoIds} />
            </div>
          )}

          <DialogFooter>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Crear servicio"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}