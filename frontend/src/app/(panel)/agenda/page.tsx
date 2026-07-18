"use client";
 
/**
 * Agenda visual (/agenda).
 *
 * Vista principal: la GRILLA DE CARRILES (Corte/Tintura/Barba) donde se ven los
 * turnos en sus columnas y se crea con clic en un hueco. Debajo, la lista de
 * turnos (vista alternativa, por ahora). El botón "Nuevo turno" y el clic en
 * hueco abren el mismo diálogo (con sobreturno inteligente).
 */
 
import { useEffect, useState, useCallback } from "react";
import { addDays, format, startOfDay, endOfDay, startOfWeek, endOfWeek, startOfMonth, endOfMonth, addMonths } from "date-fns";
import { isToday } from "date-fns/isToday";
import { es } from "date-fns/locale";
import { Plus, Printer, Search } from "lucide-react";
 
import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { listarHorarios, Horario } from "@/lib/horarios-api";
import { listarServicios, Servicio } from "@/lib/servicios-api";
import { listarTurnos, listarTurnosDelDia, moverTurno, Turno } from "@/lib/turnos-api";
import { carrilesDeGrupos } from "@/lib/carriles";
import { MetricasDia } from "./metricas-dia";
import { TurnoDetalle } from "./turno-detalle";
import { NuevoTurnoDialog } from "./nuevo-turno-dialog";
import { GrillaCarriles } from "./grilla-carriles";
import { imprimirDia } from "./imprimir-dia";
import { BuscarHuecoDialog } from "./buscar-hueco-dialog";
import { GrillaSemana } from "./grilla-semana";
import { CalendarioMes } from "./calendario-mes";
import { GrillaEquipo } from "./grilla-equipo";
import {
  colorEstadoHex,
  estaInactivo,
  labelEstado,
  horaDe,
  inicialDe,
} from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
 
/** Ordena los turnos por hora de inicio. */
function ordenarPorHora(turnos: Turno[]): Turno[] {
  return [...turnos].sort((a, b) => {
    const ta = a.fecha_inicio ? new Date(a.fecha_inicio).getTime() : 0;
    const tb = b.fecha_inicio ? new Date(b.fecha_inicio).getTime() : 0;
    return ta - tb;
  });
}
 
