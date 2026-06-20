"use client";

/**
 * Inicio del panel (/): dashboard del negocio.
 *
 * Filtros (período + barbero) que alimentan todo:
 *   - KPIs del período (turnos, confirmados, ingresos, ausencias).
 *   - Gráficos: tortas (estado, canal de adquisición) y barras (servicios, barberos).
 *   - Próximos turnos, resumen de abonos y accesos rápidos.
 * Período: hoy / esta semana / este mes (calendario) / personalizado (rango libre).
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  format,
  parseISO,
} from "date-fns";
import { es } from "date-fns/locale";
import {
  Calendar,
  CheckCircle2,
  Banknote,
  UserX,
  Plus,
  Users,
  Scissors,
  Crown,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { listarTurnosDelDia, Turno } from "@/lib/turnos-api";
import { listarClientes, Cliente } from "@/lib/clientes-api";
import {
  estadisticasMembresias,
  EstadisticasMembresias,
} from "@/lib/membresias-api";
import { colorEstadoHex, labelEstado, horaDe } from "@/lib/turno-visual";
import { Torta } from "@/components/graficos/torta";
import { Barras } from "@/components/graficos/barras";
import { ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Periodo = "hoy" | "semana" | "mes" | "personalizado";

const PERIODO_LABEL: Record<Exclude<Periodo, "personalizado">, string> = {
  hoy: "hoy",
  semana: "esta semana",
  mes: "este mes",
};

/** Orden fijo de estados para la torta (los vacíos se filtran después). */
const ESTADOS_ORDEN = [
  "pendiente",
  "confirmado",
  "en_curso",
  "finalizado",
  "cancelado",
  "ausente",
] as const;

/** Etiqueta + color por canal de adquisición. */
const CANAL_INFO: Record<string, { label: string; color: string }> = {
  instagram: { label: "Instagram", color: "#e1306c" },
  tiktok: { label: "TikTok", color: "#06b6d4" },
  referido: { label: "Referido", color: "#10b981" },
  google: { label: "Google", color: "#4285f4" },
  paso_por_la_puerta: { label: "Paso por la puerta", color: "#f59e0b" },
  otro: { label: "Otro", color: "#94a3b8" },
};

/** Rango [desde, hasta] según el período elegido. */
function rangoDe(
  periodo: Periodo,
  desdeCustom: string,
  hastaCustom: string,
): { desde: Date; hasta: Date } {
  const hoy = new Date();
  if (periodo === "semana") {
    return {
      desde: startOfWeek(hoy, { weekStartsOn: 1 }),
      hasta: endOfWeek(hoy, { weekStartsOn: 1 }),
    };
  }
  if (periodo === "mes") {
    return { desde: startOfMonth(hoy), hasta: endOfMonth(hoy) };
  }
  if (periodo === "personalizado") {
    return {
      desde: startOfDay(parseISO(desdeCustom)),
      hasta: endOfDay(parseISO(hastaCustom)),
    };
  }
  return { desde: startOfDay(hoy), hasta: endOfDay(hoy) };
}

