"use client";

/**
 * Reglas de reserva (/reglas-reserva).
 *
 * Configura cómo le entran los turnos al negocio desde la vidriera pública.
 * Antes estas reglas vivían hardcodeadas en el backend e iguales para todos
 * los negocios: 180 días hacia adelante, sin anticipación mínima.
 *
 * El texto de cada regla está escrito para el dueño, no para un programador:
 * "hasta 1 hora antes del turno", no "anticipacion_min = 60".
 */

import { useCallback, useEffect, useState } from "react";
import { format, addDays, parseISO, isValid } from "date-fns";
import { es } from "date-fns/locale";
import { toast } from "sonner";
import { CalendarClock, Save } from "lucide-react";

import {
  leerReglasReserva,
  guardarReglasReserva,
  type ReglasReserva,
} from "@/lib/empresa-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

const SYNE = { fontFamily: "Syne, sans-serif" } as const;

/** Opciones de anticipación mínima, en minutos. */
const ANTICIPACIONES = [
  { valor: 0, label: "Sin mínimo" },
  { valor: 30, label: "30 minutos" },
  { valor: 60, label: "1 hora" },
  { valor: 120, label: "2 horas" },
  { valor: 240, label: "4 horas" },
  { valor: 720, label: "12 horas" },
  { valor: 1440, label: "1 día" },
  { valor: 2880, label: "2 días" },
];

/** Opciones de ventana hacia adelante, en días. */
const VENTANAS = [
  { valor: 15, label: "15 días" },
  { valor: 30, label: "1 mes" },
  { valor: 60, label: "2 meses" },
  { valor: 90, label: "3 meses" },
  { valor: 180, label: "6 meses" },
  { valor: 365, label: "1 año" },
];

function Seccion({
  titulo,
  descripcion,
  children,
}: {
  titulo: string;
  descripcion?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border bg-card p-5 md:p-6">
      <h2 className="text-base font-bold" style={SYNE}>
        {titulo}
      </h2>
      {descripcion && (
        <p className="mt-1 text-sm text-muted-foreground">{descripcion}</p>
      )}
      <div className="mt-5 space-y-5">{children}</div>
    </section>
  );
}

/** Fila con switch a la derecha y explicación debajo del título. */
function FilaSwitch({
  titulo,
  detalle,
  valor,
  onChange,
}: {
  titulo: string;
  detalle: string;
  valor: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-sm font-medium">{titulo}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">{detalle}</p>
      </div>
      <Switch checked={valor} onCheckedChange={onChange} />
    </div>
  );
}

