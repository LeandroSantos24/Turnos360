"use client";

/**
 * Wizard de reserva online (landing pública). 4 pasos:
 *   1) servicio → 2) profesional (o "cualquiera") → 3) fecha y hora → 4) datos.
 * Usa la API pública existente (obtenerHuecos + reservar). El turno queda
 * PENDIENTE y aparece al instante en la agenda del negocio.
 *
 * Horas: el backend trabaja con "hora local etiquetada UTC" (patrón del
 * proyecto), por eso acá se lee siempre con getUTC* (helper horaDe) y el
 * string ISO elegido se manda tal cual, sin re-parsear.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Clock,
  User,
  Users,
  CalendarDays,
  MessageCircle,
  CalendarPlus,
  Loader2,
  AlertCircle,
} from "lucide-react";

import {
  obtenerHuecos,
  reservar,
  type Vidriera,
  type HuecosDia,
  type ReservaResultado,
  validarCupon,
} from "@/lib/publico-api";
import { ApiError } from "@/lib/api";
import { horaDe } from "@/lib/turno-visual";
import { BORDE, SUPERFICIE, TINTA, TINTA_SUAVE, hexA, precioFmt, linkWhatsApp } from "./vidriera-ui";

type Paso = 1 | 2 | 3 | 4 | 5;

/** "YYYY-MM-DD" → Date local sin corrimiento de zona horaria. */
function fechaLocal(iso: string): Date {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

/** Datetime "etiquetado UTC" → texto legible ("viernes 10 de julio · 15:30"). */
function linkGoogleCalendar(
  resultado: { inicio: string; servicio: string },
  v: { nombre: string; direccion?: string | null; servicios: { nombre: string; duracion_min: number }[] },
): string {
  // OJO con las zonas horarias: el sistema guarda la hora DE PARED marcada como
  // UTC ("…T09:00:00Z" = las 9 del reloj del local). Si le mandamos esa Z a
  // Google, Google la toma como UTC real y la convierte a -03 → agenda a las 6.
  // Solución: mandar la hora SIN Z (Google la lee como local) y declarar la
  // zona con ctz. Usamos getUTC* para leer los dígitos tal cual los guardamos.
  const inicio = new Date(resultado.inicio);
  const serv = v.servicios.find((s) => s.nombre === resultado.servicio);
  const fin = new Date(inicio.getTime() + (serv?.duracion_min ?? 30) * 60000);
  const fmt = (d: Date) => d.toISOString().slice(0, 19).replace(/[-:]/g, "");
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: `${resultado.servicio} · ${v.nombre}`,
    dates: `${fmt(inicio)}/${fmt(fin)}`,
    ctz: "America/Argentina/Buenos_Aires",
    location: v.direccion ?? v.nombre,
    details: "Reservado online con Turnos360",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function fechaHoraLegible(iso: string): string {
  const d = new Date(iso);
  const local = new Date(
    d.getUTCFullYear(),
    d.getUTCMonth(),
    d.getUTCDate(),
    d.getUTCHours(),
    d.getUTCMinutes(),
  );
  return format(local, "EEEE d 'de' MMMM · HH:mm", { locale: es });
}

function etiquetaDia(iso: string): { arriba: string; abajo: string } {
  const hoy = format(new Date(), "yyyy-MM-dd");
  const man = format(new Date(Date.now() + 86400000), "yyyy-MM-dd");
  const d = fechaLocal(iso);
  if (iso === hoy) return { arriba: "Hoy", abajo: format(d, "d MMM", { locale: es }) };
  if (iso === man) return { arriba: "Mañana", abajo: format(d, "d MMM", { locale: es }) };
  return {
    arriba: format(d, "EEE", { locale: es }),
    abajo: format(d, "d MMM", { locale: es }),
  };
}

const TITULOS: Record<Paso, string> = {
  1: "Elegí el servicio",
  2: "¿Con quién?",
  3: "Elegí día y hora",
  4: "Tus datos",
  5: "¡Turno reservado!",
};

export function ReservaWizard({
  v,
  slug,
  acento,
  abierto,
  servicioInicial,
  onCerrar,
}: {
  v: Vidriera;
  slug: string;
  acento: string;
  abierto: boolean;
  servicioInicial: number | null;
  onCerrar: () => void;
}) {
  const [paso, setPaso] = useState<Paso>(1);
  const [servicioId, setServicioId] = useState<number | null>(null);
  const [recursoId, setRecursoId] = useState<number | null>(null); // null = cualquiera
  const [huecos, setHuecos] = useState<HuecosDia[] | null>(null);
  const [cargandoHuecos, setCargandoHuecos] = useState(false);
  const [diaSel, setDiaSel] = useState<string | null>(null);
  const [horaSel, setHoraSel] = useState<string | null>(null);
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [aceptaMkt, setAceptaMkt] = useState(false);
  // Cupón de descuento
  const [mostrarCupon, setMostrarCupon] = useState(false);
  const [codigoCupon, setCodigoCupon] = useState("");
  const [cuponAplicado, setCuponAplicado] = useState<{
    codigo: string;
    descuento: number;
    precio_final: number | null;
  } | null>(null);
  const [errorCupon, setErrorCupon] = useState("");
  const [validandoCupon, setValidandoCupon] = useState(false);

  useEffect(() => {
    // Si cambia el servicio, el cupón se recalcula (aplica a otro precio o
    // directamente no cubre el servicio nuevo).
    setCuponAplicado(null);
    setErrorCupon("");
  }, [servicioId]);

  async function aplicarCupon() {
    if (!codigoCupon.trim() || servicioId == null) return;
    setValidandoCupon(true);
    setErrorCupon("");
    try {
      const r = await validarCupon(slug, codigoCupon.trim(), servicioId);
      if (r.valido) {
        setCuponAplicado({
          codigo: codigoCupon.trim().toUpperCase(),
          descuento: r.descuento,
          precio_final: r.precio_final,
        });
      } else {
        setCuponAplicado(null);
        setErrorCupon(r.mensaje);
      }
    } catch {
      setErrorCupon("No se pudo validar el código. Probá de nuevo.");
    } finally {
      setValidandoCupon(false);
    }
  }
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ReservaResultado | null>(null);

  const servicio = useMemo(
    () => v.servicios.find((s) => s.id === servicioId) ?? null,
    [v.servicios, servicioId],
  );
  const recurso = useMemo(
    () => v.recursos.find((r) => r.id === recursoId) ?? null,
    [v.recursos, recursoId],
  );

  /* Al abrir: resetear y, si vino un servicio preseleccionado, saltar al paso 2. */
  useEffect(() => {
    if (!abierto) return;
    setError(null);
    setResultado(null);
    setHoraSel(null);
    setDiaSel(null);
    setHuecos(null);
    if (servicioInicial != null && v.servicios.some((s) => s.id === servicioInicial)) {
      setServicioId(servicioInicial);
      setPaso(v.recursos.length > 0 ? 2 : 3);
    } else {
      setServicioId(null);
      setPaso(1);
    }
    setRecursoId(null);
  }, [abierto, servicioInicial, v.servicios, v.recursos.length]);

  /* Bloquear el scroll del fondo mientras el wizard está abierto. */
  useEffect(() => {
    if (!abierto) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [abierto]);

  /* Escape cierra (salvo mientras se envía). */
  useEffect(() => {
    if (!abierto) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !enviando) onCerrar();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [abierto, enviando, onCerrar]);

  /* Cargar huecos al entrar al paso 3 (o si cambia servicio/profesional). */
  const cargarHuecos = useCallback(() => {
    if (servicioId == null) return;
    setCargandoHuecos(true);
    setHuecos(null);
    setDiaSel(null);
    setHoraSel(null);
    obtenerHuecos(slug, servicioId, recursoId, 14)
      .then(setHuecos)
      .catch(() => setError("No pudimos cargar los horarios. Probá de nuevo."))
      .finally(() => setCargandoHuecos(false));
  }, [slug, servicioId, recursoId]);

  useEffect(() => {
    if (abierto && paso === 3) cargarHuecos();
  }, [abierto, paso, cargarHuecos]);

  /* Días con horas disponibles, filtrando las horas que ya pasaron hoy. */
  const dias = useMemo(() => {
    if (!huecos) return [];
    const hoy = format(new Date(), "yyyy-MM-dd");
    const ahora = format(new Date(), "HH:mm");
    return huecos
      .map((d) => ({
        ...d,
        horas: d.fecha === hoy ? d.horas.filter((h) => horaDe(h) > ahora) : d.horas,
      }))
      .filter((d) => d.horas.length > 0);
  }, [huecos]);

  useEffect(() => {
    if (dias.length > 0 && diaSel === null) setDiaSel(dias[0].fecha);
  }, [dias, diaSel]);

  const horasDelDia = useMemo(
    () => dias.find((d) => d.fecha === diaSel)?.horas ?? [],
    [dias, diaSel],
  );

  const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
  const puedeConfirmar =
    nombre.trim().length > 0 &&
    telefono.trim().length >= 5 &&
    emailOk &&
    horaSel != null &&
    !enviando;

  const confirmar = async () => {
    if (!puedeConfirmar || servicioId == null || horaSel == null) return;
    setEnviando(true);
    setError(null);
    try {
      const r = await reservar(slug, {
        servicio_id: servicioId,
        recurso_id: recursoId,
        inicio: horaSel,
        cliente: {
          nombre: nombre.trim(),
          telefono: telefono.trim(),
          email: email.trim(),
          acepta_marketing: aceptaMkt,
        },
        cupon_codigo: cuponAplicado?.codigo ?? null,
      });
      setResultado(r);
      setPaso(5);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Ese horario se acaba de ocupar. Elegí otro, por favor.");
        setPaso(3);
        cargarHuecos();
      } else if (e instanceof ApiError && e.status === 400) {
        // Motivo específico (ej: el cupón venció o se agotó entre validar y
        // confirmar). Se quita el cupón para que pueda reservar sin él.
        setError(e.message);
        setCuponAplicado(null);
      } else {
        setError("No pudimos crear la reserva. Probá de nuevo en unos segundos.");
      }
    } finally {
      setEnviando(false);
    }
  };

  const volver = () => {
    setError(null);
    if (paso === 4) setPaso(3);
    else if (paso === 3) setPaso(v.recursos.length > 0 ? 2 : 1);
    else if (paso === 2) setPaso(1);
  };

  const progreso = paso === 5 ? 100 : (paso / 4) * 100;
  const wa = linkWhatsApp(v);

  /* ---------- estilos base de fichas seleccionables ---------- */
  const ficha = (activa: boolean): React.CSSProperties => ({
    borderColor: activa ? acento : BORDE,
    background: activa ? hexA(acento, 0.07) : "#ffffff",
    boxShadow: activa ? `0 0 0 1px ${acento}` : "none",
  });

  return (
    <AnimatePresence>
      {abierto && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-end justify-center bg-[#0c1015]/55 backdrop-blur-sm sm:items-center sm:p-6"
          onClick={() => !enviando && onCerrar()}
          role="dialog"
          aria-modal="true"
          aria-label="Reservar turno"
        >
          <motion.div
            initial={{ y: 48, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 48, opacity: 0 }}
            transition={{ type: "spring", damping: 28, stiffness: 320 }}
            className="flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-3xl bg-white sm:max-w-lg sm:rounded-3xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Barra de progreso */}
            <div className="h-1 w-full" style={{ background: SUPERFICIE }}>
              <motion.div
                className="h-full"
                style={{ background: acento }}
                animate={{ width: `${progreso}%` }}
                transition={{ duration: 0.35 }}
              />
            </div>

            {/* Header */}
            <div className="flex items-center gap-2 px-5 pb-3 pt-4">
              {paso > 1 && paso < 5 && (
                <button
                  type="button"
                  onClick={volver}
                  aria-label="Volver"
                  className="flex h-9 w-9 items-center justify-center rounded-full transition-colors hover:bg-[#f6f7f9]"
                  style={{ color: TINTA }}
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
              )}
              <div className="min-w-0 flex-1">
                <h3
                  className="truncate text-lg font-bold"
                  style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
                >
                  {TITULOS[paso]}
                </h3>
                {paso < 5 && (
                  <p className="text-xs" style={{ color: TINTA_SUAVE }}>
                    Paso {paso} de 4
                    {servicio && paso > 1 ? ` · ${servicio.nombre}` : ""}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => !enviando && onCerrar()}
                aria-label="Cerrar"
                className="flex h-9 w-9 items-center justify-center rounded-full transition-colors hover:bg-[#f6f7f9]"
                style={{ color: TINTA_SUAVE }}
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Error inline */}
            {error && paso < 5 && (
              <div
                className="mx-5 mb-2 flex items-start gap-2 rounded-xl border px-3.5 py-2.5 text-sm"
                style={{ borderColor: "#fecaca", background: "#fef2f2", color: "#b91c1c" }}
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Contenido scrolleable */}
            <div className="flex-1 overflow-y-auto px-5 pb-5">
              {/* PASO 1 — Servicio */}
              {paso === 1 && (
                <div className="grid gap-2.5">
                  {v.servicios.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => {
                        setServicioId(s.id);
                        setPaso(v.recursos.length > 0 ? 2 : 3);
                      }}
                      className="flex items-center justify-between gap-3 rounded-2xl border p-4 text-left transition-all hover:shadow-sm"
                      style={ficha(servicioId === s.id)}
                    >
                      <div className="min-w-0">
                        <p className="truncate font-semibold" style={{ color: TINTA }}>
                          {s.nombre}
                        </p>
                        <p className="mt-0.5 flex items-center gap-1 text-xs" style={{ color: TINTA_SUAVE }}>
                          <Clock className="h-3 w-3" />
                          {s.duracion_min} min
                        </p>
                      </div>
                      {s.precio != null && (
                        <span
                          className="shrink-0 font-bold"
                          style={{ color: TINTA, fontVariantNumeric: "lining-nums tabular-nums" }}
                        >
                          {precioFmt(s.precio)}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}

              {/* PASO 2 — Profesional */}
              {paso === 2 && (
                <div className="grid gap-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      setRecursoId(null);
                      setPaso(3);
                    }}
                    className="flex items-center gap-3 rounded-2xl border p-4 text-left transition-all hover:shadow-sm"
                    style={ficha(false)}
                  >
                    <span
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full"
                      style={{ background: hexA(acento, 0.12), color: acento }}
                    >
                      <Users className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="font-semibold" style={{ color: TINTA }}>
                        Cualquiera disponible
                      </p>
                      <p className="text-xs" style={{ color: TINTA_SUAVE }}>
                        Te mostramos más horarios libres
                      </p>
                    </div>
                  </button>
                  {v.recursos.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => {
                        setRecursoId(r.id);
                        setPaso(3);
                      }}
                      className="flex items-center gap-3 rounded-2xl border p-4 text-left transition-all hover:shadow-sm"
                      style={ficha(recursoId === r.id)}
                    >
                      {r.foto_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={r.foto_url}
                          alt=""
                          className="h-11 w-11 shrink-0 rounded-full object-cover"
                        />
                      ) : (
                        <span
                          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full font-bold text-white"
                          style={{ background: hexA(acento, 0.85) }}
                        >
                          {r.nombre.charAt(0).toUpperCase()}
                        </span>
                      )}
                      <p className="font-semibold" style={{ color: TINTA }}>
                        {r.nombre}
                      </p>
                    </button>
                  ))}
                </div>
              )}

              {/* PASO 3 — Fecha y hora */}
              {paso === 3 && (
                <div>
                  {cargandoHuecos && (
                    <div className="flex flex-col items-center gap-3 py-14">
                      <Loader2 className="h-6 w-6 animate-spin" style={{ color: acento }} />
                      <p className="text-sm" style={{ color: TINTA_SUAVE }}>
                        Buscando horarios libres…
                      </p>
                    </div>
                  )}

                  {!cargandoHuecos && dias.length === 0 && huecos !== null && (
                    <div className="flex flex-col items-center gap-3 py-12 text-center">
                      <CalendarDays className="h-8 w-8" style={{ color: TINTA_SUAVE }} />
                      <p className="font-semibold" style={{ color: TINTA }}>
                        No hay horarios libres en los próximos 14 días
                      </p>
                      {wa && (
                        <a
                          href={wa}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm font-semibold"
                          style={{ color: acento }}
                        >
                          <MessageCircle className="h-4 w-4" />
                          Consultanos por WhatsApp
                        </a>
                      )}
                    </div>
                  )}

                  {!cargandoHuecos && dias.length > 0 && (
                    <>
                      {/* Strip de días */}
                      <div className="-mx-5 flex gap-2 overflow-x-auto px-5 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                        {dias.map((d) => {
                          const et = etiquetaDia(d.fecha);
                          const activa = d.fecha === diaSel;
                          return (
                            <button
                              key={d.fecha}
                              type="button"
                              onClick={() => {
                                setDiaSel(d.fecha);
                                setHoraSel(null);
                              }}
                              className="flex w-[74px] shrink-0 flex-col items-center rounded-2xl border px-2 py-2.5 transition-all"
                              style={{
                                borderColor: activa ? acento : BORDE,
                                background: activa ? acento : "#ffffff",
                              }}
                            >
                              <span
                                className="text-xs font-semibold capitalize"
                                style={{ color: activa ? "#ffffff" : TINTA_SUAVE }}
                              >
                                {et.arriba}
                              </span>
                              <span
                                className="mt-0.5 text-sm font-bold capitalize"
                                style={{ color: activa ? "#ffffff" : TINTA }}
                              >
                                {et.abajo}
                              </span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Grid de horas */}
                      <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
                        {horasDelDia.map((h) => {
                          const activa = h === horaSel;
                          return (
                            <button
                              key={h}
                              type="button"
                              onClick={() => setHoraSel(h)}
                              className="rounded-xl border py-2.5 text-sm font-semibold transition-all"
                              style={{
                                borderColor: activa ? acento : BORDE,
                                background: activa ? acento : "#ffffff",
                                color: activa ? "#ffffff" : TINTA,
                                fontVariantNumeric: "lining-nums tabular-nums",
                              }}
                            >
                              {horaDe(h)}
                            </button>
                          );
                        })}
                      </div>

                      <button
                        type="button"
                        disabled={horaSel === null}
                        onClick={() => setPaso(4)}
                        className="mt-5 w-full rounded-full py-3.5 text-base font-bold text-white transition-opacity disabled:opacity-40"
                        style={{ background: acento }}
                      >
                        Continuar
                      </button>
                    </>
                  )}
                </div>
              )}

              {/* PASO 4 — Datos */}
              {paso === 4 && (
                <div>
                  {/* Resumen */}
                  <div
                    className="mb-4 rounded-2xl border p-4 text-sm"
                    style={{ borderColor: hexA(acento, 0.3), background: hexA(acento, 0.06) }}
                  >
                    <p className="font-bold" style={{ color: TINTA }}>
                      {servicio?.nombre}
                      {servicio?.precio != null && (
                        <span className="float-right" style={{ fontVariantNumeric: "tabular-nums" }}>
                          {cuponAplicado && cuponAplicado.precio_final != null ? (
                            <>
                              <s className="mr-1.5 text-xs font-normal opacity-60">
                                {precioFmt(servicio.precio)}
                              </s>
                              {precioFmt(cuponAplicado.precio_final)}
                            </>
                          ) : (
                            precioFmt(servicio.precio)
                          )}
                        </span>
                      )}
                    </p>
                    {cuponAplicado && (
                      <p className="mt-1 text-xs font-semibold" style={{ color: "#059669" }}>
                        ✓ {cuponAplicado.codigo} aplicado: −{precioFmt(cuponAplicado.descuento)}
                      </p>
                    )}
                    <p className="mt-1 flex items-center gap-1.5 capitalize" style={{ color: TINTA_SUAVE }}>
                      <CalendarDays className="h-4 w-4" />
                      {horaSel ? fechaHoraLegible(horaSel) : ""}
                    </p>
                    <p className="mt-1 flex items-center gap-1.5" style={{ color: TINTA_SUAVE }}>
                      <User className="h-4 w-4" />
                      {recurso ? recurso.nombre : "Cualquier profesional disponible"}
                    </p>
                  </div>

                  <div className="grid gap-3">
                    <div>
                      <label
                        htmlFor="rw-nombre"
                        className="mb-1 block text-sm font-semibold"
                        style={{ color: TINTA }}
                      >
                        Nombre y apellido
                      </label>
                      <input
                        id="rw-nombre"
                        value={nombre}
                        onChange={(e) => setNombre(e.target.value)}
                        placeholder="Ej: Juan Pérez"
                        autoComplete="name"
                        className="w-full rounded-xl border bg-white px-3.5 py-3 text-base outline-none transition-shadow focus:shadow-[0_0_0_2px_var(--tw-shadow-color)]"
                        style={{ borderColor: BORDE, color: TINTA, ["--tw-shadow-color" as string]: hexA(acento, 0.5) }}
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="rw-telefono"
                        className="mb-1 block text-sm font-semibold"
                        style={{ color: TINTA }}
                      >
                        Teléfono (WhatsApp)
                      </label>
                      <input
                        id="rw-telefono"
                        value={telefono}
                        onChange={(e) => setTelefono(e.target.value)}
                        placeholder="Ej: 261 555 0000"
                        inputMode="tel"
                        autoComplete="tel"
                        className="w-full rounded-xl border bg-white px-3.5 py-3 text-base outline-none transition-shadow focus:shadow-[0_0_0_2px_var(--tw-shadow-color)]"
                        style={{ borderColor: BORDE, color: TINTA, ["--tw-shadow-color" as string]: hexA(acento, 0.5) }}
                      />
                      <p className="mt-1 text-xs" style={{ color: TINTA_SUAVE }}>
                        Lo usamos para confirmarte el turno.
                      </p>
                    </div>
                    <div>
                      <label
                        htmlFor="rw-email"
                        className="mb-1 block text-sm font-semibold"
                        style={{ color: TINTA }}
                      >
                        Email
                      </label>
                      <input
                        id="rw-email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="tu@email.com"
                        inputMode="email"
                        autoComplete="email"
                        required
                        className="w-full rounded-xl border bg-white px-3.5 py-3 text-base outline-none transition-shadow focus:shadow-[0_0_0_2px_var(--tw-shadow-color)]"
                        style={{
                          borderColor: email.length > 0 && !emailOk ? "#dc2626" : BORDE,
                          color: TINTA,
                          ["--tw-shadow-color" as string]: hexA(acento, 0.5),
                        }}
                      />
                      <p className="mt-1 text-xs" style={{ color: TINTA_SUAVE }}>
                        Te mandamos la confirmación y el recordatorio del turno acá.
                      </p>
                    </div>
                  </div>

                  {/* Consentimiento de marketing (Ley 25.326): separado de los
                      emails del turno, que son parte del servicio. */}
                  <label className="mt-4 flex cursor-pointer items-start gap-2.5">
                    <input
                      type="checkbox"
                      checked={aceptaMkt}
                      onChange={(e) => setAceptaMkt(e.target.checked)}
                      className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded"
                      style={{ accentColor: acento }}
                    />
                    <span className="text-xs leading-relaxed" style={{ color: TINTA_SUAVE }}>
                      Quiero recibir promociones y novedades de {v.nombre} por email
                      (podés darte de baja cuando quieras).
                    </span>
                  </label>

                  <p className="mt-3 text-[11px] leading-relaxed" style={{ color: TINTA_SUAVE }}>
                    Al reservar aceptás la{" "}
                    <a
                      href="/privacidad#reservas"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline underline-offset-2"
                    >
                      política de privacidad
                    </a>
                    . Tus datos los recibe {v.nombre} para gestionar tu turno.
                  </p>

                  {/* Código de descuento: link discreto que despliega el input */}
                  <div className="mt-4">
                    {!mostrarCupon && !cuponAplicado && (
                      <button
                        type="button"
                        onClick={() => setMostrarCupon(true)}
                        className="text-xs font-semibold underline underline-offset-2"
                        style={{ color: acento }}
                      >
                        Tengo un código de descuento
                      </button>
                    )}
                    {(mostrarCupon || cuponAplicado) && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium" style={{ color: TINTA }}>
                          Código de descuento
                        </p>
                        {cuponAplicado ? (
                          <div
                            className="flex items-center justify-between rounded-xl border px-3.5 py-2.5"
                            style={{ borderColor: "#05966955", background: "#05966910" }}
                          >
                            <span className="text-sm font-bold tracking-wide" style={{ color: "#059669" }}>
                              ✓ {cuponAplicado.codigo} · −{precioFmt(cuponAplicado.descuento)}
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                setCuponAplicado(null);
                                setCodigoCupon("");
                                setErrorCupon("");
                              }}
                              className="text-xs underline"
                              style={{ color: TINTA_SUAVE }}
                            >
                              Quitar
                            </button>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <input
                              value={codigoCupon}
                              onChange={(e) => {
                                setCodigoCupon(e.target.value.toUpperCase());
                                setErrorCupon("");
                              }}
                              onKeyDown={(e) => e.key === "Enter" && aplicarCupon()}
                              placeholder="EJ: INAUGURACION20"
                              className="w-full rounded-xl border bg-white px-3.5 py-2.5 font-mono text-sm uppercase outline-none"
                              style={{ borderColor: errorCupon ? "#dc2626" : BORDE, color: TINTA }}
                            />
                            <button
                              type="button"
                              onClick={aplicarCupon}
                              disabled={validandoCupon || !codigoCupon.trim()}
                              className="shrink-0 rounded-xl px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50"
                              style={{ background: acento }}
                            >
                              {validandoCupon ? "…" : "Aplicar"}
                            </button>
                          </div>
                        )}
                        {errorCupon && (
                          <p className="text-xs font-medium" style={{ color: "#dc2626" }}>
                            {errorCupon}
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    disabled={!puedeConfirmar}
                    onClick={confirmar}
                    className="mt-5 flex w-full items-center justify-center gap-2 rounded-full py-3.5 text-base font-bold text-white transition-opacity disabled:opacity-40"
                    style={{ background: acento }}
                  >
                    {enviando && <Loader2 className="h-5 w-5 animate-spin" />}
                    {enviando ? "Reservando…" : "Confirmar reserva"}
                  </button>
                </div>
              )}

              {/* PASO 5 — Éxito */}
              {paso === 5 && resultado && (
                <div className="flex flex-col items-center pb-2 pt-4 text-center">
                  <motion.svg
                    width="72"
                    height="72"
                    viewBox="0 0 72 72"
                    initial="oculto"
                    animate="visible"
                  >
                    <motion.circle
                      cx="36"
                      cy="36"
                      r="33"
                      fill="none"
                      stroke="#16a34a"
                      strokeWidth="4"
                      variants={{
                        oculto: { pathLength: 0 },
                        visible: { pathLength: 1, transition: { duration: 0.5 } },
                      }}
                    />
                    <motion.path
                      d="M22 37 l10 10 l19 -20"
                      fill="none"
                      stroke="#16a34a"
                      strokeWidth="5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      variants={{
                        oculto: { pathLength: 0 },
                        visible: {
                          pathLength: 1,
                          transition: { duration: 0.4, delay: 0.45 },
                        },
                      }}
                    />
                  </motion.svg>
                  <h4
                    className="mt-4 text-xl font-bold"
                    style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
                  >
                    ¡Listo, {nombre.trim().split(" ")[0]}!
                  </h4>
                  <p className="mt-1 text-sm" style={{ color: TINTA_SUAVE }}>
                    {resultado.mensaje ||
                      "Tu turno quedó reservado y el negocio ya lo tiene en su agenda."}
                  </p>
                  <div
                    className="mt-5 w-full rounded-2xl border p-4 text-left text-sm"
                    style={{ borderColor: BORDE, background: SUPERFICIE }}
                  >
                    <p className="font-bold" style={{ color: TINTA }}>
                      {resultado.servicio}
                    </p>
                    <p className="mt-1 capitalize" style={{ color: TINTA_SUAVE }}>
                      {fechaHoraLegible(resultado.inicio)}
                    </p>
                    <p className="mt-1" style={{ color: TINTA_SUAVE }}>
                      Con {resultado.recurso} · {v.nombre}
                    </p>
                  </div>
                  <a
                    href={linkGoogleCalendar(resultado, v)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full border py-3 text-sm font-semibold"
                    style={{ borderColor: BORDE, color: TINTA }}
                  >
                    <CalendarPlus className="h-4 w-4" style={{ color: "#1a73e8" }} />
                    Agregar a Google Calendar
                  </a>
                  {resultado.pago_url && (
                    <div
                      className="mt-4 w-full rounded-2xl border p-4 text-left"
                      style={{ borderColor: "#f6c94f", background: "#fef8e7" }}
                    >
                      <p className="text-sm font-bold" style={{ color: "#8a6a12" }}>
                        Falta la seña para confirmar
                      </p>
                      <p className="mt-1 text-xs leading-relaxed" style={{ color: "#8a6a12" }}>
                        {v.nombre} pide una seña de{" "}
                        <b>${(resultado.sena_monto ?? 0).toLocaleString("es-AR")}</b> para
                        asegurar tu turno. Si no se abona, el negocio puede liberar el horario.
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          window.location.href = resultado.pago_url as string;
                        }}
                        className="mt-3 w-full rounded-full py-3 text-sm font-bold text-white"
                        style={{ background: "#009ee3" }}
                      >
                        Pagar seña con Mercado Pago
                      </button>
                    </div>
                  )}
                  {wa && (
                    <a
                      href={wa}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold"
                      style={{ color: acento }}
                    >
                      <MessageCircle className="h-4 w-4" />
                      ¿Dudas? Escribinos por WhatsApp
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={onCerrar}
                    className={
                      resultado.pago_url
                        ? "mt-4 w-full rounded-full border py-3 text-sm font-semibold"
                        : "mt-5 w-full rounded-full py-3.5 text-base font-bold text-white"
                    }
                    style={
                      resultado.pago_url
                        ? { borderColor: BORDE, color: TINTA_SUAVE, background: "#fff" }
                        : { background: acento }
                    }
                  >
                    {resultado.pago_url ? "Pagar más tarde" : "Listo"}
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
