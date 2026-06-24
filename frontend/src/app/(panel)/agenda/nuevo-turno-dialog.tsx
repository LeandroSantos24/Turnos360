"use client";

/**
 * Diálogo para crear un turno desde la agenda.
 *
 * Cliente (buscar/crear) + servicio + barbero + fecha/hora.
 * Sobreturno inteligente: si el backend rechaza por choque (409), aparece
 * el switch "Forzar como sobreturno" para crearlo igual.
 *
 * Puede abrirse desde el botón "Nuevo turno" (vacío) o desde un hueco de la
 * grilla (con carril y hora precargados).
 */

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import { AlertTriangle } from "lucide-react";

import { Cliente } from "@/lib/clientes-api";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { crearTurno } from "@/lib/turnos-api";
import { ApiError } from "@/lib/api";
import { SelectorCliente } from "./selector-cliente";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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

interface NuevoTurnoDialogProps {
  abierto: boolean;
  onCerrar: () => void;
  onCreado: () => void;
  recursoInicial?: number | null;
  fechaInicial?: Date | null;
  // Carril precargado (cuando se abre desde un hueco de la grilla)
  carrilInicial?: string | null;
}

export function NuevoTurnoDialog({
  abierto,
  onCerrar,
  onCreado,
  recursoInicial = null,
  fechaInicial = null,
  carrilInicial = null,
}: NuevoTurnoDialogProps) {
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [recursos, setRecursos] = useState<Recurso[]>([]);

  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [servicioId, setServicioId] = useState<string>("");
  const [recursoId, setRecursoId] = useState<string>("");
  const [fecha, setFecha] = useState<string>("");
  const [hora, setHora] = useState<string>("");
  const [guardando, setGuardando] = useState(false);

  // Sobreturno: arranca oculto, aparece si hay choque
  const [hayChoque, setHayChoque] = useState(false);
  const [forzar, setForzar] = useState(false);

  // Cargar servicios y recursos al abrir
  useEffect(() => {
    if (!abierto) return;
    listarServicios().then((d) => setServicios(d.items)).catch(() => {});
    listarRecursos()
      .then((d) => setRecursos(d.items.filter((r) => r.tipo === "persona")))
      .catch(() => {});
  }, [abierto]);

  // Prefill al abrir desde un hueco
  useEffect(() => {
    if (!abierto) return;
    if (recursoInicial != null) setRecursoId(String(recursoInicial));
    if (fechaInicial) {
      setFecha(format(fechaInicial, "yyyy-MM-dd"));
      setHora(
        `${String(fechaInicial.getUTCHours()).padStart(2, "0")}:${String(
          fechaInicial.getUTCMinutes(),
        ).padStart(2, "0")}`,
      );
    }
  }, [abierto, recursoInicial, fechaInicial]);

  // Preseleccionar un servicio del carril clickeado
  useEffect(() => {
    if (!abierto || !carrilInicial || servicios.length === 0) return;
    const delCarril = servicios.find((s) => {
      const g = s.grupo_agenda ?? "";
      return g === carrilInicial || g === `solo-${carrilInicial}`;
    });
    if (delCarril) setServicioId(String(delCarril.id));
  }, [abierto, carrilInicial, servicios]);

  function limpiar() {
    setCliente(null);
    setServicioId("");
    setRecursoId("");
    setFecha("");
    setHora("");
    setHayChoque(false);
    setForzar(false);
  }

  function cerrar() {
    limpiar();
    onCerrar();
  }

  // Si cambian datos clave, reseteamos el estado de choque
  function resetChoque() {
    if (hayChoque) {
      setHayChoque(false);
      setForzar(false);
    }
  }

  async function guardar() {
    if (!cliente) return toast.error("Elegí un cliente");
    if (!servicioId) return toast.error("Elegí un servicio");
    if (!recursoId) return toast.error("Elegí un profesional");
    if (!fecha || !hora) return toast.error("Elegí fecha y hora");

    const fechaInicio = `${fecha}T${hora}:00Z`;

    setGuardando(true);
    try {
      await crearTurno({
        cliente_id: cliente.id,
        servicio_id: Number(servicioId),
        recurso_id: Number(recursoId),
        fecha_inicio: fechaInicio,
        es_sobreturno: forzar, // true solo si activó el switch
      });
      toast.success(forzar ? "Sobreturno creado" : "Turno creado");
      limpiar();
      onCreado();
      onCerrar();
    } catch (err) {
      // 409 = choque de horario → ofrecer sobreturno
      if (err instanceof ApiError && err.status === 409) {
        setHayChoque(true);
        toast.error("Ese horario está ocupado. Podés forzarlo como sobreturno.");
      } else {
        toast.error(err instanceof ApiError ? err.message : "No se pudo crear");
      }
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && cerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo turno</DialogTitle>
          <DialogDescription>
            Elegí el cliente, el servicio, el profesional y el horario.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Cliente */}
          <div className="space-y-2">
            <Label>Cliente *</Label>
            <SelectorCliente clienteElegido={cliente} onSeleccion={setCliente} />
          </div>

          {/* Servicio */}
          <div className="space-y-2">
            <Label>Servicio *</Label>
            <Select
              value={servicioId}
              onValueChange={(v) => {
                setServicioId(v);
                resetChoque();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Elegí un servicio" />
              </SelectTrigger>
              <SelectContent>
                {servicios.filter((s) => s.agendable).map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.nombre} · {s.duracion_min} min
                    {s.precio != null &&
                      ` · $${Number(s.precio).toLocaleString("es-AR")}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Profesional */}
          <div className="space-y-2">
            <Label>Profesional *</Label>
            <Select
              value={recursoId}
              onValueChange={(v) => {
                setRecursoId(v);
                resetChoque();
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Elegí un profesional" />
              </SelectTrigger>
              <SelectContent>
                {recursos.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>
                    {r.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Fecha + hora */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="fecha">Fecha *</Label>
              <Input
                id="fecha"
                type="date"
                value={fecha}
                onChange={(e) => {
                  setFecha(e.target.value);
                  resetChoque();
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hora">Hora *</Label>
              <Input
                id="hora"
                type="time"
                value={hora}
                onChange={(e) => {
                  setHora(e.target.value);
                  resetChoque();
                }}
              />
            </div>
          </div>

          {/* Bloque de sobreturno: solo aparece si hubo choque */}
          {hayChoque && (
            <div className="space-y-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle
                  size={18}
                  className="mt-0.5 shrink-0 text-amber-600"
                />
                <div className="space-y-0.5">
                  <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                    Horario ocupado
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Ya hay un turno en ese carril y horario. Podés forzarlo como
                    sobreturno si vas a poder atenderlo igual.
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-amber-500/20 pt-3">
                <Label htmlFor="forzar" className="cursor-pointer">
                  Forzar como sobreturno
                </Label>
                <Switch id="forzar" checked={forzar} onCheckedChange={setForzar} />
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={cerrar} disabled={guardando}>
            Cancelar
          </Button>
          <Button onClick={guardar} disabled={guardando || (hayChoque && !forzar)}>
            {guardando
              ? "Creando…"
              : hayChoque
                ? "Crear igual (sobreturno)"
                : "Crear turno"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}