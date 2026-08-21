"use client";

/**
 * WhatsApp (/whatsapp) — solo el dueño.
 *
 * Qué tiene que poder contestar esta pantalla, en este orden:
 *
 *   1. ¿Cuántos mensajes me quedan?          -> el número grande, arriba
 *   2. ¿A quién NO le va a llegar nada?      -> el cartel ámbar de teléfonos
 *   3. ¿Le llegó a fulano?                   -> el historial
 *   4. ¿En qué se me fueron los mensajes?    -> el libro de movimientos
 *
 * La 2 es la que nadie pide y la que más sirve: un cliente con el teléfono
 * cargado como "no tiene" no recibe el recordatorio y nadie se entera nunca.
 */

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  MessageCircle,
  Phone,
  Send,
  ShoppingCart,
  TestTube,
} from "lucide-react";
import { toast } from "sonner";

import { ApiError, esCancelado } from "@/lib/api";
import { WA_NUMERO } from "@/lib/contacto";
import { NUM, pesos } from "@/lib/numeros";
import {
  ESTADO_CLASE,
  ESTADO_LABEL,
  MOTIVO_LABEL,
  estadoWhatsapp,
  mensajesWhatsapp,
  movimientosWhatsapp,
  probarNumero,
  type EstadoWhatsapp,
  type MensajeWhatsapp,
  type MovimientoWhatsapp,
  type PackWhatsapp,
  type PruebaNumero,
} from "@/lib/whatsapp-api";
import { RequiereDueno } from "@/components/requiere-rol";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** Debajo de esto el negocio se queda sin mensajes en unos días. */
const SALDO_BAJO = 50;

