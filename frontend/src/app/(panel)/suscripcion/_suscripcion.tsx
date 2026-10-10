"use client";

/**
 * Lo que comparten las seis pantallas del circuito de suscripción.
 *
 * POR QUÉ EXISTE ESTE ARCHIVO
 * ───────────────────────────
 * El circuito pasó de ser UNA pantalla de 33 KB a seis rutas, una por paso.
 * Sin un lugar común, cada paso terminaría con su propia copia de `pesos()`,
 * de los datos de cobro y del pedido a la API — y el día que cambie el formato
 * del monto habría que acordarse de tocar seis archivos.
 *
 * Acá vive lo que TODOS los pasos necesitan y nada más: el formato de plata y
 * fechas, el hook que trae la suscripción, el encabezado con el indicador de
 * paso, y la fila copiable del CBU.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format, parseISO, isValid } from "date-fns";
import { es } from "date-fns/locale";
import { toast } from "sonner";
import { ArrowLeft, Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  leerAvisoPago,
  leerMiSuscripcion,
  type MiSuscripcion,
  type PlanDeLaGrilla,
  type TonoEstado,
} from "@/lib/empresa-api";

export const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

/** Los seis pasos, en orden. El índice es lo que se le pasa a <Pasos>. */
export const PASOS = [
  "Plan",
  "Resumen",
  "Pago",
  "Transferencia",
  "Comprobante",
  "Listo",
] as const;

export function pesos(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toLocaleString("es-AR")}`;
}

/** "2026-08-05" -> "5 de agosto de 2026". Nunca formatea una fecha inválida. */
export function fechaLarga(iso: string | null): string {
  if (!iso) return "—";
  const d = parseISO(iso);
  return isValid(d) ? format(d, "d 'de' MMMM 'de' yyyy", { locale: es }) : "—";
}

/** Fecha y hora de un evento (ISO con zona) en hora local. */
export function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  const d = parseISO(iso);
  return isValid(d) ? format(d, "d MMM yyyy, HH:mm", { locale: es }) : "—";
}

export function fechaCorta(iso: string | null): string {
  if (!iso) return "—";
  const d = parseISO(iso);
  return isValid(d) ? format(d, "d MMM yyyy", { locale: es }) : "—";
}

type Estilo = { fondo: string; borde: string; texto: string; punto: string };

/**
 * Colores por TONO, no por estado. El tono lo decide el servidor
 * (core/estados_suscripcion.py) junto con la etiqueta: la pantalla no vuelve
 * a interpretar qué significa cada estado, solo lo pinta.
 */
export const ESTILO_TONO: Record<TonoEstado, Estilo> = {
  ok: {
    fondo: "bg-emerald-500/10",
    borde: "border-emerald-500/30",
    texto: "text-emerald-700 dark:text-emerald-400",
    punto: "bg-emerald-500",
  },
  info: {
    fondo: "bg-sky-500/10",
    borde: "border-sky-500/30",
    texto: "text-sky-700 dark:text-sky-400",
    punto: "bg-sky-500",
  },
  aviso: {
    fondo: "bg-amber-500/10",
    borde: "border-amber-500/30",
    texto: "text-amber-700 dark:text-amber-400",
    punto: "bg-amber-500",
  },
  error: {
    fondo: "bg-red-500/10",
    borde: "border-red-500/30",
    texto: "text-red-700 dark:text-red-400",
    punto: "bg-red-500",
  },
  neutro: {
    fondo: "bg-muted",
    borde: "border-border",
    texto: "text-muted-foreground",
    punto: "bg-muted-foreground",
  },
};

export function estiloDe(tono: TonoEstado | string | null | undefined): Estilo {
  return ESTILO_TONO[(tono as TonoEstado) ?? "neutro"] ?? ESTILO_TONO.neutro;
}

/** Badge del estado, con la etiqueta que manda el servidor. */
export function BadgeEstado({
  etiqueta,
  tono,
}: {
  etiqueta: string;
  tono: TonoEstado | string;
}) {
  const e = estiloDe(tono);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${e.fondo} ${e.borde} ${e.texto}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${e.punto}`} />
      {etiqueta}
    </span>
  );
}

/**
 * Cuánto se paga por `destino`: el precio pactado si lo hay, si no el del
 * plan. Es la MISMA regla que `mp_suscripcion.precio_de` en el servidor, que
 * es el que igual decide lo que se espera cobrar.
 */
export function montoDe(datos: MiSuscripcion, destino?: PlanDeLaGrilla): number | null {
  if (datos.precio_pactado) return datos.cuota;
  return destino?.precio ?? datos.cuota;
}

/**
 * Trae la suscripción y el aviso de pago pendiente.
 *
 * Cada paso la pide por su cuenta en vez de arrastrarla por la URL o por un
 * contexto: son datos de plata y se leen del servidor en cada pantalla, así
 * nadie decide sobre una foto vieja. Si alguien entra directo al paso 4 por el
 * historial del navegador, llega con los datos frescos igual.
 */
