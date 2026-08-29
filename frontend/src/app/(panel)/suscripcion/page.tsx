"use client";

/**
 * Mi suscripción (/suscripcion).
 *
 * Lo que el dueño necesita saber sobre su cuenta de Turnos360: en qué estado
 * está, cuánto paga, hasta cuándo, qué pagó antes y cómo pagar.
 *
 * El objetivo es que nunca tenga que escribirte para preguntar "¿cuándo me
 * vence?" o "¿me pasás el CBU?". Los datos de cobro salen del entorno, no del
 * código.
 */

import { useCallback, useEffect, useState } from "react";
import { format, parseISO, isValid } from "date-fns";
import { es } from "date-fns/locale";
import { toast } from "sonner";
import { CreditCard, Copy, Check, AlertTriangle, Clock, ExternalLink } from "lucide-react";
import { Input } from "@/components/ui/input";

import {
  avisarPagoSuscripcion,
  leerAvisoPago,
  leerMiSuscripcion,
  pagarSuscripcionMP,
  type MiSuscripcion,
} from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";

const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

function pesos(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toLocaleString("es-AR")}`;
}

/** "2026-08-05" -> "5 de agosto de 2026". Nunca formatea una fecha inválida. */
function fechaLarga(iso: string | null): string {
  if (!iso) return "—";
  const d = parseISO(iso);
  return isValid(d) ? format(d, "d 'de' MMMM 'de' yyyy", { locale: es }) : "—";
}

function fechaCorta(iso: string | null): string {
  if (!iso) return "—";
  const d = parseISO(iso);
  return isValid(d) ? format(d, "d MMM yyyy", { locale: es }) : "—";
}

/** Colores del cartel de estado. */
const ESTILO_ESTADO: Record<string, { fondo: string; borde: string; texto: string }> = {
  activa: { fondo: "bg-emerald-500/10", borde: "border-emerald-500/30", texto: "text-emerald-700 dark:text-emerald-400" },
  prorroga: { fondo: "bg-amber-500/10", borde: "border-amber-500/30", texto: "text-amber-700 dark:text-amber-400" },
  vencida: { fondo: "bg-red-500/10", borde: "border-red-500/30", texto: "text-red-700 dark:text-red-400" },
  sin_vencimiento: { fondo: "bg-muted", borde: "border-border", texto: "text-muted-foreground" },
  prueba: { fondo: "bg-sky-500/10", borde: "border-sky-500/30", texto: "text-sky-700 dark:text-sky-400" },
};

/** Fila copiable: en el celular, tipear un CBU de 22 dígitos es garantía de error. */
function FilaCopiable({ etiqueta, valor }: { etiqueta: string; valor: string }) {
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
            toast.success(`${etiqueta} copiado`);
            setTimeout(() => setCopiado(false), 1800);
          } catch {
            toast.error("No se pudo copiar. Seleccionalo a mano.");
          }
        }}
      >
        {copiado ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
  );
}

export default function SuscripcionPage() {
  const [datos, setDatos] = useState<MiSuscripcion | null>(null);
  const [cargando, setCargando] = useState(true);
  // Abre el bloque "Cómo pagar" desde el botón de arriba. Arranca cerrado para
  // que la pantalla siga siendo, ante todo, "cuándo vence".
  const [pagando, setPagando] = useState(false);
  const [avisoPendiente, setAvisoPendiente] = useState(false);
  const [yendoAMP, setYendoAMP] = useState(false);
  const [avisando, setAvisando] = useState(false);
  const [referencia, setReferencia] = useState("");

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

  async function irAMercadoPago() {
    setYendoAMP(true);
    try {
      const { url } = await pagarSuscripcionMP();
      // Checkout Pro se abre en la misma pestaña: el dueño vuelve solo por las
      // back_urls, y así no se pierde entre ventanas en el celular.
      window.location.href = url;
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "No se pudo abrir Mercado Pago",
      );
      setYendoAMP(false);
    }
  }

  async function avisarQueTransferi() {
    setAvisando(true);
    try {
      const r = await avisarPagoSuscripcion({
        monto: datos?.precio_mensual ?? datos?.precio_lista ?? null,
        referencia: referencia.trim() || null,
      });
      toast.success(r.detalle);
      setAvisoPendiente(true);
      setReferencia("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo registrar el aviso");
    } finally {
      setAvisando(false);
    }
  }

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (cargando) {
    return <p className="p-6 text-sm text-muted-foreground">Cargando…</p>;
  }
  if (!datos) {
    return <p className="p-6 text-sm text-muted-foreground">No se pudo cargar.</p>;
  }

  const est = ESTILO_ESTADO[datos.estado] ?? ESTILO_ESTADO.sin_vencimiento;
  const precioAPagar = datos.precio_mensual ?? datos.precio_lista;
  const c = datos.cobro;
  const hayTransferencia = Boolean(c.cbu || c.alias);
  // c.mp_checkout es el Checkout de verdad (genera el pago y lo acredita solo).
  // c.mp_link es el link permanente de siempre, que sigue sirviendo de respaldo.
  const hayCobro = hayTransferencia || Boolean(c.mp_link) || c.mp_checkout;

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 md:p-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold" style={SYNE}>
          <CreditCard className="h-6 w-6" />
          Mi suscripción
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tu plan, tus vencimientos y cómo pagar.
        </p>
      </header>

      {/* Estado */}
      <section className={`rounded-2xl border p-5 md:p-6 ${est.fondo} ${est.borde}`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wide ${est.texto}`}>
              {datos.estado === "prueba" && "Período de prueba"}
              {datos.estado === "activa" && "Al día"}
              {datos.estado === "prorroga" && "Vencida · en período de gracia"}
              {datos.estado === "vencida" && "Vencida"}
              {datos.estado === "sin_vencimiento" && "Sin vencimiento"}
            </p>
            <p className="mt-1.5 text-lg font-bold" style={SYNE}>
              {datos.mensaje}
            </p>
            {datos.vence && (
              <p className="mt-0.5 text-sm text-muted-foreground">
                {datos.estado === "prueba"
                  ? `Tu prueba termina el ${fechaLarga(datos.vence)}`
                  : `Próximo vencimiento: ${fechaLarga(datos.vence)}`}
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Cuota mensual
            </p>
            <p className="text-3xl font-extrabold tabular-nums" style={SYNE}>
              {pesos(datos.precio_mensual ?? datos.ultimo_monto)}
            </p>
            {datos.precio_mensual === null && datos.ultimo_monto !== null && (
              <p className="text-xs text-muted-foreground">según tu último pago</p>
            )}
          </div>
        </div>

        {datos.estado === "prueba" && (
          <p className="mt-4 text-sm">
            Estás usando Turnos360 gratis, con todas las funciones. Cuando
            termine la prueba, escribinos para seguir
            {/* Cuota pactada si ya la hay; si no, el precio de lista. Antes,
                sin cuota cargada la frase terminaba en "para seguir." y el
                que estaba probando no sabía cuánto le iba a salir. */}
            {datos.precio_mensual || datos.precio_lista
              ? ` por ${pesos(datos.precio_mensual ?? datos.precio_lista)} por mes`
              : ""}
            . No te cobramos nada automáticamente ni te pedimos tarjeta.
          </p>
        )}

        {datos.estado === "activa" && datos.corte && (
          <p className="mt-4 text-sm">
            Después del vencimiento tenés{" "}
            <strong>{datos.dias_prorroga} días de gracia</strong> para pagar sin
            que se corte nada. En la práctica, tu servicio sigue andando hasta el{" "}
            <strong>{fechaLarga(datos.corte)}</strong>.
          </p>
        )}

        {datos.estado === "prorroga" && (
          <p className="mt-4 flex items-start gap-2 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Tu cuenta sigue funcionando con normalidad. Tenés tiempo de pagar
              hasta el <strong>{fechaLarga(datos.corte)}</strong>; pasada esa
              fecha, la agenda y tu página dejan de estar disponibles.
            </span>
          </p>
        )}

        {datos.precio_mensual === null && datos.estado !== "prueba" && (
          <p className="mt-4 text-sm text-muted-foreground">
            Todavía no tenés una cuota cargada. Escribinos y la definimos.
          </p>
        )}

        {hayCobro && (
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button
              size="lg"
              onClick={() => {
                setPagando(true);
                document
                  .getElementById("como-pagar")
                  ?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
            >
              {datos.estado === "prueba" ? "Activar mi plan Pro" : "Renovar mi plan"}
            </Button>
            {precioAPagar !== null && (
              <span className="text-sm text-muted-foreground">
                {pesos(precioAPagar)} por mes
              </span>
            )}
          </div>
        )}
      </section>

      {/* Qué incluye tu plan, y cuánto estás usando.
          Va ANTES de "Cómo pagar" a propósito: el dueño tiene que ver que se
          está quedando sin lugar antes de chocarse con el error al cargar el
          profesional número cuatro. */}
      {datos.plan_etiqueta && (
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-bold" style={SYNE}>
              Tu plan {datos.plan_etiqueta}
            </h2>
            <span className="text-sm text-muted-foreground">
              {datos.plan_resumen}
            </span>
          </div>

          {datos.profesionales_tope !== null && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm">
                <span>Profesionales</span>
                <span className="tabular-nums font-medium">
                  {datos.profesionales_usados} de {datos.profesionales_tope}
                </span>
              </div>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full transition-all ${
                    datos.profesionales_usados >= datos.profesionales_tope
                      ? "bg-amber-500"
                      : "bg-primary"
                  }`}
                  style={{
                    width: `${Math.min(
                      100,
                      (datos.profesionales_usados / datos.profesionales_tope) * 100,
                    )}%`,
                  }}
                />
              </div>
              {datos.profesionales_usados >= datos.profesionales_tope && (
                <p className="mt-2 text-sm text-amber-700 dark:text-amber-500">
                  Llegaste al tope de tu plan. Para sumar a alguien más,
                  cambiá de plan o dá de baja a quien ya no trabaja acá.
                </p>
              )}
            </div>
          )}

          {datos.grilla.length > 0 && (
            <div className="mt-5 grid gap-2.5 sm:grid-cols-3">
              {datos.grilla.map((p) => {
                const esElMio =
                  p.etiqueta.toLowerCase() ===
                  (datos.plan_etiqueta ?? "").toLowerCase();
                return (
                  <div
                    key={p.codigo}
                    className={`rounded-xl border p-3.5 ${
                      esElMio ? "border-primary bg-primary/5" : ""
                    }`}
                  >
                    <p className="flex items-center gap-1.5 text-sm font-semibold">
                      {p.etiqueta}
                      {esElMio && (
                        <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                          tu plan
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 text-lg font-bold tabular-nums">
                      {pesos(p.precio)}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {p.resumen}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Cómo pagar */}
      {hayCobro && (pagando || avisoPendiente || datos.estado !== "prueba") && (
        <section id="como-pagar" className="rounded-2xl border bg-card p-5 md:p-6">
          <h2 className="text-base font-bold" style={SYNE}>
            Cómo pagar
          </h2>

          {avisoPendiente && (
            <div className="mt-4 flex gap-3 rounded-xl border border-sky-500/40 bg-sky-500/10 p-3.5">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" />
              <div className="text-sm">
                <p className="font-medium">Tu pago está en proceso</p>
                <p className="mt-0.5 text-muted-foreground">
                  Nos avisaste que transferiste. Lo confirmamos dentro de las
                  próximas 24 horas hábiles y vas a ver el vencimiento
                  actualizado en esta misma pantalla. Mientras tanto tu cuenta
                  sigue funcionando normalmente.
                </p>
              </div>
            </div>
          )}

          {c.mp_checkout && (
            <div className="mt-4">
              <Button
                size="lg"
                className="w-full"
                disabled={yendoAMP}
                onClick={irAMercadoPago}
              >
                {yendoAMP ? "Abriendo Mercado Pago…" : "Pagar con Mercado Pago"}
              </Button>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Se acredita solo: apenas Mercado Pago nos confirma el pago, tu
                vencimiento se corre 30 días sin que tengas que avisar nada.
              </p>
            </div>
          )}

          {c.mp_link && (
            <a
              href={c.mp_link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-foreground px-4 py-3 text-sm font-semibold text-background"
            >
              Pagar con Mercado Pago
              <ExternalLink className="h-4 w-4" />
            </a>
          )}

          {hayTransferencia && (
            <div className="mt-4">
              <p className="mb-1 text-sm font-medium">Transferencia bancaria</p>
              <div className="divide-y rounded-xl border px-3.5">
                {c.alias && <FilaCopiable etiqueta="Alias" valor={c.alias} />}
                {c.cbu && <FilaCopiable etiqueta="CBU" valor={c.cbu} />}
                {c.titular && (
                  <div className="py-2.5">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Titular
                    </p>
                    <p className="text-sm font-medium">{c.titular}</p>
                  </div>
                )}
                {c.cuit && (
                  <div className="py-2.5">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      CUIT / CUIL
                    </p>
                    <p className="text-sm font-medium tabular-nums">{c.cuit}</p>
                  </div>
                )}
                {c.banco && (
                  <div className="py-2.5">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Banco
                    </p>
                    <p className="text-sm font-medium">{c.banco}</p>
                  </div>
                )}
              </div>
              <div className="mt-3 rounded-xl border bg-muted/40 p-3.5">
                <p className="text-sm font-medium">Cómo sigue</p>
                <ol className="mt-1.5 space-y-1 pl-4 text-sm text-muted-foreground">
                  <li className="list-decimal">Transferís a los datos de arriba.</li>
                  <li className="list-decimal">
                    Tocás <b>Ya transferí</b> acá abajo. Si querés, además nos
                    mandás el comprobante por WhatsApp.
                  </li>
                  <li className="list-decimal">
                    Lo confirmamos contra el banco y registramos el pago: tu
                    vencimiento se corre 30 días.
                  </li>
                </ol>
                <p className="mt-2 text-xs text-muted-foreground">
                  La verificación es manual, así que puede demorar unas horas.
                  Mientras tanto tu cuenta sigue funcionando: para eso están los{" "}
                  {datos.dias_prorroga} días de gracia.
                </p>
                {c.whatsapp && (
                  <a
                    href={`https://wa.me/${c.whatsapp}?text=${encodeURIComponent(
                      "Hola! Te paso el comprobante de la transferencia de Turnos360.",
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-flex items-center gap-2 rounded-lg border bg-background px-3.5 py-2 text-sm font-medium"
                  >
                    Mandar el comprobante
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}

                {!avisoPendiente && (
                  <div className="mt-4 border-t pt-3.5">
                    <p className="text-sm font-medium">¿Ya transferiste?</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Avisanos y lo confirmamos contra el banco. Si tenés el
                      número de operación a mano, ponelo: lo encontramos más
                      rápido.
                    </p>
                    <div className="mt-2.5 flex flex-col gap-2 sm:flex-row">
                      <Input
                        placeholder="N.º de operación (opcional)"
                        value={referencia}
                        onChange={(e) => setReferencia(e.target.value)}
                        maxLength={300}
                      />
                      <Button
                        variant="outline"
                        className="shrink-0"
                        disabled={avisando}
                        onClick={avisarQueTransferi}
                      >
                        {avisando ? "Avisando…" : "Ya transferí"}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Historial */}
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <h2 className="text-base font-bold" style={SYNE}>
          Historial de pagos
        </h2>
        {datos.pagos.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Todavía no hay pagos registrados. Cuando registremos el primero, va a
            aparecer acá.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Fecha</th>
                  <th className="pb-2 font-medium">Período</th>
                  <th className="pb-2 font-medium">Método</th>
                  <th className="pb-2 text-right font-medium">Monto</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {datos.pagos.map((p, i) => (
                  <tr key={`${p.fecha}-${i}`}>
                    <td className="py-2.5">{fechaCorta(p.fecha)}</td>
                    <td className="py-2.5 text-muted-foreground">
                      {p.periodo_desde
                        ? `${fechaCorta(p.periodo_desde)} — ${fechaCorta(p.periodo_hasta)}`
                        : "—"}
                    </td>
                    <td className="py-2.5 capitalize text-muted-foreground">
                      {p.metodo}
                    </td>
                    <td className="py-2.5 text-right font-semibold tabular-nums">
                      {pesos(p.monto)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
