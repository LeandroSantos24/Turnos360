"use client";

/**
 * Gestionar mi turno (/gestionar/<token>): el link que llega en los emails.
 *
 * El cliente ve su turno y, si el negocio lo permite, lo cambia de día u
 * horario o lo cancela. Sin cuenta: el token es la llave, y solo abre ESTE
 * turno. Todo se valida en el servidor (services/autogestion.py); acá solo se
 * muestra lo que el servidor dice que se puede hacer.
 *
 * Cada acción tiene un paso de confirmación: un clic suelto no cancela nada.
 */

import { legible } from "@/lib/color";
import { useCallback, useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { ArrowLeft, CalendarClock, CalendarX2, Check, Loader2, MapPin, MessageCircle, Phone } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  cancelarGestion,
  huecosGestion,
  obtenerGestion,
  reprogramarGestion,
  type GestionTurno,
  type HuecosDia,
} from "@/lib/publico-api";
import { telefonoWa } from "@/lib/telefono";

const ACENTO = "#0ca88c";

/** La agenda guarda hora de pared etiquetada UTC: se leen los dígitos tal cual. */
function local(iso: string): Date {
  const d = new Date(iso);
  return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), d.getUTCHours(), d.getUTCMinutes());
}
const fechaLarga = (iso: string) => {
  const t = format(local(iso), "EEEE d 'de' MMMM", { locale: es });
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const hora = (iso: string) => format(local(iso), "HH:mm");
const diaCorto = (fecha: string) => {
  const [a, m, d] = fecha.split("-").map(Number);
  const f = new Date(a, m - 1, d);
  return { arriba: format(f, "EEE", { locale: es }), abajo: format(f, "d MMM", { locale: es }) };
};

type Vista = "turno" | "elegir" | "confirmar-cambio" | "confirmar-cancelar" | "listo";

export default function GestionarTurno({ params }: { params: { token: string } }) {
  const token = params.token;
  const [t, setT] = useState<GestionTurno | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vista, setVista] = useState<Vista>("turno");
  const [huecos, setHuecos] = useState<HuecosDia[] | null>(null);
  const [dia, setDia] = useState<string | null>(null);
  const [elegido, setElegido] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [hecho, setHecho] = useState<"cancelado" | "cambiado" | null>(null);
  const [antes, setAntes] = useState<string | null>(null);

  useEffect(() => {
    obtenerGestion(token)
      .then(setT)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No pudimos abrir tu turno. Probá en un rato."));
  }, [token]);

  const acento = legible(t?.color_marca || ACENTO);

  const abrirCambio = useCallback(() => {
    setVista("elegir");
    setAviso(null);
    setElegido(null);
    if (huecos === null) {
      huecosGestion(token)
        .then((h) => {
          setHuecos(h);
          setDia(h[0]?.fecha ?? null);
        })
        .catch((e) => {
          setHuecos([]);
          setAviso(e instanceof ApiError ? e.message : "No pudimos cargar los horarios.");
        });
    }
  }, [huecos, token]);

  const horasDelDia = useMemo(() => huecos?.find((d) => d.fecha === dia)?.horas ?? [], [huecos, dia]);

  async function confirmarCambio() {
    if (!elegido || !t) return;
    setEnviando(true);
    setAviso(null);
    try {
      const previo = t.inicio;
      const nuevo = await reprogramarGestion(token, elegido);
      setAntes(previo);
      setT(nuevo);
      setHecho("cambiado");
      setVista("listo");
    } catch (e) {
      setAviso(e instanceof ApiError ? e.message : "No se pudo cambiar el turno.");
      // El horario pudo ocuparse mientras tanto: se recargan los huecos.
      setHuecos(null);
      setVista("turno");
    } finally {
      setEnviando(false);
    }
  }

  async function confirmarCancelacion() {
    setEnviando(true);
    setAviso(null);
    try {
      const nuevo = await cancelarGestion(token, motivo.trim() || undefined);
      setT(nuevo);
      setHecho("cancelado");
      setVista("listo");
    } catch (e) {
      setAviso(e instanceof ApiError ? e.message : "No se pudo cancelar el turno.");
      setVista("turno");
    } finally {
      setEnviando(false);
    }
  }

  if (error) {
    return (
      <Marco acento={ACENTO}>
        <div className="rounded-3xl bg-white p-6 text-center shadow-sm">
          <CalendarX2 className="mx-auto h-10 w-10 text-slate-400" aria-hidden />
          <h1 className="mt-3 text-lg font-bold text-slate-900">No pudimos abrir este turno</h1>
          <p className="mt-1 text-sm text-slate-600">{error}</p>
        </div>
      </Marco>
    );
  }
  if (!t) {
    return (
      <Marco acento={ACENTO}>
        <div className="flex justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" aria-label="Cargando" />
        </div>
      </Marco>
    );
  }

  const wa = telefonoWa(t.telefono);
  const cancelado = t.estado === "cancelado";

  return (
    <Marco acento={acento}>
      <header className="flex items-center gap-3">
        {t.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={t.logo_url} alt="" className="h-11 w-11 rounded-2xl object-cover" />
        ) : (
          <span
            aria-hidden
            className="flex h-11 w-11 items-center justify-center rounded-2xl text-lg font-bold text-white"
            style={{ background: acento }}
          >
            {t.negocio.charAt(0)}
          </span>
        )}
        <div className="min-w-0">
          <p className="truncate font-bold text-slate-900">{t.negocio}</p>
          <p className="text-xs text-slate-600">Tu turno</p>
        </div>
      </header>

      {aviso && (
        <p role="alert" className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {aviso}
        </p>
      )}

      {vista === "listo" && (
        <section className="mt-4 rounded-3xl bg-white p-6 text-center shadow-sm" aria-live="polite">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full" style={{ background: `${acento}22`, color: acento }}>
            <Check className="h-6 w-6" aria-hidden />
          </span>
          {hecho === "cancelado" ? (
            <>
              <h1 className="mt-3 text-xl font-bold text-slate-900">Turno cancelado</h1>
              <p className="mt-1 text-sm text-slate-600">
                Gracias por avisar: el horario ya quedó libre para otra persona. Te mandamos la confirmación por email.
              </p>
            </>
          ) : (
            <>
              <h1 className="mt-3 text-xl font-bold text-slate-900">¡Listo, cambiamos tu turno!</h1>
              <p className="mt-1 text-sm text-slate-600">
                {antes && <>Antes: {fechaLarga(antes)} a las {hora(antes)}. </>}
                Ahora es el <b>{fechaLarga(t.inicio)} a las {hora(t.inicio)}</b>. Te llega la confirmación por email.
              </p>
            </>
          )}
          <button type="button" onClick={() => setVista("turno")} className="mt-5 text-sm font-semibold underline underline-offset-4" style={{ color: "#0a6b5c" }}>
            Ver mi turno
          </button>
        </section>
      )}

      {vista === "turno" && (
        <>
          <section className="mt-4 rounded-3xl bg-white p-5 shadow-sm">
            {t.cliente && <p className="text-sm text-slate-600">Hola, {t.cliente}</p>}
            <p className={`mt-1 text-xl font-bold ${cancelado ? "text-slate-500 line-through" : "text-slate-900"}`}>{t.servicio}</p>
            {t.profesional && <p className="text-sm text-slate-600">con {t.profesional}</p>}
            <div className="mt-4 rounded-2xl bg-slate-50 p-4">
              <p className="text-base font-semibold text-slate-900">{fechaLarga(t.inicio)}</p>
              <p className="text-2xl font-bold tabular-nums text-slate-900">{hora(t.inicio)}</p>
            </div>
            {t.direccion && (
              <p className="mt-3 flex items-start gap-1.5 text-sm text-slate-700">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {t.direccion}
              </p>
            )}
            <p className="mt-3">
              <EstadoChip estado={t.estado} />
            </p>
            {t.sena_estado === "pagada" && t.sena_monto && !cancelado && (
              <p className="mt-3 text-xs text-slate-600">
                Dejaste una seña de ${t.sena_monto.toLocaleString("es-AR")}. Si cancelás, la seña no se devuelve.
              </p>
            )}
          </section>

          {(t.puede_reprogramar || t.puede_cancelar) && (
            <div className="mt-4 grid gap-2">
              {t.puede_reprogramar && (
                <button
                  type="button"
                  onClick={abrirCambio}
                  className="flex items-center justify-center gap-2 rounded-2xl px-5 py-3.5 font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  style={{ background: acento }}
                >
                  <CalendarClock className="h-5 w-5" aria-hidden /> Cambiar día u horario
                </button>
              )}
              {t.puede_cancelar && (
                <button
                  type="button"
                  onClick={() => {
                    setAviso(null);
                    setVista("confirmar-cancelar");
                  }}
                  className="rounded-2xl border border-slate-300 bg-white px-5 py-3.5 font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
                >
                  Cancelar turno
                </button>
              )}
            </div>
          )}

          {t.motivo_bloqueo && (
            <p className="mt-4 rounded-2xl bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">{t.motivo_bloqueo}</p>
          )}

          {(t.telefono || wa) && (
            <div className="mt-4 flex flex-wrap justify-center gap-4 text-sm">
              {wa && (
                <a href={`https://wa.me/${wa}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-medium text-slate-700 underline-offset-4 hover:underline">
                  <MessageCircle className="h-4 w-4" aria-hidden /> Escribirle al negocio
                </a>
              )}
              {t.telefono && (
                <a href={`tel:${t.telefono.replace(/[^\d+]/g, "")}`} className="inline-flex items-center gap-1.5 font-medium text-slate-700 underline-offset-4 hover:underline">
                  <Phone className="h-4 w-4" aria-hidden /> Llamar
                </a>
              )}
            </div>
          )}
        </>
      )}

      {vista === "elegir" && (
        <section className="mt-4 rounded-3xl bg-white p-5 shadow-sm" aria-labelledby="t-elegir">
          <Volver onClick={() => setVista("turno")} />
          <h1 id="t-elegir" className="mt-2 text-lg font-bold text-slate-900">Elegí el nuevo día y horario</h1>
          <p className="text-sm text-slate-600">{t.servicio} · en el mismo local</p>
          {huecos === null ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" aria-label="Cargando horarios" />
            </div>
          ) : huecos.length === 0 ? (
            <p className="mt-4 text-sm text-slate-600">No hay horarios libres en los próximos días. Escribile al negocio para coordinar.</p>
          ) : (
            <>
              <div className="-mx-1 mt-4 flex gap-2 overflow-x-auto px-1 pb-1" role="radiogroup" aria-label="Día">
                {huecos.map((d) => {
                  const c = diaCorto(d.fecha);
                  const sel = d.fecha === dia;
                  return (
                    <button
                      key={d.fecha}
                      type="button"
                      role="radio"
                      aria-checked={sel}
                      onClick={() => {
                        setDia(d.fecha);
                        setElegido(null);
                      }}
                      className="flex min-w-[64px] flex-col items-center rounded-2xl border px-3 py-2 text-sm"
                      style={sel ? { borderColor: acento, background: `${acento}14` } : undefined}
                    >
                      <span className="capitalize text-slate-600">{c.arriba}</span>
                      <span className="font-semibold text-slate-900">{c.abajo}</span>
                    </button>
                  );
                })}
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4" role="radiogroup" aria-label="Horario">
                {horasDelDia.map((h) => {
                  const sel = h === elegido;
                  const actual = h === t.inicio;
                  return (
                    <button
                      key={h}
                      type="button"
                      role="radio"
                      aria-checked={sel}
                      disabled={actual}
                      onClick={() => setElegido(h)}
                      className="rounded-xl border py-2.5 text-sm font-semibold tabular-nums text-slate-800 disabled:opacity-40"
                      style={sel ? { borderColor: acento, background: acento, color: "#fff" } : undefined}
                      title={actual ? "Es tu horario actual" : undefined}
                    >
                      {hora(h)}
                    </button>
                  );
                })}
              </div>
              <button
                type="button"
                disabled={!elegido}
                onClick={() => setVista("confirmar-cambio")}
                className="mt-5 w-full rounded-2xl px-5 py-3.5 font-semibold text-white disabled:opacity-40"
                style={{ background: acento }}
              >
                Continuar
              </button>
            </>
          )}
        </section>
      )}

      {vista === "confirmar-cambio" && elegido && (
        <section className="mt-4 rounded-3xl bg-white p-5 shadow-sm" aria-labelledby="t-conf-cambio">
          <Volver onClick={() => setVista("elegir")} />
          <h1 id="t-conf-cambio" className="mt-2 text-lg font-bold text-slate-900">¿Confirmás el cambio?</h1>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="rounded-2xl bg-slate-50 p-3">
              <dt className="text-slate-600">Antes</dt>
              <dd className="font-semibold text-slate-500 line-through">{fechaLarga(t.inicio)} · {hora(t.inicio)}</dd>
            </div>
            <div className="rounded-2xl p-3" style={{ background: `${acento}14` }}>
              <dt className="text-slate-600">Ahora</dt>
              <dd className="font-semibold text-slate-900">{fechaLarga(elegido)} · {hora(elegido)}</dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={confirmarCambio}
            disabled={enviando}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 font-semibold text-white disabled:opacity-60"
            style={{ background: acento }}
          >
            {enviando && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            Sí, cambiar mi turno
          </button>
        </section>
      )}

      {vista === "confirmar-cancelar" && (
        <section className="mt-4 rounded-3xl bg-white p-5 shadow-sm" aria-labelledby="t-conf-cancelar">
          <Volver onClick={() => setVista("turno")} />
          <h1 id="t-conf-cancelar" className="mt-2 text-lg font-bold text-slate-900">¿Seguro que querés cancelar?</h1>
          <p className="mt-1 text-sm text-slate-600">
            {t.servicio}, {fechaLarga(t.inicio).toLowerCase()} a las {hora(t.inicio)}. El horario queda libre para otra persona.
          </p>
          {t.sena_estado === "pagada" && t.sena_monto && (
            <p className="mt-3 rounded-2xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
              La seña de ${t.sena_monto.toLocaleString("es-AR")} no se devuelve.
            </p>
          )}
          {t.puede_reprogramar && (
            <p className="mt-3 text-sm text-slate-600">
              ¿Preferís otro día?{" "}
              <button type="button" onClick={abrirCambio} className="font-semibold underline underline-offset-4" style={{ color: "#0a6b5c" }}>
                Cambialo en vez de cancelarlo
              </button>
              .
            </p>
          )}
          <label htmlFor="motivo" className="mt-4 block text-sm font-medium text-slate-800">
            ¿Querés contarle al negocio por qué? <span className="font-normal text-slate-500">(opcional)</span>
          </label>
          <textarea
            id="motivo"
            rows={2}
            maxLength={200}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
          <button
            type="button"
            onClick={confirmarCancelacion}
            disabled={enviando}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-red-600 px-5 py-3.5 font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          >
            {enviando && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            Sí, cancelar mi turno
          </button>
        </section>
      )}

      <p className="mt-8 text-center text-xs text-slate-500">
        Este link es personal: no lo compartas. Turnos360
      </p>
    </Marco>
  );
}

function Marco({ acento, children }: { acento: string; children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8" style={{ backgroundImage: `linear-gradient(180deg, ${acento}1f, transparent 240px)` }}>
      <div className="mx-auto max-w-md">{children}</div>
    </main>
  );
}

function Volver({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900">
      <ArrowLeft className="h-4 w-4" aria-hidden /> Volver
    </button>
  );
}

function EstadoChip({ estado }: { estado: string }) {
  const m: Record<string, [string, string]> = {
    pendiente: ["Pendiente de confirmación", "bg-amber-100 text-amber-900"],
    confirmado: ["Confirmado", "bg-emerald-100 text-emerald-900"],
    cancelado: ["Cancelado", "bg-slate-200 text-slate-700"],
    en_curso: ["En curso", "bg-sky-100 text-sky-900"],
    finalizado: ["Atendido", "bg-slate-200 text-slate-700"],
    ausente: ["No asistió", "bg-slate-200 text-slate-700"],
  };
  const [txt, cls] = m[estado] ?? [estado, "bg-slate-200 text-slate-700"];
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>{txt}</span>;
}