function fechaCorta(iso: string): string {
  const f = new Date(iso);
  return f.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ContenidoWhatsapp() {
  const [estado, setEstado] = useState<EstadoWhatsapp | null>(null);
  const [mensajes, setMensajes] = useState<MensajeWhatsapp[]>([]);
  const [movimientos, setMovimientos] = useState<MovimientoWhatsapp[]>([]);
  const [cargando, setCargando] = useState(true);

  const [telefono, setTelefono] = useState("");
  const [probando, setProbando] = useState(false);
  const [prueba, setPrueba] = useState<PruebaNumero | null>(null);

  const cargar = useCallback(async (signal?: AbortSignal) => {
    setCargando(true);
    try {
      const [e, m, mv] = await Promise.all([
        estadoWhatsapp(signal),
        mensajesWhatsapp(30, signal),
        movimientosWhatsapp(30, signal),
      ]);
      setEstado(e);
      setMensajes(m);
      setMovimientos(mv);
    } catch (err) {
      if (esCancelado(err)) return;
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo cargar WhatsApp",
      );
    } finally {
      if (!signal?.aborted) setCargando(false);
    }
  }, []);

  useEffect(() => {
    const control = new AbortController();
    cargar(control.signal);
    return () => control.abort();
  }, [cargar]);

  async function probar() {
    if (!telefono.trim()) return;
    setProbando(true);
    setPrueba(null);
    try {
      setPrueba(await probarNumero(telefono));
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No pude probar ese número",
      );
    } finally {
      setProbando(false);
    }
  }

  function pedirPack(pack: PackWhatsapp) {
    const texto =
      `Hola! Quiero cargar el pack de ${pack.cantidad} mensajes de WhatsApp ` +
      `(${pesos(pack.precio_ars)}) para mi negocio en Turnos360.`;
    window.open(
      `https://wa.me/${WA_NUMERO}?text=${encodeURIComponent(texto)}`,
      "_blank",
      "noopener,noreferrer",
    );
  }

  const sinSaldo = (estado?.disponible ?? 0) < 1;
  const saldoBajo = !sinSaldo && (estado?.disponible ?? 0) < SALDO_BAJO;

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-6">
      {/* ── Encabezado ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-2.5">
        <MessageCircle className="h-6 w-6 text-primary" />
        <div>
          <h1 className="font-[family-name:var(--font-syne)] text-2xl font-bold">
            WhatsApp
          </h1>
          <p className="text-sm text-muted-foreground">
            Los recordatorios de turno que salen por WhatsApp, y cuántos
            mensajes te quedan.
          </p>
        </div>
      </div>

      {cargando && !estado ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : !estado ? null : (
        <>
          {/* ── Modo simulado ─────────────────────────────────────────── */}
          {estado.proveedor === "simulado" && (
            <div className="flex items-start gap-2.5 rounded-2xl border border-dashed p-4">
              <TestTube className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
              <div className="text-sm">
                <p className="font-semibold">Modo de prueba</p>
                <p className="mt-0.5 text-muted-foreground">
                  Todavía no está conectado a WhatsApp, así que{" "}
                  <strong>no le llega nada a nadie</strong>. Igual todo funciona
                  como si fuera de verdad: el saldo baja y los envíos quedan
                  registrados acá abajo, para que puedas probar el circuito
                  completo.
                </p>
              </div>
            </div>
          )}

          {/* ── Saldo ─────────────────────────────────────────────────── */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div
              className={`rounded-2xl border p-5 sm:col-span-1 ${
                sinSaldo
                  ? "border-red-500/30 bg-red-500/5"
                  : saldoBajo
                    ? "border-amber-500/30 bg-amber-500/10"
                    : "bg-card"
              }`}
            >
              <p className="text-sm text-muted-foreground">Mensajes disponibles</p>
              <p className="mt-1 text-4xl font-bold" style={NUM}>
                {estado.disponible.toLocaleString("es-AR")}
              </p>
              {sinSaldo ? (
                <p className="mt-2 text-sm font-medium text-red-600 dark:text-red-400">
                  Sin mensajes: los recordatorios están saliendo por email.
                </p>
              ) : saldoBajo ? (
                <p className="mt-2 text-sm font-medium text-amber-700 dark:text-amber-500">
                  Te quedan pocos. Cargá antes de que se corten.
                </p>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  Usaste {estado.consumidos.toLocaleString("es-AR")} en total.
                </p>
              )}
            </div>

            <div className="rounded-2xl border bg-card p-5 sm:col-span-2">
              <p className="text-sm text-muted-foreground">Cómo funciona</p>
              <ul className="mt-2 space-y-1.5 text-sm">
                <li className="flex gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  Cada recordatorio que sale por WhatsApp descuenta un mensaje.
                </li>
                <li className="flex gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  Si un envío no sale, el mensaje se te devuelve. No pagás lo que
                  no llegó.
                </li>
                <li className="flex gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  Cuando te quedás sin mensajes, el recordatorio sale por email:
                  el cliente igual se entera.
                </li>
              </ul>
            </div>
          </div>

          {/* ── Los que no van a recibir nada ─────────────────────────── */}
          {estado.clientes_sin_telefono_valido > 0 && (
            <div className="flex items-start gap-2.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
              <div className="text-sm">
                <p className="font-semibold text-amber-800 dark:text-amber-400">
                  {estado.clientes_sin_telefono_valido === 1
                    ? "1 cliente no va a recibir el recordatorio"
                    : `${estado.clientes_sin_telefono_valido} clientes no van a recibir el recordatorio`}
                </p>
                <p className="mt-0.5 text-muted-foreground">
                  Tienen el teléfono vacío o cargado de una forma que no es un
                  celular (algo como &ldquo;no tiene&rdquo;, o un número
                  incompleto). Corregilos desde Clientes y empiezan a recibir
                  solos. Podés probar acá abajo cómo queda un número antes de
                  guardarlo.
                </p>
              </div>
            </div>
          )}

          {/* ── Probar un número ──────────────────────────────────────── */}
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center gap-2">
              <Phone className="h-5 w-5 text-primary" />
              <h2 className="font-semibold">Probar un número</h2>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Escribilo como lo tengas anotado. Te digo si sirve y cómo va a
              salir el mensaje. No gasta mensajes: probalo las veces que quieras.
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              <Input
                value={telefono}
                onChange={(e) => setTelefono(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") probar();
                }}
                placeholder="0261 15 4123456"
                className="max-w-xs"
              />
              <Button onClick={probar} disabled={probando || !telefono.trim()}>
                <Send className="mr-1.5 h-4 w-4" />
                {probando ? "Probando…" : "Probar"}
              </Button>
            </div>

            {prueba && (
              <div className="mt-3 space-y-2 rounded-xl border bg-muted/40 p-3 text-sm">
                <p>
                  <span className="text-muted-foreground">Se manda a: </span>
                  <span className="font-mono">+{prueba.destino}</span>
                </p>
                <p className="text-muted-foreground">Así le llega el mensaje:</p>
                <p className="rounded-lg bg-background p-3">{prueba.texto}</p>
              </div>
            )}
          </div>

          {/* ── Packs ─────────────────────────────────────────────────── */}
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center gap-2">
              <ShoppingCart className="h-5 w-5 text-primary" />
              <h2 className="font-semibold">Cargar mensajes</h2>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Elegí un pack y escribinos. Los mensajes no vencen.
            </p>

            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {estado.packs.map((pack) => (
                <div
                  key={pack.cantidad}
                  className="flex flex-col rounded-xl border p-4"
                >
                  <p className="text-lg font-bold" style={NUM}>
                    {pack.cantidad.toLocaleString("es-AR")}
                  </p>
                  <p className="text-xs text-muted-foreground">mensajes</p>
                  <p className="mt-2 font-semibold" style={NUM}>
                    {pesos(pack.precio_ars)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {pesos(pack.precio_por_mensaje)} c/u
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3"
                    onClick={() => pedirPack(pack)}
                  >
                    Pedir
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {/* ── Historial ─────────────────────────────────────────────── */}
          <div className="rounded-2xl border bg-card p-5">
            <h2 className="font-semibold">Últimos envíos</h2>
            {mensajes.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                Todavía no salió ningún WhatsApp. Los recordatorios se mandan
                solos 24 horas antes de cada turno.
              </p>
            ) : (
              <div className="mt-3 space-y-2">
                {mensajes.map((m) => (
                  <div
                    key={m.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3 text-sm"
                  >
                    <div className="min-w-0">
                      <p className="font-medium">{m.cliente ?? "—"}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {m.telefono ?? "sin teléfono"} · {fechaCorta(m.fecha)}
                      </p>
                      {m.error && (
                        <p className="mt-0.5 text-xs text-red-600 dark:text-red-400">
                          {m.error}
                        </p>
                      )}
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        ESTADO_CLASE[m.estado] ?? "bg-muted"
                      }`}
                    >
                      {ESTADO_LABEL[m.estado] ?? m.estado}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Movimientos ───────────────────────────────────────────── */}
          <div className="rounded-2xl border bg-card p-5">
            <h2 className="font-semibold">Movimientos</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Cada carga y cada mensaje usado, con fecha. Si alguna vez no te
              cierra el saldo, la cuenta está acá.
            </p>
            {movimientos.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                Todavía no hay movimientos.
              </p>
            ) : (
              <div className="mt-3 divide-y">
                {movimientos.map((mv) => (
                  <div
                    key={mv.id}
                    className="flex items-center justify-between gap-3 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <p>{MOTIVO_LABEL[mv.motivo] ?? mv.motivo}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {fechaCorta(mv.fecha)}
                        {mv.precio_ars ? ` · ${pesos(mv.precio_ars)}` : ""}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 font-semibold ${
                        mv.cantidad > 0
                          ? "text-primary"
                          : "text-muted-foreground"
                      }`}
                      style={NUM}
                    >
                      {mv.cantidad > 0 ? "+" : ""}
                      {mv.cantidad}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function WhatsappPage() {
  return (
    <RequiereDueno>
      <ContenidoWhatsapp />
    </RequiereDueno>
  );
}
