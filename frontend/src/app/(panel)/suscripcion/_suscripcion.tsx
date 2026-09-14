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

import { useCallback, useEffect, useState } from "react";
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

export function fechaCorta(iso: string | null): string {
  if (!iso) return "—";
  const d = parseISO(iso);
  return isValid(d) ? format(d, "d MMM yyyy", { locale: es }) : "—";
}

/** Colores del cartel de estado. */
export const ESTILO_ESTADO: Record<
  string,
  { fondo: string; borde: string; texto: string }
> = {
  activa: {
    fondo: "bg-emerald-500/10",
    borde: "border-emerald-500/30",
    texto: "text-emerald-700 dark:text-emerald-400",
  },
  prorroga: {
    fondo: "bg-amber-500/10",
    borde: "border-amber-500/30",
    texto: "text-amber-700 dark:text-amber-400",
  },
  vencida: {
    fondo: "bg-red-500/10",
    borde: "border-red-500/30",
    texto: "text-red-700 dark:text-red-400",
  },
  sin_vencimiento: {
    fondo: "bg-muted",
    borde: "border-border",
    texto: "text-muted-foreground",
  },
  prueba: {
    fondo: "bg-sky-500/10",
    borde: "border-sky-500/30",
    texto: "text-sky-700 dark:text-sky-400",
  },
};

/**
 * Trae la suscripción y el aviso de pago pendiente.
 *
 * Cada paso la pide por su cuenta en vez de arrastrarla por la URL o por un
 * contexto: son datos de plata y se leen del servidor en cada pantalla, así
 * nadie decide sobre una foto vieja. Si alguien entra directo al paso 4 por el
 * historial del navegador, llega con los datos frescos igual.
 */
export function useSuscripcion() {
  const [datos, setDatos] = useState<MiSuscripcion | null>(null);
  const [avisoPendiente, setAvisoPendiente] = useState(false);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [sus, aviso] = await Promise.all([
        leerMiSuscripcion(),
        leerAvisoPago().catch(() => ({ pendiente: false })),
      ]);
      setDatos(sus);
      setAvisoPendiente(Boolean(aviso.pendiente));
    } catch {
      toast.error("No se pudo cargar tu suscripción");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return { datos, avisoPendiente, setAvisoPendiente, cargando, cargar };
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