function useSuscripcionPropia(activo: boolean) {
  const [datos, setDatos] = useState<MiSuscripcion | null>(null);
  const [avisoPendiente, setAvisoPendiente] = useState(false);
  // El aviso puede estar esperando que lo revisemos ("pendiente") o esperando
  // un dato del negocio ("info_solicitada"). Solo en el primer caso no tiene
  // sentido volver a avisar.
  const [avisoEstado, setAvisoEstado] = useState<string | null>(null);
  const [mensajeAdmin, setMensajeAdmin] = useState<string | null>(null);
  const [cargando, setCargando] = useState(activo);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [sus, aviso] = await Promise.all([
        leerMiSuscripcion(),
        leerAvisoPago().catch(
          () => ({ pendiente: false }) as Awaited<ReturnType<typeof leerAvisoPago>>,
        ),
      ]);
      setDatos(sus);
      setAvisoPendiente(Boolean(aviso.pendiente) && aviso.estado !== "info_solicitada");
      setAvisoEstado(aviso.pendiente ? (aviso.estado ?? "pendiente") : null);
      setMensajeAdmin(aviso.mensaje_admin ?? null);
    } catch {
      toast.error("No se pudo cargar tu suscripción");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    if (activo) cargar();
  }, [activo, cargar]);

  return {
    datos,
    avisoPendiente,
    avisoEstado,
    mensajeAdmin,
    setAvisoPendiente,
    cargando,
    cargar,
  };
}

type EstadoSuscripcionPantalla = ReturnType<typeof useSuscripcionPropia>;

const CtxSuscripcion = createContext<EstadoSuscripcionPantalla | null>(null);

/**
 * Las pestañas de «Mi suscripción» (resumen, planes, pagos…) comparten UNA
 * lectura: pasar de una a otra no vuelve a pedir nada. El circuito de pago
 * (./cambiar/*) queda afuera a propósito y lee fresco en cada paso.
 */
export function ProveedorSuscripcion({ children }: { children: React.ReactNode }) {
  const valor = useSuscripcionPropia(true);
  return <CtxSuscripcion.Provider value={valor}>{children}</CtxSuscripcion.Provider>;
}

export function useSuscripcion(): EstadoSuscripcionPantalla {
  const ctx = useContext(CtxSuscripcion);
  const propio = useSuscripcionPropia(ctx === null);
  return ctx ?? propio;
}

/**
 * El plan que se está comprando, sacado del `?plan=` de la URL.
 *
 * El paso viaja en la URL y no en un estado de React a propósito: así el botón
 * "atrás" del navegador funciona, un F5 no vuelve al principio, y el que deja
 * el checkout a la mitad y vuelve al link cae donde estaba. Un contexto en
 * memoria se pierde con cualquiera de las tres cosas.
 */
export function planDeLaUrl(
  datos: MiSuscripcion | null,
  codigo: string | null,
): PlanDeLaGrilla | undefined {
  if (!datos || !codigo) return undefined;
  return datos.grilla.find((p) => p.codigo === codigo);
}

/** El precio del plan que la empresa tiene hoy. 0 si no está en la grilla. */
export function miPrecioActual(datos: MiSuscripcion): number {
  return datos.grilla.find((p) => p.codigo === datos.plan_codigo)?.precio ?? 0;
}

/** Indicador de en qué paso está, arriba de cada pantalla del circuito. */
export function Pasos({ actual }: { actual: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      {PASOS.map((nombre, i) => {
        const hecho = i < actual;
        const esteEs = i === actual;
        return (
          <li key={nombre} className="flex items-center gap-2">
            <span
              className={
                esteEs
                  ? "font-semibold text-foreground"
                  : hecho
                    ? "text-muted-foreground"
                    : "text-muted-foreground/50"
              }
            >
              {hecho ? "✓ " : `${i + 1}. `}
              {nombre}
            </span>
            {i < PASOS.length - 1 && (
              <span className="text-muted-foreground/30">·</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/**
 * El marco de cada paso: volver, título y el indicador.
 *
 * "Volver" es un `router.back()` y no un link fijo: desde el paso 4 se puede
 * haber llegado por el paso 3 o directo desde el aviso de vencimiento, y
 * mandarlo siempre al mismo lado lo sacaría del camino por el que vino.
 */
export function PasoLayout({
  paso,
  titulo,
  bajada,
  children,
}: {
  paso: number;
  titulo: string;
  bajada?: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 md:p-6">
      <header className="space-y-3">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2 h-8 gap-1.5 px-2 text-muted-foreground"
          onClick={() => router.back()}
        >
          <ArrowLeft className="h-4 w-4" />
          Volver
        </Button>
        <Pasos actual={paso} />
        <div>
          <h1 className="text-2xl font-bold" style={SYNE}>
            {titulo}
          </h1>
          {bajada && (
            <p className="mt-1 text-sm text-muted-foreground">{bajada}</p>
          )}
        </div>
      </header>
      {children}
    </div>
  );
}

/** Fila copiable: en el celular, tipear un CBU de 22 dígitos es garantía de error. */
export function FilaCopiable({
  etiqueta,
  valor,
}: {
  etiqueta: string;
  valor: string;
}) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {etiqueta}
        </p>
        <p className="truncate text-sm font-medium tabular-nums">{valor}</p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="shrink-0"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(valor);
            setCopiado(true);
            setTimeout(() => setCopiado(false), 1600);
          } catch {
            toast.error("No se pudo copiar");
          }
        }}
      >
        {copiado ? (
          <Check className="h-4 w-4 text-emerald-600" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}

/** Pantalla de carga, igual en los seis pasos. */
export function Cargando() {
  return (
    <div className="mx-auto max-w-3xl p-4 md:p-6">
      <div className="h-40 animate-pulse rounded-2xl bg-muted" />
    </div>
  );
}
