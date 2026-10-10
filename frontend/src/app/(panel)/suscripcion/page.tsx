"use client";

/**
 * Mi suscripción · Resumen (/suscripcion).
 *
 * En qué estado está, cuánto paga, hasta cuándo, con qué paga y qué hacer
 * ahora. El detalle vive en sus pestañas (planes, pagos, actividad, uso).
 *
 * EL ESTADO LO DECIDE EL SERVIDOR (core/estados_suscripcion.py) y llega con
 * su etiqueta y su tono. Esta pantalla no vuelve a interpretar fechas: pinta.
 * El MÉTODO de pago y el ESTADO del pago van separados.
 *
 * Las vueltas de Mercado Pago (?debito=listo, ?pago=…) caen acá.
 */

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  History,
  Layers,
  Receipt,
} from "lucide-react";

import { sincronizarDebitoAutomatico } from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import { DebitoAutomatico } from "./debito-automatico";
import { BadgeEstado, Cargando, SYNE, estiloDe, fechaCorta, fechaLarga, pesos, useSuscripcion } from "./_suscripcion";
import { Avisos, Dato, ESTADO_PAGO, useReactivar } from "./_componentes";

export default function SuscripcionResumen() {
  const router = useRouter();
  const { datos, cargando, cargar } = useSuscripcion();
  const reactivar = useReactivar(datos, cargar);

  /**
   * La vuelta del checkout de Mercado Pago (débito automático): nuestra fila
   * todavía dice `pending` porque el webhook no llegó. Se le pregunta a MP en
   * el acto y se limpia el parámetro para que un F5 no repita la consulta.
   */
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("debito") !== "listo") return;
    url.searchParams.delete("debito");
    window.history.replaceState(null, "", url.pathname + url.search);

    let vivo = true;
    (async () => {
      try {
        await sincronizarDebitoAutomatico();
      } catch {
        // Que MP no conteste no puede romper la vuelta: el webhook lo resuelve.
      }
      if (vivo) {
        await cargar();
        toast.success("Listo. Tu suscripción quedó activada.");
      }
    })();
    return () => {
      vivo = false;
    };
  }, [cargar]);

  /** Vuelta del Checkout Pro (pago suelto): solo se informa, acredita el webhook. */
  useEffect(() => {
    const url = new URL(window.location.href);
    const pago = url.searchParams.get("pago");
    if (!pago) return;
    url.searchParams.delete("pago");
    window.history.replaceState(null, "", url.pathname + url.search);
    if (pago === "aprobado") toast.success("¡Pago recibido! En unos segundos se actualiza tu suscripción.");
    if (pago === "pendiente") toast.info("Tu pago quedó pendiente en Mercado Pago. Te avisamos cuando se acredite.");
    if (pago === "rechazado") toast.error("Mercado Pago rechazó el pago. Podés intentar con otro medio.");
  }, []);

  if (cargando || !datos) return <Cargando />;

  const c = datos.cobro;
  const hayCobro = Boolean(c.cbu || c.alias) || Boolean(c.mp_link) || c.mp_checkout;
  const est = estiloDe(datos.tono);
  const cancelada = datos.estado === "cancelada";
  const cancelPendiente = datos.estado === "cancelacion_programada";
  const suspendida = datos.estado === "suspendida";
  const debe = ["prorroga", "vencida", "prueba_vencida"].includes(datos.estado_base);
  const verPlanes = () => router.push("/suscripcion/planes");

  // ── Acción principal según el estado ──────────────────────────────────
  let principal: { texto: string; accion: () => void } | null = null;
  if (suspendida) principal = null;
  else if (cancelada || cancelPendiente) principal = { texto: "Reactivar suscripción", accion: reactivar };
  else if (datos.estado === "prueba" || datos.estado === "prueba_vencida")
    principal = { texto: "Elegir mi plan", accion: verPlanes };
  else if (datos.estado_pago === "info_solicitada")
    principal = { texto: "Responder", accion: () => router.push("/suscripcion/cambiar/comprobante") };
  // Con un pago ya informado o pendiente en MP no se ofrece pagar de nuevo:
  // es la forma más fácil de cobrar dos veces lo mismo.
  else if (hayCobro && !datos.aviso && datos.estado_pago !== "pendiente" && !datos.renovacion_automatica)
    principal = { texto: debe ? "Pagar ahora" : "Pagar este mes", accion: () => router.push("/suscripcion/cambiar/pago") };

  const estadoPago = ESTADO_PAGO[datos.estado_pago] ?? ESTADO_PAGO.al_dia;
  const puedeCambiar = !cancelada && !suspendida && datos.grilla.length > 0;

  return (
    <div className="space-y-6">
      <section className={`overflow-hidden rounded-2xl border ${est.borde}`}>
        <div className={`p-5 md:p-6 ${est.fondo}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Plan</p>
                <BadgeEstado etiqueta={datos.etiqueta} tono={datos.tono} />
              </div>
              <p className="mt-1 text-2xl font-extrabold md:text-3xl" style={SYNE}>
                {datos.estado === "prueba" ? "Prueba gratis" : datos.plan_etiqueta}
              </p>
              <p className={`mt-1 text-sm font-medium ${est.texto}`}>{datos.mensaje}</p>
            </div>
            <div className="text-left sm:text-right">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {datos.estado === "prueba" ? "Después de la prueba, desde" : "Cuota mensual"}
              </p>
              <p className="text-3xl font-extrabold tabular-nums" style={SYNE}>
                {datos.estado === "prueba" ? pesos(datos.precio_entrada) : pesos(datos.cuota ?? datos.ultimo_monto)}
              </p>
              {datos.precio_pactado && <p className="text-xs text-muted-foreground">tu precio acordado</p>}
            </div>
          </div>

          {(principal || puedeCambiar) && (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              {principal && (
                <Button size="lg" onClick={principal.accion}>
                  {principal.texto}
                </Button>
              )}
              {puedeCambiar && principal?.accion !== verPlanes && (
                <Button size="lg" variant="outline" onClick={verPlanes}>
                  Cambiar de plan
                </Button>
              )}
            </div>
          )}
        </div>

        <dl className="grid grid-cols-1 divide-y bg-card sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x">
          <Dato
            icono={<CalendarClock className="h-4 w-4" />}
            etiqueta={
              datos.estado === "prueba"
                ? "Fin de la prueba"
                : cancelPendiente
                  ? "Activa hasta"
                  : datos.renovacion_automatica
                    ? "Próxima renovación"
                    : "Próximo vencimiento"
            }
            valor={fechaLarga(datos.vence)}
            ayuda={
              datos.renovacion_automatica
                ? "Se cobra solo con débito automático"
                : cancelPendiente
                  ? "No se renueva"
                  : datos.vence && !cancelada
                    ? "Renovación manual"
                    : undefined
            }
          />
          <Dato icono={<CreditCard className="h-4 w-4" />} etiqueta="Método de pago" valor={datos.metodo_pago_etiqueta ?? "Sin definir"} />
          <Dato
            icono={<History className="h-4 w-4" />}
            etiqueta="Último pago"
            valor={datos.ultimo_pago ? pesos(datos.ultimo_pago.monto) : "—"}
            ayuda={datos.ultimo_pago ? `${fechaCorta(datos.ultimo_pago.fecha)} · ${datos.ultimo_pago.tipo}` : undefined}
          />
          <Dato
            icono={<CheckCircle2 className="h-4 w-4" />}
            etiqueta="Estado del pago"
            valor={<span className={estadoPago.clase}>{estadoPago.texto}</span>}
          />
        </dl>
      </section>

      <Avisos datos={datos} onReactivar={reactivar} />

      {/* El débito automático va pegado al estado: es la opción que le saca
          trabajo a los dos lados. Con la suscripción cancelada no se ofrece. */}
      {!cancelada && !cancelPendiente && !suspendida && <DebitoAutomatico datos={datos} onCambio={cargar} />}

      {/* ── Accesos directos a los apartados ─────────────────────────────── */}
      <section aria-label="Accesos directos" className="grid gap-3 sm:grid-cols-3">
        <Acceso
          href="/suscripcion/planes"
          icono={<Layers className="h-4 w-4" />}
          titulo="Planes"
          detalle={
            datos.plan_programado
              ? `Pasás a ${datos.plan_programado_etiqueta} el ${fechaCorta(datos.vence)}`
              : datos.estado === "prueba"
                ? "Elegí con cuál seguir"
                : `Estás en ${datos.plan_etiqueta}`
          }
        />
        <Acceso
          href="/suscripcion/pagos"
          icono={<Receipt className="h-4 w-4" />}
          titulo="Historial de pagos"
          detalle={
            datos.pagos.length === 0
              ? "Todavía no hay pagos"
              : `${datos.pagos.length} pago${datos.pagos.length === 1 ? "" : "s"} registrado${datos.pagos.length === 1 ? "" : "s"}`
          }
        />
        <Acceso
          href="/suscripcion/uso"
          icono={<BarChart3 className="h-4 w-4" />}
          titulo="Uso y límites"
          detalle={`${datos.uso.profesionales} de ${datos.topes.profesionales ?? "∞"} profesionales`}
        />
      </section>

      {!cancelada && !cancelPendiente && !suspendida && (
        <p className="text-sm text-muted-foreground">
          ¿Querés darte de baja?{" "}
          <Link href="/suscripcion/cancelar" className="font-medium text-foreground underline underline-offset-4">
            Cancelar suscripción
          </Link>
          . Seguís usando todo hasta el final del período y tus datos no se borran.
        </p>
      )}
    </div>
  );
}

function Acceso({
  href,
  icono,
  titulo,
  detalle,
}: {
  href: string;
  icono: React.ReactNode;
  titulo: string;
  detalle: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-3 rounded-2xl border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">{icono}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{titulo}</span>
        <span className="block truncate text-xs text-muted-foreground">{detalle}</span>
      </span>
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Link>
  );
}