export default function InicioPage() {
  const hoyStr = format(new Date(), "yyyy-MM-dd");

  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [estadisticas, setEstadisticas] =
    useState<EstadisticasMembresias | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [periodo, setPeriodo] = useState<Periodo>("hoy");
  const [desdeCustom, setDesdeCustom] = useState(hoyStr);
  const [hastaCustom, setHastaCustom] = useState(hoyStr);
  const [barberoId, setBarberoId] = useState<number | null>(null); // null = todos
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Barberos (para el filtro)
  useEffect(() => {
    listarRecursos()
      .then((data) =>
        setRecursos(data.items.filter((r) => r.tipo === "persona")),
      )
      .catch(() => setRecursos([]));
  }, []);

  // Clientes (para la torta de canal de adquisición; dato histórico del negocio)
  useEffect(() => {
    listarClientes(undefined, 0, 1000)
      .then((data) => setClientes(data.items))
      .catch(() => setClientes([]));
  }, []);

  // Estadísticas de abonos (resumen del negocio)
  useEffect(() => {
    estadisticasMembresias()
      .then(setEstadisticas)
      .catch(() => setEstadisticas(null));
  }, []);

  // Turnos del período elegido (todos los recursos; filtramos por barbero abajo)
  const cargar = useCallback(async () => {
    if (periodo === "personalizado" && (!desdeCustom || !hastaCustom)) return;
    setCargando(true);
    setError(null);
    try {
      const { desde, hasta } = rangoDe(periodo, desdeCustom, hastaCustom);
      const data = await listarTurnosDelDia(
        desde.toISOString(),
        hasta.toISOString(),
      );
      setTurnos(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [periodo, desdeCustom, hastaCustom]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Filtro por barbero (en el front)
  const visibles = useMemo(() => {
    if (barberoId === null) return turnos;
    return turnos.filter((t) => t.recurso_id === barberoId);
  }, [turnos, barberoId]);

  // --- KPIs del período ---
  const activos = visibles.filter(
    (t) => t.estado !== "cancelado" && t.estado !== "ausente",
  );
  const confirmados = visibles.filter((t) => t.estado === "confirmado").length;
  const ingresos = activos.reduce(
    (acc, t) => acc + (t.importe_previsto ? Number(t.importe_previsto) : 0),
    0,
  );
  const ausentes = visibles.filter((t) => t.estado === "ausente").length;
  const noCancelados = visibles.filter((t) => t.estado !== "cancelado").length;
  const tasaAusencias =
    noCancelados > 0 ? Math.round((ausentes / noCancelados) * 100) : 0;

  const kpis = [
    {
      label: "Turnos",
      valor: String(activos.length),
      icon: Calendar,
      color: "#00d4aa",
    },
    {
      label: "Confirmados",
      valor: String(confirmados),
      icon: CheckCircle2,
      color: "#3b82f6",
    },
    {
      label: "Ingresos previstos",
      valor: `$${ingresos.toLocaleString("es-AR")}`,
      icon: Banknote,
      color: "#10b981",
    },
    {
      label: "Ausencias",
      valor: `${tasaAusencias}%`,
      icon: UserX,
      color: "#ef4444",
    },
  ];

  // --- Segmentos para las tortas ---
  // Turnos por estado (reacciona al período/barbero)
  const segmentosEstado = ESTADOS_ORDEN.map((e) => ({
    label: labelEstado(e),
    valor: visibles.filter((t) => t.estado === e).length,
    color: colorEstadoHex(e),
  })).filter((s) => s.valor > 0);

  // Canal de adquisición (histórico: todos los clientes del negocio)
  const conteoCanal: Record<string, number> = {};
  for (const c of clientes) {
    const key = c.canal_adquisicion ?? "sin";
    conteoCanal[key] = (conteoCanal[key] ?? 0) + 1;
  }
  const segmentosCanal = Object.entries(conteoCanal)
    .map(([key, valor]) => ({
      label: CANAL_INFO[key]?.label ?? "Sin especificar",
      valor,
      color: CANAL_INFO[key]?.color ?? "#cbd5e1",
    }))
    .sort((a, b) => b.valor - a.valor);

  // --- Rankings para las barras (sin contar cancelados) ---
  // Servicios más pedidos (respeta el filtro de barbero)
  const conteoServicio: Record<string, number> = {};
  for (const t of visibles) {
    if (t.estado === "cancelado") continue;
    const nombre = t.servicio_nombre ?? "Sin servicio";
    conteoServicio[nombre] = (conteoServicio[nombre] ?? 0) + 1;
  }
  const rankingServicios = Object.entries(conteoServicio)
    .map(([label, valor]) => ({ label, valor }))
    .sort((a, b) => b.valor - a.valor)
    .slice(0, 6);

  // Turnos por barbero (siempre compara todos, ignora el filtro de barbero)
  const conteoBarbero: Record<number, number> = {};
  for (const t of turnos) {
    if (t.estado === "cancelado") continue;
    conteoBarbero[t.recurso_id] = (conteoBarbero[t.recurso_id] ?? 0) + 1;
  }
  const rankingBarberos = Object.entries(conteoBarbero)
    .map(([id, valor]) => ({
      label: recursos.find((r) => r.id === Number(id))?.nombre ?? `#${id}`,
      valor,
    }))
    .sort((a, b) => b.valor - a.valor);

  // --- Datos de la capa 3 ---
  // Próximos turnos (de ahora en adelante, dentro del período/barbero)
  const ahora = new Date();
  const proximos = visibles
    .filter(
      (t) =>
        t.fecha_inicio &&
        new Date(t.fecha_inicio) >= ahora &&
        t.estado !== "cancelado",
    )
    .sort(
      (a, b) =>
        new Date(a.fecha_inicio!).getTime() -
        new Date(b.fecha_inicio!).getTime(),
    )
    .slice(0, 5);

  const nombreBarbero = (id: number) =>
    recursos.find((r) => r.id === id)?.nombre ?? "—";

  // Abonados por plan (para las barras del resumen de abonos)
  const barrasAbonos =
    estadisticas?.planes.map((p) => ({
      label: p.nombre,
      valor: p.abonados_activos,
    })) ?? [];

  // Subtítulo según el período
  const subtitulo =
    periodo === "personalizado"
      ? `Resumen del ${format(parseISO(desdeCustom), "d MMM", { locale: es })} al ${format(parseISO(hastaCustom), "d MMM", { locale: es })}`
      : `Resumen de ${PERIODO_LABEL[periodo]}`;

  return (
    <div className="p-8">
      {/* Cabecera + filtros */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Inicio</h1>
          <p className="text-sm text-muted-foreground">
            {subtitulo}
            {cargando && " · cargando…"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={periodo}
            onValueChange={(v) => setPeriodo(v as Periodo)}
          >
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hoy">Hoy</SelectItem>
              <SelectItem value="semana">Esta semana</SelectItem>
              <SelectItem value="mes">Este mes</SelectItem>
              <SelectItem value="personalizado">Personalizado</SelectItem>
            </SelectContent>
          </Select>

          {periodo === "personalizado" && (
            <>
              <Input
                type="date"
                value={desdeCustom}
                max={hastaCustom}
                onChange={(e) => setDesdeCustom(e.target.value)}
                className="w-40 tabular-nums"
              />
              <span className="text-muted-foreground">a</span>
              <Input
                type="date"
                value={hastaCustom}
                min={desdeCustom}
                onChange={(e) => setHastaCustom(e.target.value)}
                className="w-40 tabular-nums"
              />
            </>
          )}

          <Select
            value={barberoId === null ? "todos" : String(barberoId)}
            onValueChange={(v) =>
              setBarberoId(v === "todos" ? null : Number(v))
            }
          >
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Todos los barberos</SelectItem>
              {recursos.map((r) => (
                <SelectItem key={r.id} value={String(r.id)}>
                  {r.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* KPIs del período */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis.map((k) => {
          const Icono = k.icon;
          return (
            <div
              key={k.label}
              className="rounded-2xl border bg-card p-5 transition-shadow hover:shadow-sm"
            >
              <div
                className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl"
                style={{
                  background: `${k.color}18`,
                  border: `1px solid ${k.color}30`,
                }}
              >
                <Icono size={18} style={{ color: k.color }} />
              </div>
              <p
                className="mb-1 text-2xl font-bold tabular-nums"
                style={{
                  fontFamily: "Syne, sans-serif",
                  fontVariantNumeric: "lining-nums tabular-nums",
                }}
              >
                {k.valor}
              </p>
              <p className="text-sm font-medium text-muted-foreground">
                {k.label}
              </p>
            </div>
          );
        })}
      </div>

      {/* Gráficos */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Turnos por estado (del período/barbero) */}
        <div className="rounded-2xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold">Turnos por estado</h3>
          {visibles.length > 0 ? (
            <Torta datos={segmentosEstado} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Sin turnos en este período.
            </p>
          )}
        </div>

        {/* Canal de adquisición (histórico) */}
        <div className="rounded-2xl border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Cómo nos conocieron</h3>
            <span className="text-xs text-muted-foreground">histórico</span>
          </div>
          {clientes.length > 0 ? (
            <Torta datos={segmentosCanal} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Todavía no hay clientes cargados.
            </p>
          )}
        </div>
      </div>

      {/* Rankings (barras) */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Servicios más pedidos */}
        <div className="rounded-2xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold">Servicios más pedidos</h3>
          {rankingServicios.length > 0 ? (
            <Barras datos={rankingServicios} color="#00d4aa" />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Sin datos en este período.
            </p>
          )}
        </div>

        {/* Turnos por barbero */}
        <div className="rounded-2xl border bg-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Turnos por barbero</h3>
            <span className="text-xs text-muted-foreground">todos</span>
          </div>
          {rankingBarberos.length > 0 ? (
            <Barras datos={rankingBarberos} color="#3b82f6" />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Sin datos en este período.
            </p>
          )}
        </div>
      </div>

      {/* Próximos turnos + Resumen de abonos */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Próximos turnos */}
        <div className="rounded-2xl border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold">Próximos turnos</h3>
          {proximos.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {proximos.map((t) => {
                const color = colorEstadoHex(t.estado);
                return (
                  <Link
                    key={t.id}
                    href="/agenda"
                    className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-muted/50"
                  >
                    <span
                      className="w-12 shrink-0 text-sm font-bold tabular-nums"
                      style={{ fontFamily: "Syne, sans-serif" }}
                    >
                      {t.fecha_inicio && horaDe(t.fecha_inicio)}
                    </span>
                    <div className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-sm font-medium">
                        {t.cliente_nombre}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {t.servicio_nombre ?? "Sin servicio"}
                        {barberoId === null &&
                          ` · ${nombreBarbero(t.recurso_id)}`}
                      </span>
                    </div>
                    <span
                      className="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{ backgroundColor: `${color}22`, color }}
                    >
                      {labelEstado(t.estado)}
                    </span>
                  </Link>
                );
              })}
            </ul>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No hay turnos próximos.
            </p>
          )}
        </div>

        {/* Resumen de abonos */}
        <div className="rounded-2xl border bg-card p-5">
          <div className="mb-4 flex items-center gap-2">
            <Crown size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold">Abonos</h3>
          </div>
          {estadisticas ? (
            <>
              <div className="mb-4 grid grid-cols-3 gap-2">
                <div>
                  <p
                    className="text-xl font-bold tabular-nums"
                    style={{ fontFamily: "Syne, sans-serif" }}
                  >
                    {estadisticas.resumen.total_abonados}
                  </p>
                  <p className="text-xs text-muted-foreground">PRO activos</p>
                </div>
                <div>
                  <p
                    className="text-xl font-bold tabular-nums"
                    style={{ fontFamily: "Syne, sans-serif" }}
                  >
                    ${estadisticas.resumen.total_ingreso.toLocaleString("es-AR")}
                  </p>
                  <p className="text-xs text-muted-foreground">Ingresos</p>
                </div>
                <div>
                  <p
                    className="text-xl font-bold tabular-nums"
                    style={{ fontFamily: "Syne, sans-serif" }}
                  >
                    {estadisticas.resumen.total_cortes}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Cortes cubiertos
                  </p>
                </div>
              </div>
              {barrasAbonos.length > 0 ? (
                <Barras datos={barrasAbonos} color="#f59e0b" />
              ) : (
                <p className="text-center text-sm text-muted-foreground">
                  Todavía no hay planes de abono.
                </p>
              )}
            </>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Sin datos de abonos.
            </p>
          )}
        </div>
      </div>

      {/* Accesos rápidos */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Nuevo turno", href: "/agenda", icon: Plus },
          { label: "Clientes", href: "/clientes", icon: Users },
          { label: "Membresías", href: "/membresias", icon: Crown },
          { label: "Servicios", href: "/servicios", icon: Scissors },
        ].map((a) => {
          const Icono = a.icon;
          return (
            <Link
              key={a.href}
              href={a.href}
              className="group flex items-center gap-3 rounded-2xl border bg-card p-4 transition-colors hover:border-primary/40 hover:bg-primary/5"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icono size={18} />
              </div>
              <span className="flex-1 text-sm font-medium">{a.label}</span>
              <ArrowRight
                size={16}
                className="text-muted-foreground transition-transform group-hover:translate-x-0.5"
              />
            </Link>
          );
        })}
      </div>
    </div>
  );
}