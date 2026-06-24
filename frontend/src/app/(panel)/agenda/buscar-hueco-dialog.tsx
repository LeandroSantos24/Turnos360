"use client";
 
/**
 * Diálogo "Buscar hueco libre".
 *
 * Elegís servicio + barbero + día y consulta al backend los horarios de inicio
 * disponibles (respeta franjas, excepciones, buffer y carril). Al tocar un
 * horario, avisa al padre para abrir el alta de turno con ese hueco precargado.
 */
 
import { useState } from "react";
import { format } from "date-fns";
import { Search } from "lucide-react";
 
import { Recurso } from "@/lib/recursos-api";
import { Servicio } from "@/lib/servicios-api";
import { buscarHuecos } from "@/lib/turnos-api";
import { ApiError } from "@/lib/api";
 
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
 
interface BuscarHuecoDialogProps {
  abierto: boolean;
  onCerrar: () => void;
  recursos: Recurso[];
  servicios: Servicio[];
  recursoInicial?: number | null;
  /** Al elegir un hueco: barbero + fecha/hora exactas. */
  onElegir: (recursoId: number, fecha: Date) => void;
}
 
/** Parsea un ISO tratándolo como UTC aunque venga sin "Z" (igual que el resto). */
function aFechaUTC(iso: string): Date {
  const tieneTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(tieneTz ? iso : iso + "Z");
}
 
function horaUTC(d: Date): string {
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(
    d.getUTCMinutes(),
  ).padStart(2, "0")}`;
}
 
export function BuscarHuecoDialog({
  abierto,
  onCerrar,
  recursos,
  servicios,
  recursoInicial = null,
  onElegir,
}: BuscarHuecoDialogProps) {
  const [servicioId, setServicioId] = useState("");
  const [recursoId, setRecursoId] = useState(
    recursoInicial ? String(recursoInicial) : "",
  );
  const [fecha, setFecha] = useState(format(new Date(), "yyyy-MM-dd"));
  const [huecos, setHuecos] = useState<string[]>([]);
  const [cargando, setCargando] = useState(false);
  const [buscado, setBuscado] = useState(false);
  const [error, setError] = useState<string | null>(null);
 
  const puedeBuscar = servicioId !== "" && recursoId !== "" && fecha !== "";
 
  async function buscar() {
    if (!puedeBuscar) return;
    setCargando(true);
    setError(null);
    setBuscado(true);
    try {
      const data = await buscarHuecos(
        Number(recursoId),
        fecha,
        Number(servicioId),
      );
      setHuecos(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al buscar huecos");
      setHuecos([]);
    } finally {
      setCargando(false);
    }
  }
 
  function elegir(hueco: string) {
    onElegir(Number(recursoId), aFechaUTC(hueco));
    onCerrar();
  }
 
  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Buscar hueco libre</DialogTitle>
          <DialogDescription>
            Elegí servicio, barbero y día para ver los horarios disponibles.
          </DialogDescription>
        </DialogHeader>
 
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Servicio</Label>
            <Select value={servicioId} onValueChange={setServicioId}>
              <SelectTrigger>
                <SelectValue placeholder="Elegí un servicio" />
              </SelectTrigger>
              <SelectContent>
                {servicios.filter((s) => s.agendable).map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.nombre} ({s.duracion_min} min)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
 
          <div className="flex flex-col gap-1.5">
            <Label>Barbero</Label>
            <Select value={recursoId} onValueChange={setRecursoId}>
              <SelectTrigger>
                <SelectValue placeholder="Elegí un barbero" />
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
 
          <div className="flex flex-col gap-1.5">
            <Label>Día</Label>
            <Input
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
            />
          </div>
 
          <Button onClick={buscar} disabled={!puedeBuscar || cargando}>
            <Search size={16} className="mr-1" />
            {cargando ? "Buscando…" : "Buscar"}
          </Button>
 
          {error && <p className="text-sm text-destructive">{error}</p>}
 
          {/* Resultados */}
          {buscado &&
            !cargando &&
            !error &&
            (huecos.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                No hay huecos ese día. Probá con otra fecha.
              </p>
            ) : (
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {huecos.length} horario{huecos.length === 1 ? "" : "s"} disponible
                  {huecos.length === 1 ? "" : "s"}:
                </p>
                <div className="grid grid-cols-4 gap-2">
                  {huecos.map((h) => (
                    <button
                      key={h}
                      onClick={() => elegir(h)}
                      className="rounded-lg border px-2 py-2 text-sm font-medium tabular-nums transition-colors hover:border-primary hover:bg-primary/10"
                    >
                      {horaUTC(aFechaUTC(h))}
                    </button>
                  ))}
                </div>
              </div>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}