/** Grupo de botones tipo "chips". Más rápido de tocar en celular que un select. */
function Chips<T extends number>({
  opciones,
  valor,
  onChange,
}: {
  opciones: { valor: T; label: string }[];
  valor: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {opciones.map((o) => {
        const activo = o.valor === valor;
        return (
          <button
            key={o.valor}
            type="button"
            onClick={() => onChange(o.valor)}
            className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
              activo
                ? "border-transparent bg-foreground text-background"
                : "bg-background hover:bg-muted"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export default function ReglasReservaPage() {
  const [form, setForm] = useState<ReglasReserva | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setForm(await leerReglasReserva());
    } catch {
      toast.error("No se pudieron cargar las reglas");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function set<K extends keyof ReglasReserva>(clave: K, valor: ReglasReserva[K]) {
    setForm((f) => (f ? { ...f, [clave]: valor } : f));
  }

  /**
   * Hasta qué día queda abierta la agenda, mostrando la regla que MANDA.
   * Entre "X días hacia adelante" y la fecha fija gana la más restrictiva:
   * si no se explica, el dueño pone una fecha y no entiende por qué la
   * agenda cierra antes.
   */
  function topeEfectivo(f: ReglasReserva): { fecha: Date; porFechaFija: boolean } {
    const porDias = addDays(new Date(), f.dias_max);
    if (f.fecha_limite) {
      const fija = parseISO(f.fecha_limite);
      if (isValid(fija) && fija < porDias) return { fecha: fija, porFechaFija: true };
    }
    return { fecha: porDias, porFechaFija: false };
  }

  async function guardar() {
    if (!form) return;
    setGuardando(true);
    try {
      const limpio: ReglasReserva = {
        ...form,
        // Un input date a medio tipear manda "" y el backend espera null.
        fecha_limite:
          form.fecha_limite && /^\d{4}-\d{2}-\d{2}$/.test(form.fecha_limite)
            ? form.fecha_limite
            : null,
      };
      setForm(await guardarReglasReserva(limpio));
      toast.success("Reglas guardadas");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return <p className="p-6 text-sm text-muted-foreground">Cargando…</p>;
  }
  if (!form) {
    return <p className="p-6 text-sm text-muted-foreground">No se pudo cargar.</p>;
  }

  const tope = topeEfectivo(form);

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold" style={SYNE}>
            <CalendarClock className="h-6 w-6" />
            Reglas de reserva
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Cómo te entran los turnos desde tu página. Podés cambiarlas cuando
            quieras.
          </p>
        </div>
        <Button onClick={guardar} disabled={guardando}>
          <Save className="mr-2 h-4 w-4" />
          {guardando ? "Guardando…" : "Guardar"}
        </Button>
      </header>

      <Seccion
        titulo="Cuándo pueden reservar"
        descripcion="Define la ventana de tiempo en la que tu agenda acepta turnos online."
      >
        <div className="space-y-2">
          <Label>Anticipación mínima</Label>
          <p className="text-sm text-muted-foreground">
            Cuánto antes del turno se corta la reserva online. Sirve para que no
            te entre un turno para dentro de diez minutos mientras estás
            atendiendo.
          </p>
          <Chips
            opciones={ANTICIPACIONES}
            valor={form.anticipacion_min}
            onChange={(v) => set("anticipacion_min", v)}
          />
        </div>

        <div className="space-y-2">
          <Label>Hasta cuándo se puede reservar</Label>
          <p className="text-sm text-muted-foreground">
            Cuánto hacia adelante está abierta tu agenda.
          </p>
          <Chips
            opciones={VENTANAS}
            valor={form.dias_max}
            onChange={(v) => set("dias_max", v)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="fecha_limite">Fecha de cierre (opcional)</Label>
          <p className="text-sm text-muted-foreground">
            Una fecha fija a partir de la cual no se toman más turnos. Útil si
            cerrás por vacaciones. Dejala vacía si no la necesitás.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              id="fecha_limite"
              type="date"
              className="w-48"
              value={form.fecha_limite ?? ""}
              onChange={(e) => set("fecha_limite", e.target.value || null)}
            />
            {form.fecha_limite && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => set("fecha_limite", null)}
              >
                Quitar
              </Button>
            )}
          </div>
        </div>

        <div className="rounded-xl bg-muted/60 p-3.5 text-sm">
          Tus clientes pueden reservar hasta el{" "}
          <strong>
            {format(tope.fecha, "d 'de' MMMM 'de' yyyy", { locale: es })}
          </strong>{" "}
          inclusive.
          {tope.porFechaFija && (
            <span className="text-muted-foreground">
              {" "}
              Manda la fecha de cierre, que llega antes que el plazo elegido
              arriba.
            </span>
          )}
        </div>
      </Seccion>

      <Seccion
        titulo="Qué datos les pedís"
        descripcion="Cuantos menos campos, más reservas se completan. Pedí solo lo que vas a usar."
      >
        <FilaSwitch
          titulo="Número de teléfono"
          detalle="Es con lo que el sistema identifica al cliente y te deja escribirle por WhatsApp. Si lo apagás, vas a tener fichas repetidas."
          valor={form.pide_telefono}
          onChange={(v) => set("pide_telefono", v)}
        />
        <FilaSwitch
          titulo="Fecha de nacimiento"
          detalle="Habilita la campaña de saludo de cumpleaños, que es la mejor excusa para mandar un descuento."
          valor={form.pide_nacimiento}
          onChange={(v) => set("pide_nacimiento", v)}
        />
      </Seccion>

      <Seccion titulo="Cancelaciones">
        <FilaSwitch
          titulo="Permitir que cancelen o reprogramen"
          detalle="Si el cliente ya pagó una seña, la seña no se devuelve. Apagarlo no evita ausentes: solo hace que no te avisen."
          valor={form.permite_cancelar}
          onChange={(v) => set("permite_cancelar", v)}
        />
      </Seccion>
    </div>
  );
}
