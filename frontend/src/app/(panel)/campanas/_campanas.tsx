"use client";

/**
 * Lo que comparten los apartados de «Campañas»: la configuración (una sola
 * lectura y el guardado automático) y la actividad real de los últimos 30
 * días, más las piezas de cada tarjeta.
 *
 * SE GUARDA SOLO
 * ──────────────
 * Cada cambio se guarda con un respiro de 800 ms y el estado se ve arriba,
 * en el encabezado. El estado vive acá (en el layout) y no en cada pestaña:
 * así cambiar de pestaña no corta un guardado a medio salir.
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertTriangle, Bell, Check, Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import {
  guardarAutomatizaciones,
  obtenerActividadCampanas,
  obtenerAutomatizaciones,
  probarCampana,
  type ActividadCampanas,
  type Automatizaciones,
} from "@/lib/empresa-api";
import { ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type EstadoGuardado = "quieto" | "guardando" | "guardado";

interface Contexto {
  cfg: Automatizaciones | null;
  set: <K extends keyof Automatizaciones>(clave: K, valor: Automatizaciones[K]) => void;
  estado: EstadoGuardado;
  actividad: ActividadCampanas | null;
}

const Ctx = createContext<Contexto | null>(null);

export function ProveedorCampanas({ children }: { children: React.ReactNode }) {
  const [cfg, setCfg] = useState<Automatizaciones | null>(null);
  const [estado, setEstado] = useState<EstadoGuardado>("quieto");
  const [actividad, setActividad] = useState<ActividadCampanas | null>(null);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Lo último que sabemos que está guardado en el servidor. Se compara
  // contra esto y no contra «es la primera carga»: si la lectura llega dos
  // veces (o se prende y apaga un switch), no hay nada nuevo que mandar.
  const enServidor = useRef<string | null>(null);

  useEffect(() => {
    obtenerAutomatizaciones()
      .then((c) => {
        enServidor.current = JSON.stringify(c);
        setCfg(c);
      })
      .catch(() => toast.error("No se pudieron cargar las campañas"));
    // La actividad es un extra: si falla, las campañas se configuran igual.
    obtenerActividadCampanas()
      .then(setActividad)
      .catch(() => setActividad(null));
  }, []);

  const guardar = useCallback((datos: Automatizaciones) => {
    if (temporizador.current) clearTimeout(temporizador.current);
    setEstado("guardando");
    temporizador.current = setTimeout(async () => {
      try {
        await guardarAutomatizaciones(datos);
        enServidor.current = JSON.stringify(datos);
        setEstado("guardado");
        setTimeout(() => setEstado("quieto"), 2200);
      } catch (e) {
        setEstado("quieto");
        toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
      }
    }, 800);
  }, []);

  useEffect(() => {
    if (!cfg || JSON.stringify(cfg) === enServidor.current) return;
    guardar(cfg);
  }, [cfg, guardar]);

  useEffect(
    () => () => {
      if (temporizador.current) clearTimeout(temporizador.current);
    },
    [],
  );

  const set = useCallback(
    <K extends keyof Automatizaciones>(clave: K, valor: Automatizaciones[K]) => {
      setCfg((prev) => (prev ? { ...prev, [clave]: valor } : prev));
    },
    [],
  );

  return <Ctx.Provider value={{ cfg, set, estado, actividad }}>{children}</Ctx.Provider>;
}

export function useCampanas(): Contexto {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCampanas fuera de ProveedorCampanas");
  return c;
}

export const CLAVES: (keyof Automatizaciones)[] = [
  "recordatorio_24h",
  "recordatorio_2h",
  "cumple",
  "inactivos",
  "resena_google",
];

/** «Guardando… / Guardado / 2 de 5 prendidas», siempre en el mismo lugar. */
export function EstadoCampanas() {
  const { cfg, estado } = useCampanas();
  if (!cfg) return null;
  const prendidas = CLAVES.filter((k) => cfg[k].activa).length;
  return (
    <div className="flex h-6 shrink-0 items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
      {estado === "guardando" && (
        <>
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Guardando…
        </>
      )}
      {estado === "guardado" && (
        <>
          <Check className="h-3.5 w-3.5 text-emerald-600" /> Guardado
        </>
      )}
      {estado === "quieto" && <>{prendidas} de 5 prendidas</>}
    </div>
  );
}

export function fechaCorta(iso: string): string {
  return new Date(iso).toLocaleDateString("es-AR", { day: "numeric", month: "short" });
}

/** Lo que mandó la campaña en los últimos 30 días. Dato real, de la tabla Mensaje. */
export function LineaActividad({ tipo }: { tipo: keyof Automatizaciones }) {
  const { actividad } = useCampanas();
  const a = actividad?.campanas[tipo];
  if (!actividad || !a) return null;
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
      <span>
        {a.enviados === 0
          ? `Sin envíos en los últimos ${actividad.dias} días`
          : `${a.enviados} ${a.enviados === 1 ? "email enviado" : "emails enviados"} en ${actividad.dias} días`}
        {a.ultimo && ` · último el ${fechaCorta(a.ultimo)}`}
      </span>
      {a.fallidos > 0 && (
        <span className="inline-flex items-center gap-1 font-semibold text-amber-800 dark:text-amber-300">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
          {a.fallidos} sin poder enviar
        </span>
      )}
    </p>
  );
}