/** "lunes 13 de julio" → "Lunes 13 de julio" (solo la primera letra). */
function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function AgendaPage() {
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [horarios, setHorarios] = useState<Horario[]>([]);
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [recursoId, setRecursoId] = useState<number | null>(null);
  const [dia, setDia] = useState<Date>(startOfDay(new Date()));
  const [vista, setVista] = useState<"dia" | "semana" | "mes" | "equipo">("dia");
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [turnosDia, setTurnosDia] = useState<Turno[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turnoSel, setTurnoSel] = useState<Turno | null>(null);
 
  // Diálogo de nuevo turno + datos del hueco clickeado
  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [buscarAbierto, setBuscarAbierto] = useState(false);
  const [huecoCarril, setHuecoCarril] = useState<string | null>(null);
  const [huecoFecha, setHuecoFecha] = useState<Date | null>(null);
 
  const hoyEs = isToday(dia);
 
  const cargarRecursos = useCallback(async () => {
    try {
      const data = await listarRecursos();
      const personas = data.items.filter((r) => r.tipo === "persona");
      setRecursos(personas);
      if (personas.length > 0) {
        setRecursoId((actual) => actual ?? personas[0].id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    }
  }, []);
 
  useEffect(() => {
    cargarRecursos();
  }, [cargarRecursos]);
 
  // Servicios del negocio: definen las columnas de la grilla (por grupo_agenda).
  useEffect(() => {
    listarServicios()
      .then((d) => setServicios(d.items))
      .catch(() => setServicios([]));
  }, []);
 
  const cargarTurnos = useCallback(async () => {
    if (recursoId === null) return;
    setCargando(true);
    setError(null);
    try {
      // El recurso se carga según la vista; las métricas, siempre del día.
      let inicioRango: Date;
      let finRango: Date;
      if (vista === "mes") {
        inicioRango = startOfWeek(startOfMonth(dia), { weekStartsOn: 1 });
        finRango = endOfWeek(endOfMonth(dia), { weekStartsOn: 1 });
      } else if (vista === "semana") {
        inicioRango = startOfWeek(dia, { weekStartsOn: 1 });
        finRango = endOfWeek(dia, { weekStartsOn: 1 });
      } else {
        inicioRango = startOfDay(dia);
        finRango = endOfDay(dia);
      }
      const desde = inicioRango.toISOString();
      const hasta = finRango.toISOString();
      const desdeDia = startOfDay(dia).toISOString();
      const hastaDia = endOfDay(dia).toISOString();
 
      if (vista === "equipo") {
        // Equipo: todos los barberos del día (sin filtrar por recurso)
        const data = await listarTurnosDelDia(desdeDia, hastaDia);
        setTurnos(ordenarPorHora(data.items));
        setTurnosDia(data.items);
      } else {
        const [delRecurso, delDia] = await Promise.all([
          listarTurnos(recursoId, desde, hasta),
          listarTurnosDelDia(desdeDia, hastaDia),
        ]);
        setTurnos(ordenarPorHora(delRecurso.items));
        setTurnosDia(delDia.items);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar turnos");
    } finally {
      setCargando(false);
    }
  }, [recursoId, dia, vista]);
 
  useEffect(() => {
    cargarTurnos();
  }, [cargarTurnos]);

  // Mantener el panel de detalle en sincronía: cuando la agenda se recarga
  // tras un cambio de estado, el panel queda abierto pero debe mostrar el
  // turno actualizado (mismo id, estado nuevo). Si el turno ya no está en la
  // lista (otro día, filtro), no lo tocamos.
  useEffect(() => {
    if (turnoSel === null) return;
    const fresco =
      turnos.find((t) => t.id === turnoSel.id) ??
      turnosDia.find((t) => t.id === turnoSel.id);
    if (fresco && fresco !== turnoSel) {
      setTurnoSel(fresco);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnos, turnosDia]);
 
  // Carga el horario del barbero elegido (para dibujar la grilla a su medida).
  useEffect(() => {
    if (recursoId === null) {
      setHorarios([]);
      return;
    }
    listarHorarios(recursoId)
      .then(setHorarios)
      .catch(() => setHorarios([]));
  }, [recursoId]);
 
  const recursoActual = recursos.find((r) => r.id === recursoId);
 
  // Columnas de la grilla, generadas desde los grupos de los servicios.
  const carriles = carrilesDeGrupos(servicios.filter((s) => s.agendable).map((s) => s.grupo_agenda));
 
  // --- Horario del barbero para el día mostrado ---
  /** "09:00:00" → minutos desde medianoche (540). */
  function aMinutos(hhmmss: string): number {
    const [h, m] = hhmmss.split(":");
    return Number(h) * 60 + Number(m);
  }
 
  // JS: 0=domingo…6=sábado. Backend: 0=lunes…6=domingo.
  const diaSemana = (dia.getDay() + 6) % 7;
  const franjasDia = horarios
    .filter((h) => h.dia_semana === diaSemana)
    .map((h) => ({
      desdeMin: aMinutos(h.hora_desde),
      hastaMin: aMinutos(h.hora_hasta),
    }))
    .sort((a, b) => a.desdeMin - b.desdeMin);
 
  const atiendeHoy = franjasDia.length > 0;
  const horaInicio = atiendeHoy
    ? Math.floor(Math.min(...franjasDia.map((f) => f.desdeMin)) / 60)
    : 9;
  const horaFin = atiendeHoy
    ? Math.ceil(Math.max(...franjasDia.map((f) => f.hastaMin)) / 60)
    : 19;
 
  // Rango horario para la vista semanal (min/max de todos los días con horario)
  const todasFranjas = horarios.map((h) => ({
    desdeMin: aMinutos(h.hora_desde),
    hastaMin: aMinutos(h.hora_hasta),
  }));
  const horaInicioSemana = todasFranjas.length
    ? Math.floor(Math.min(...todasFranjas.map((f) => f.desdeMin)) / 60)
    : 9;
  const horaFinSemana = todasFranjas.length
    ? Math.ceil(Math.max(...todasFranjas.map((f) => f.hastaMin)) / 60)
    : 19;
 
  // Etiqueta del período según la vista
  const inicioSem = startOfWeek(dia, { weekStartsOn: 1 });
  const finSem = endOfWeek(dia, { weekStartsOn: 1 });
  const etiquetaPeriodo =
    vista === "mes"
      ? format(dia, "MMMM yyyy", { locale: es })
      : vista === "semana"
        ? `${format(inicioSem, "d", { locale: es })} – ${format(finSem, "d 'de' MMMM", { locale: es })}`
        : vista === "equipo"
          ? `${cap(format(dia, "EEEE d 'de' MMMM", { locale: es }))} · equipo`
          : cap(format(dia, "EEEE d 'de' MMMM", { locale: es }));
 
  /** Reprograma un turno al soltarlo en otra franja (drag & drop). */
  async function manejarMover(turno: Turno, nuevaFecha: Date) {
    try {
      await moverTurno(turno.id, nuevaFecha.toISOString());
      toast.success("Turno reprogramado");
      cargarTurnos();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo mover el turno",
      );
    }
  }
 
  /** Cierra el diálogo y limpia los datos del hueco. */
  function cerrarDialogo() {
    setDialogAbierto(false);
    setHuecoCarril(null);
    setHuecoFecha(null);
  }
 
  return (
    <div className="p-8">
      {/* Encabezado */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agenda</h1>
 
        <div className="flex items-center gap-3">
          {recursos.length > 0 && vista !== "equipo" && (
            <Select
              value={recursoId ? String(recursoId) : undefined}
              onValueChange={(v) => setRecursoId(Number(v))}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Elegí un recurso">
                  {(v) =>
                    recursos.find((r) => String(r.id) === String(v))?.nombre ?? v
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {recursos.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>
                    {r.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
 
          {/* Selector de vista */}
          <div className="flex items-center rounded-lg border p-0.5">
            <button
              onClick={() => setVista("dia")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                vista === "dia"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Día
            </button>
            <button
              onClick={() => setVista("semana")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                vista === "semana"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Semana
            </button>
            <button
              onClick={() => setVista("mes")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                vista === "mes"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Mes
            </button>
            <button
              onClick={() => setVista("equipo")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                vista === "equipo"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Equipo
            </button>
          </div>
 
          {/* Navegación (se mueve de a un día o una semana) */}
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={() =>
                setDia((d) =>
                  vista === "mes"
                    ? addMonths(d, -1)
                    : addDays(d, vista === "semana" ? -7 : -1),
                )
              }
              aria-label="Anterior"
            >
              ‹
            </Button>
            <Button
              variant={hoyEs ? "default" : "outline"}
              size="sm"
              onClick={() => setDia(startOfDay(new Date()))}
            >
              Hoy
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() =>
                setDia((d) =>
                  vista === "mes"
                    ? addMonths(d, 1)
                    : addDays(d, vista === "semana" ? 7 : 1),
                )
              }
              aria-label="Siguiente"
            >
              ›
            </Button>
          </div>
 
          <Button variant="outline" onClick={() => setBuscarAbierto(true)}>
            <Search size={16} className="mr-1" />
            Buscar hueco
          </Button>
 
          {vista === "dia" && (
            <Button
              variant="outline"
              onClick={() =>
                imprimirDia({
                  titulo: "Agenda del día",
                  subtitulo: `${recursoActual?.nombre ?? ""} · ${cap(format(dia, "EEEE d 'de' MMMM", { locale: es }))}`,
                  filas: turnos
                    .filter((t) => t.estado !== "cancelado")
                    .map((t) => ({
                      hora: t.fecha_inicio ? horaDe(t.fecha_inicio) : "",
                      cliente: t.cliente_nombre ?? "",
                      servicio: t.servicio_nombre ?? "Sin servicio",
                      estado: labelEstado(t.estado),
                    })),
                })
              }
            >
              <Printer size={16} className="mr-1" />
              Imprimir
            </Button>
          )}
 
          <Button
            onClick={() => {
              setHuecoCarril(null);
              setHuecoFecha(null);
              setDialogAbierto(true);
            }}
          >
            <Plus size={16} className="mr-1" />
            Nuevo turno
          </Button>
        </div>
      </div>
 
      {vista === "dia" && <MetricasDia turnos={turnosDia} />}
 
      <p className="mb-4 text-sm font-medium text-muted-foreground">
        {etiquetaPeriodo}
        {recursoActual && ` · ${recursoActual.nombre}`}
        {cargando && " · cargando…"}
      </p>
 
      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}
 
      {/* Vista semanal: grilla horaria de 7 días */}
      {vista === "semana" && (
        <div className="mb-8">
          <GrillaSemana
            turnos={turnos}
            dia={dia}
            horaInicio={horaInicioSemana}
            horaFin={horaFinSemana}
            horarios={horarios}
            onClickTurno={(t) => setTurnoSel(t)}
            onClickHueco={(fecha) => {
              setHuecoCarril(null);
              setHuecoFecha(fecha);
              setDialogAbierto(true);
            }}
          />
        </div>
      )}
 
      {/* Vista de equipo: una columna por barbero */}
      {vista === "equipo" && (
        <div className="mb-8">
          <GrillaEquipo
            turnos={turnos}
            recursos={recursos}
            dia={dia}
            horaInicio={horaInicioSemana}
            horaFin={horaFinSemana}
            onClickTurno={(t) => setTurnoSel(t)}
            onClickHueco={(rid, fecha) => {
              setRecursoId(rid);
              setHuecoCarril(null);
              setHuecoFecha(fecha);
              setDialogAbierto(true);
            }}
          />
        </div>
      )}
 
      {/* Vista mensual: calendario con resumen por día */}
      {vista === "mes" && (
        <div className="mb-8">
          <CalendarioMes
            turnos={turnos}
            dia={dia}
            onClickDia={(d) => {
              setDia(startOfDay(d));
              setVista("dia");
            }}
          />
        </div>
      )}
 
      {/* Vista diaria: grilla de carriles + listado */}
      {vista === "dia" && (
        <>
          <div className="mb-8">
            {!atiendeHoy && (
          <div className="mb-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
            {recursoActual?.nombre ?? "Este recurso"} no atiende este día. Podés
            anotar igual si hace falta (queda como sobreturno).
          </div>
        )}
        <GrillaCarriles
          turnos={turnos}
          carriles={carriles}
          dia={dia}
          horaInicio={horaInicio}
          horaFin={horaFin}
          franjasTrabajo={franjasDia}
          onMoverTurno={manejarMover}
          onClickTurno={(t) => setTurnoSel(t)}
          onClickHueco={(carril, fecha) => {
            setHuecoCarril(carril);
            setHuecoFecha(fecha);
            setDialogAbierto(true);
          }}
        />
      </div>
 
      {/* Lista de turnos (vista alternativa, por ahora) */}
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Listado del día
      </h2>
      {!cargando && turnos.length === 0 ? (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            {recursoActual?.nombre ?? "Este recurso"} no tiene turnos este día.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border bg-card">
          {turnos.map((turno, i) => {
            const color = colorEstadoHex(turno.estado);
            const inactivo = estaInactivo(turno.estado);
            return (
              <div
                key={turno.id}
                onClick={() => setTurnoSel(turno)}
                className={`flex cursor-pointer items-stretch transition-colors hover:bg-muted/50 ${
                  i > 0 ? "border-t" : ""
                }`}
                style={{ opacity: inactivo ? 0.6 : 1 }}
              >
                {/* Hora a la izquierda */}
                <div className="flex w-24 shrink-0 flex-col items-end justify-center border-r px-4 py-4">
                  <span
                    className="text-sm font-bold"
                    style={{
                      fontFamily: "Syne, sans-serif",
                      fontVariantNumeric: "lining-nums tabular-nums",
                    }}
                  >
                    {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                  </span>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {turno.fecha_fin && horaDe(turno.fecha_fin)}
                  </span>
                </div>
 
                {/* Barra de color (estado) */}
                <div
                  className="w-1 shrink-0"
                  style={{ backgroundColor: color }}
                />
 
                {/* Contenido */}
                <div className="flex min-w-0 flex-1 items-center gap-3 px-4 py-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white"
                    style={{
                      backgroundColor: color,
                      fontFamily: "Syne, sans-serif",
                    }}
                  >
                    {inicialDe(turno.cliente_nombre)}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span
                      className={`truncate text-sm font-semibold ${
                        inactivo ? "line-through" : ""
                      }`}
                    >
                      {turno.cliente_nombre}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {turno.servicio_nombre ?? "Sin servicio"}
                      {turno.es_sobreturno && " · sobreturno"}
                    </span>
                  </div>
                  <span
                    className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
                    style={{ backgroundColor: `${color}22`, color: color }}
                  >
                    {labelEstado(turno.estado)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
 
      {/* Leyenda */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {(["pendiente", "confirmado", "en_curso", "finalizado", "cancelado"] as const).map(
          (e) => (
            <span key={e} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: colorEstadoHex(e) }}
              />
              {labelEstado(e)}
            </span>
          ),
        )}
      </div>
        </>
      )}
 
      {/* Panel de detalle del turno */}
      <TurnoDetalle
        turno={turnoSel}
        abierto={turnoSel !== null}
        onCerrar={() => setTurnoSel(null)}
        onCambio={cargarTurnos}
      />
 
      {/* Diálogo de nuevo turno (con sobreturno inteligente) */}
      <NuevoTurnoDialog
        abierto={dialogAbierto}
        onCerrar={cerrarDialogo}
        onCreado={cargarTurnos}
        recursoInicial={recursoId}
        fechaInicial={huecoFecha ?? dia}
        carrilInicial={huecoCarril}
      />
 
      {/* Diálogo de búsqueda de hueco libre */}
      <BuscarHuecoDialog
        abierto={buscarAbierto}
        onCerrar={() => setBuscarAbierto(false)}
        recursos={recursos}
        servicios={servicios}
        recursoInicial={recursoId}
        onElegir={(rid, fecha) => {
          setRecursoId(rid);
          setHuecoCarril(null);
          setHuecoFecha(fecha);
          setDialogAbierto(true);
        }}
      />
    </div>
  );
}