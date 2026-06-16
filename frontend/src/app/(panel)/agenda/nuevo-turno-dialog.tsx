"use client";

/**
 * Diálogo para crear un turno desde la agenda.
 *
 * Junta: selector de cliente (buscar/crear) + servicio + barbero + fecha/hora.
 * Al guardar llama a POST /turnos, que valida disponibilidad en el backend.
 *
 * Puede abrirse de dos formas:
 * - Botón "Nuevo turno": campos vacíos (o con el barbero/fecha actual).
 * - Clic en un hueco: viene con recurso y hora precargados (prefill).
 */

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { format } from "date-fns";

import { Cliente } from "@/lib/clientes-api";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { crearTurno } from "@/lib/turnos-api";
import { ApiError } from "@/lib/api";
import { SelectorCliente } from "./selector-cliente";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
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
  // Prefill opcional (cuando se abre desde un hueco de la agenda)
  recursoInicial?: number | null;
  fechaInicial?: Date | null; // fecha + hora del hueco
}

export function NuevoTurnoDialog({
  abierto,
  onCerrar,
  onCreado,
  recursoInicial = null,
  fechaInicial = null,
}: NuevoTurnoDialogProps) {
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [recursos, setRecursos] = useState<Recurso[]>([]);

  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [servicioId, setServicioId] = useState<string>("");
  const [recursoId, setRecursoId] = useState<string>("");
  const [fecha, setFecha] = useState<string>(""); // yyyy-MM-dd
  const [hora, setHora] = useState<string>(""); // HH:mm
  const [guardando, setGuardando] = useState(false);

  // Cargar servicios y recursos al abrir
  useEffect(() => {
    if (!abierto) return;
    listarServicios().then((d) => setServicios(d.items)).catch(() => {});
    listarRecursos()
      .then((d) => setRecursos(d.items.filter((r) => r.tipo === "persona")))
      .catch(() => {});
  }, [abierto]);

  // Aplicar prefill cuando se abre desde un hueco
  useEffect(() => {
    if (!abierto) return;
    if (recursoInicial != null) setRecursoId(String(recursoInicial));
    if (fechaInicial) {
      setFecha(format(fechaInicial, "yyyy-MM-dd"));
      setHora(format(fechaInicial, "HH:mm"));
    }
  }, [abierto, recursoInicial, fechaInicial]);

  function limpiar() {
    setCliente(null);
    setServicioId("");
    setRecursoId("");
    setFecha("");
    setHora("");
  }

  function cerrar() {
    limpiar();
    onCerrar();
  }

  async function guardar() {
    // Validaciones simples antes de mandar
    if (!cliente) {
      toast.error("Elegí un cliente");
      return;
    }
    if (!servicioId) {
      toast.error("Elegí un servicio");
      return;
    }
    if (!recursoId) {
      toast.error("Elegí un profesional");
      return;
    }
    if (!fecha || !hora) {
      toast.error("Elegí fecha y hora");
      return;
    }

    // Construir la fecha de inicio. La guardamos "tal cual" en UTC para que
    // coincida con cómo la lee la agenda (hora de pared del local).
    const fechaInicio = `${fecha}T${hora}:00Z`;

    setGuardando(true);
    try {
      await crearTurno({
        cliente_id: cliente.id,
        servicio_id: Number(servicioId),
        recurso_id: Number(recursoId),
        fecha_inicio: fechaInicio,
      });
      toast.success("Turno creado");
      limpiar();
      onCreado();
      onCerrar();
    } catch (err) {
      // El backend devuelve 409 si el horario no está disponible
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo crear el turno",
      );
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
          {/* Cliente (buscar o crear) */}
          <div className="space-y-2">
            <Label>Cliente *</Label>
            <SelectorCliente
              clienteElegido={cliente}
              onSeleccion={setCliente}
            />
          </div>

          {/* Servicio */}
          <div className="space-y-2">
            <Label>Servicio *</Label>
            <Select value={servicioId} onValueChange={setServicioId}>
              <SelectTrigger>
                <SelectValue placeholder="Elegí un servicio" />
              </SelectTrigger>
              <SelectContent>
                {servicios.map((s) => (
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
            <Select value={recursoId} onValueChange={setRecursoId}>
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
                onChange={(e) => setFecha(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hora">Hora *</Label>
              <Input
                id="hora"
                type="time"
                value={hora}
                onChange={(e) => setHora(e.target.value)}
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={cerrar} disabled={guardando}>
            Cancelar
          </Button>
          <Button onClick={guardar} disabled={guardando}>
            {guardando ? "Creando…" : "Crear turno"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}