/** "3 horas antes" / "1 hora antes" / "2 días antes" — sin "48 horas antes". */
export function textoAnticipacion(horas: number): string {
  if (horas >= 24 && horas % 24 === 0) {
    const d = horas / 24;
    return d === 1 ? "1 día antes" : `${d} días antes`;
  }
  return horas === 1 ? "1 hora antes" : `${horas} horas antes`;
}

export function Grupo({
  titulo,
  porQue,
  tono,
  children,
}: {
  titulo: string;
  porQue: string;
  tono: string;
  children: React.ReactNode;
}) {
  return (
    <section className="aparece">
      <div className="mb-3">
        <h2
          className="text-xs font-bold uppercase tracking-[0.14em]"
          style={{ color: `hsl(${tono})` }}
        >
          {titulo}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{porQue}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function Tarjeta({
  Icono,
  tono,
  titulo,
  descripcion,
  activa,
  onSwitch,
  tipo,
  children,
}: {
  Icono: typeof Bell;
  tono: string;
  titulo: string;
  descripcion: string;
  activa: boolean;
  onSwitch: (v: boolean) => void;
  tipo: string;
  children?: React.ReactNode;
}) {
  const [probando, setProbando] = useState(false);

  async function probar() {
    setProbando(true);
    try {
      // El destino ya no se pregunta: va al email del usuario que la pide, y
      // lo decide el backend. Cuando era un campo libre, con una cuenta de
      // prueba se podía mandar cualquier contenido a cualquier casilla desde
      // el remitente oficial de Turnos360.
      const r = await probarCampana(tipo);
      toast.success(r.detalle);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo enviar la prueba");
    } finally {
      setProbando(false);
    }
  }

  return (
    <div
      className={`tarjeta overflow-hidden transition-shadow ${
        activa ? "shadow-[var(--sombra-tarjeta)]" : "shadow-none"
      }`}
      style={{ "--tono": tono } as React.CSSProperties}
    >
      <div className="flex items-start gap-4 p-5">
        <span className="cajita">
          <Icono className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{titulo}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{descripcion}</p>
          <div className="mt-1.5">
            <LineaActividad tipo={tipo as keyof Automatizaciones} />
          </div>
        </div>
        <Switch
          checked={activa}
          onCheckedChange={onSwitch}
          aria-label={`${activa ? "Apagar" : "Prender"} ${titulo}`}
        />
      </div>

      {activa && (
        <div className="space-y-4 border-t bg-muted/25 px-5 py-4">
          {children}
          <button
            type="button"
            onClick={probar}
            disabled={probando}
            className="enlace inline-flex items-center gap-1.5 text-xs disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            {probando ? "Enviando…" : "Enviarme una prueba"}
          </button>
        </div>
      )}
    </div>
  );
}

/** Fila de píldoras para elegir un valor de una lista corta. */
export function Opciones({
  etiqueta,
  ayuda,
  valor,
  opciones,
  onElegir,
  texto,
}: {
  etiqueta: string;
  ayuda?: string;
  valor: number;
  opciones: number[];
  onElegir: (v: number) => void;
  texto: (v: number) => string;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">{etiqueta}</Label>
      <div className="flex flex-wrap gap-1.5">
        {opciones.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => onElegir(o)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              o === valor
                ? "border-transparent bg-primary text-primary-foreground"
                : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {texto(o)}
          </button>
        ))}
      </div>
      {ayuda && <p className="text-xs text-muted-foreground">{ayuda}</p>}
    </div>
  );
}

/** El campo de asunto, igual en cumpleaños y en inactivos. */
export function CampoAsunto({
  valor,
  onCambio,
  placeholder,
}: {
  valor: string;
  onCambio: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">
        Asunto del email{" "}
        <span className="font-normal">(vacío = el nuestro)</span>
      </Label>
      <Input value={valor} maxLength={120} placeholder={placeholder} onChange={(e) => onCambio(e.target.value)} />
      <p className="text-xs text-muted-foreground">
        Es lo único que ve tu cliente en la bandeja antes de decidir si abre.
      </p>
    </div>
  );
}

export function CargandoCampanas() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="tarjeta h-[88px] animate-pulse" />
      ))}
    </div>
  );
}

/** Ley 25.326: lo promocional solo va a quien aceptó recibirlo. */
export function AvisoPromos() {
  const { actividad } = useCampanas();
  const a = actividad?.alcance;
  return (
    <div className="rounded-xl border border-amber-300/60 bg-amber-50 p-3.5 text-xs leading-relaxed text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
      <b>Cumpleaños</b> y <b>recuperar inactivos</b> son promocionales: solo le llegan a quien aceptó
      recibir promociones (el tilde que aparece al reservar).
      {a && (
        <>
          {" "}Hoy son <b>{a.aceptan_promos}</b> de tus {a.clientes} clientes
          {a.aceptan_promos > 0 && <>, y {a.con_cumple} tienen la fecha de cumpleaños cargada</>}.
        </>
      )}
    </div>
  );
}
