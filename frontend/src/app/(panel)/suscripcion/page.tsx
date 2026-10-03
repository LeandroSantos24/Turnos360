"use client";

/**
 * PASO 1 — Mi suscripción (/suscripcion).
 *
 * En qué estado está, cuánto paga, hasta cuándo, con qué paga, qué pagó antes,
 * cuánto usa del plan y la grilla para cambiar. El objetivo sigue siendo que
 * nunca tenga que escribir para preguntar "¿cuándo me vence?".
 *
 * EL ESTADO LO DECIDE EL SERVIDOR (core/estados_suscripcion.py) y llega con
 * su etiqueta y su tono. Esta pantalla no vuelve a interpretar fechas: pinta.
 * El MÉTODO de pago y el ESTADO del pago van separados — «Transferencia» no es
 * un estado, «En revisión» no es un método.
 *
 * El circuito de pago sigue en rutas propias (ver ./cambiar/*): el plan viaja
 * en `?plan=`, así el "atrás", el F5 y la vuelta del checkout caen bien.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  CreditCard,
  ExternalLink,
  History,
  Info,
  MessageSquareWarning,
  RotateCcw,
  XCircle,
} from "lucide-react";

import {
  cancelarSuscripcion,
  reactivarSuscripcion,
  sincronizarDebitoAutomatico,
  type MiSuscripcion,
} from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useConfirmar } from "@/components/confirmar";
import { WA_LINK_ENTERPRISE } from "@/lib/contacto";
import { DebitoAutomatico } from "./debito-automatico";
import {
  BadgeEstado,
  Cargando,
  SYNE,
  estiloDe,
  fechaCorta,
  fechaHora,
  fechaLarga,
  miPrecioActual,
  pesos,
  useSuscripcion,
} from "./_suscripcion";

const ESTADO_PAGO: Record<string, { texto: string; clase: string }> = {
  al_dia: { texto: "Al día", clase: "text-emerald-700 dark:text-emerald-400" },
  en_revision: { texto: "En revisión", clase: "text-sky-700 dark:text-sky-400" },
  info_solicitada: { texto: "Falta un dato", clase: "text-amber-700 dark:text-amber-400" },
  rechazado: { texto: "Rechazado", clase: "text-red-700 dark:text-red-400" },
  pendiente: { texto: "Pendiente de acreditación", clase: "text-amber-700 dark:text-amber-400" },
  adeuda: { texto: "Pendiente de pago", clase: "text-red-700 dark:text-red-400" },
};

export default function SuscripcionPage() {
  const router = useRouter();
  const { datos, cargando, cargar } = useSuscripcion();
  const confirmar = useConfirmar();
  const [cancelando, setCancelando] = useState(false);

  /**
   * La vuelta del checkout de Mercado Pago (débito automático).
   *
   * El dueño pone la tarjeta, MP lo devuelve acá y nuestra fila todavía dice
   * `pending` porque el webhook no llegó. Se le pregunta a MP en el acto y se
   * limpia el parámetro para que un F5 no repita la consulta.
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

  const miPrecio = miPrecioActual(datos);
  const c = datos.cobro;
  const hayCobro = Boolean(c.cbu || c.alias) || Boolean(c.mp_link) || c.mp_checkout;
  const est = estiloDe(datos.tono);
  const cancelada = datos.estado === "cancelada";
  const cancelPendiente = datos.estado === "cancelacion_programada";
  const suspendida = datos.estado === "suspendida";
  const debe = ["prorroga", "vencida", "prueba_vencida"].includes(datos.estado_base);

  function irAlCircuito(plan?: string) {
    router.push(plan ? `/suscripcion/cambiar?plan=${plan}` : "/suscripcion/cambiar/pago");
  }

  function verPlanes() {
    document.getElementById("planes")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function reactivar() {
    if (!datos) return;
    const hasta = datos.cancelacion?.activa_hasta;
    const ok = await confirmar({
      titulo: "¿Reactivar tu suscripción?",
      descripcion: cancelada
        ? `Se deshace la cancelación. Para volver a tomar reservas por la web vas a tener que pagar la cuota de ${pesos(datos.cuota)}.`
        : `Tu plan ${datos.plan_etiqueta} sigue activo${hasta ? ` después del ${fechaLarga(hasta)}` : ""} y se renueva normalmente.`,
      textoAccion: "Sí, reactivar",
      textoCancelar: "Volver",
    });
    if (!ok) return;
    try {
      const r = await reactivarSuscripcion();
      toast.success(r.detalle);
      await cargar();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo reactivar");
    }
  }

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
    principal = { texto: debe ? "Pagar ahora" : "Pagar este mes", accion: () => irAlCircuito() };

  const estadoPago = ESTADO_PAGO[datos.estado_pago] ?? ESTADO_PAGO.al_dia;

  return (
    <div className="w-full space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header>
        <h1 className="titulo-pantalla">
          Mi <b>suscripción</b>.
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Tu plan, tus pagos y lo que estás usando.
        </p>
      </header>

      {/* ── Resumen: plan, estado, precio y las cuatro cosas que se preguntan ── */}
      <section className={`overflow-hidden rounded-2xl border ${est.borde}`}>
        <div className={`p-5 md:p-6 ${est.fondo}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Plan
                </p>
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
                {datos.estado === "prueba"
                  ? pesos(datos.precio_entrada)
                  : pesos(datos.cuota ?? datos.ultimo_monto)}
              </p>
              {datos.precio_pactado && (
                <p className="text-xs text-muted-foreground">tu precio acordado</p>
              )}
            </div>
          </div>

          {(principal || (!cancelada && !suspendida && datos.grilla.length > 0)) && (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              {principal && (
                <Button size="lg" onClick={principal.accion}>
                  {principal.texto}
                </Button>
              )}
              {!cancelada && !suspendida && datos.grilla.length > 0 && principal?.accion !== verPlanes && (
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
          <Dato
            icono={<CreditCard className="h-4 w-4" />}
            etiqueta="Método de pago"
            valor={datos.metodo_pago_etiqueta ?? "Sin definir"}
          />
          <Dato
            icono={<History className="h-4 w-4" />}
            etiqueta="Último pago"
            valor={datos.ultimo_pago ? pesos(datos.ultimo_pago.monto) : "—"}
            ayuda={
              datos.ultimo_pago
                ? `${fechaCorta(datos.ultimo_pago.fecha)} · ${datos.ultimo_pago.tipo}`
                : undefined
            }
          />
          <Dato
            icono={<CheckCircle2 className="h-4 w-4" />}
            etiqueta="Estado del pago"
            valor={<span className={estadoPago.clase}>{estadoPago.texto}</span>}
          />
        </dl>
      </section>

      {/* ── Avisos según el estado ────────────────────────────────────────── */}
      <Avisos datos={datos} onReactivar={reactivar} />

      {/* EL DÉBITO AUTOMÁTICO VA ACÁ, pegado al estado: es la opción que le
          saca trabajo a los dos lados. Con la suscripción cancelada no se
          ofrece: sería invitar a cobrar algo que pidió dar de baja. */}
      {!cancelada && !cancelPendiente && !suspendida && (
        <DebitoAutomatico datos={datos} onCambio={cargar} />
      )}

      {/* ── Uso del plan ─────────────────────────────────────────────────── */}
      {datos.plan_etiqueta && (
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-bold" style={SYNE}>
              Lo que estás usando
            </h2>
            <span className="text-sm text-muted-foreground">{datos.plan_resumen}</span>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <BarraUso etiqueta="Profesionales" usados={datos.uso.profesionales} tope={datos.topes.profesionales} />
            <BarraUso etiqueta="Usuarios con acceso" usados={datos.uso.usuarios} tope={datos.topes.usuarios} />
            <BarraUso etiqueta="Sucursales" usados={datos.uso.sucursales} tope={datos.topes.sucursales} />
          </div>
        </section>
      )}

      {/* ── Planes ───────────────────────────────────────────────────────── */}
      {datos.grilla.length > 0 && !suspendida && (
        <section id="planes" className="scroll-mt-4 rounded-2xl border bg-card p-5 md:p-6">
          <h2 className="text-base font-bold" style={SYNE}>
            Planes
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Subir de plan se paga al momento y suma 30 días. Bajar se aplica al
            terminar el período que ya pagaste.
          </p>

          {datos.plan_programado && (
            <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-amber-400/50 bg-amber-50 p-3.5 text-sm dark:border-amber-700/50 dark:bg-amber-950/40">
              <Clock className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
              <p className="min-w-0 flex-1 text-amber-900 dark:text-amber-200">
                Seguís en <b>{datos.plan_etiqueta}</b>
                {datos.vence ? ` hasta el ${fechaLarga(datos.vence)}` : ""} y ahí pasás a{" "}
                <b>{datos.plan_programado_etiqueta}</b>.
              </p>
              <Button size="sm" variant="outline" onClick={() => irAlCircuito(datos.plan_codigo)}>
                Seguir en {datos.plan_etiqueta}
              </Button>
            </div>
          )}

          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {datos.grilla.map((p) => {
              const esElMio = p.codigo === datos.plan_codigo && datos.estado !== "prueba";
              const sube = p.precio > (miPrecio ?? 0);
              return (
                <div
                  key={p.codigo}
                  className={`relative flex flex-col rounded-xl border p-4 ${
                    esElMio ? "border-primary ring-1 ring-primary/40 bg-primary/5" : ""
                  }`}
                >
                  {esElMio && (
                    <span className="absolute -top-2.5 left-4 rounded-full bg-primary px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary-foreground">
                      Tu plan
                    </span>
                  )}
                  <p className="text-sm font-semibold">{p.etiqueta}</p>
                  <p className="mt-1 text-lg font-bold tabular-nums">
                    {p.a_convenir ? "A convenir" : pesos(p.precio)}
                    {!p.a_convenir && (
                      <span className="ml-1 text-xs font-normal text-muted-foreground">/mes</span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">{p.resumen}</p>
                  <p className="mt-2 flex-1 text-xs text-muted-foreground">{p.para_quien}</p>

                  <div className="mt-3">
                    {p.a_convenir ? (
                      <a
                        href={WA_LINK_ENTERPRISE}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold transition-colors hover:bg-muted"
                      >
                        Hablemos <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : esElMio && !datos.plan_programado ? (
                      <p className="py-2 text-center text-xs text-muted-foreground">Es el que tenés</p>
                    ) : cancelada ? (
                      <p className="py-2 text-center text-xs text-muted-foreground">
                        Reactivá para cambiar
                      </p>
                    ) : (
                      <Button
                        size="sm"
                        variant={sube || datos.estado === "prueba" ? "default" : "outline"}
                        className="w-full"
                        onClick={() => irAlCircuito(p.codigo)}
                      >
                        {esElMio
                          ? `Seguir en ${p.etiqueta}`
                          : datos.estado === "prueba" || datos.estado === "prueba_vencida"
                            ? `Elegir ${p.etiqueta}`
                            : sube
                              ? `Pasar a ${p.etiqueta}`
                              : `Bajar a ${p.etiqueta}`}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Historial de pagos ──────────────────────────────────────────── */}
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <h2 className="text-base font-bold" style={SYNE}>
          Historial de pagos
        </h2>
        {datos.pagos.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Todavía no hay pagos registrados. Cuando registremos el primero, va a aparecer acá.
          </p>
        ) : (
          <>
            {/* Celular: tarjetas. Una tabla de 5 columnas en 390px no se lee. */}
            <ul className="mt-4 divide-y sm:hidden">
              {datos.pagos.map((p, i) => (
                <li key={`${p.fecha}-${i}`} className="flex items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {p.tipo_etiqueta ?? "Pago"}
                      {p.plan_etiqueta ? ` · ${p.plan_etiqueta}` : ""}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {fechaCorta(p.fecha)} · {p.metodo}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-semibold tabular-nums">{pesos(p.monto)}</p>
                </li>
              ))}
            </ul>
            <div className="mt-4 hidden overflow-x-auto sm:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-2 font-medium">Fecha</th>
                    <th className="pb-2 font-medium">Concepto</th>
                    <th className="pb-2 font-medium">Período</th>
                    <th className="pb-2 font-medium">Método</th>
                    <th className="pb-2 text-right font-medium">Monto</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {datos.pagos.map((p, i) => (
                    <tr key={`${p.fecha}-${i}`}>
                      <td className="py-2.5 whitespace-nowrap">{fechaCorta(p.fecha)}</td>
                      <td className="py-2.5">
                        {p.tipo_etiqueta ?? "Pago"}
                        {p.plan_etiqueta && (
                          <span className="text-muted-foreground"> · {p.plan_etiqueta}</span>
                        )}
                      </td>
                      <td className="py-2.5 text-muted-foreground">
                        {p.periodo_desde
                          ? `${fechaCorta(p.periodo_desde)} — ${fechaCorta(p.periodo_hasta)}`
                          : "—"}
                      </td>
                      <td className="py-2.5 text-muted-foreground">{p.metodo}</td>
                      <td className="py-2.5 text-right font-semibold tabular-nums">{pesos(p.monto)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* ── Actividad ───────────────────────────────────────────────────── */}
      {datos.actividad.length > 0 && (
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <h2 className="text-base font-bold" style={SYNE}>
            Actividad de tu suscripción
          </h2>
          <ol className="mt-4 space-y-3">
            {datos.actividad.map((ev, i) => (
              <li key={i} className="flex gap-3">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm">
                    <span className="font-medium">{ev.titulo}</span>
                    {ev.detalle && <span className="text-muted-foreground"> · {ev.detalle}</span>}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {fechaHora(ev.fecha)} · {ev.quien}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* ── Cancelar: al final, sin esconderlo ──────────────────────────── */}
      {!cancelada && !cancelPendiente && !suspendida && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed p-5 md:p-6">
          <div className="min-w-0">
            <p className="text-sm font-medium">Cancelar suscripción</p>
            <p className="text-sm text-muted-foreground">
              Seguís usando todo hasta el final del período. Tus datos no se borran.
            </p>
          </div>
          <Button variant="outline" onClick={() => setCancelando(true)}>
            Cancelar suscripción
          </Button>
        </section>
      )}

      <DialogCancelar
        abierto={cancelando}
        datos={datos}
        onCerrar={() => setCancelando(false)}
        onListo={cargar}
      />
    </div>
  );
}

function Dato({
  icono,
  etiqueta,
  valor,
  ayuda,
}: {
  icono: React.ReactNode;
  etiqueta: string;
  valor: React.ReactNode;
  ayuda?: string;
}) {
  return (
    <div className="p-4 md:p-5">
      <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
        {icono}
        {etiqueta}
      </dt>
      <dd className="mt-1 text-sm font-semibold">{valor}</dd>
      {ayuda && <dd className="text-xs text-muted-foreground">{ayuda}</dd>}
    </div>
  );
}

function BarraUso({ etiqueta, usados, tope }: { etiqueta: string; usados: number; tope: number | null }) {
  const pasado = tope !== null && usados > tope;
  // Con tope 1 (un solo local) estar «lleno» es lo normal, no un aviso.
  const lleno = pasado || (tope !== null && tope > 1 && usados >= tope);
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span>{etiqueta}</span>
        <span className="font-medium tabular-nums">
          {usados} {tope === null ? "· sin tope" : `de ${tope}`}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all ${
            pasado ? "bg-red-500" : lleno ? "bg-amber-500" : "bg-primary"
          }`}
          style={{ width: tope === null ? "12%" : `${Math.min(100, (usados / Math.max(tope, 1)) * 100)}%` }}
        />
      </div>
      {lleno && (
        <p className={`mt-1.5 text-xs ${pasado ? "text-red-700 dark:text-red-400" : "text-amber-700 dark:text-amber-500"}`}>
          {pasado ? "Usás más de lo que permite tu plan." : "Llegaste al tope de tu plan."}
        </p>
      )}
    </div>
  );
}

/** Los carteles que explican el estado en palabras del negocio. */
function Avisos({ datos, onReactivar }: { datos: MiSuscripcion; onReactivar: () => void }) {
  const router = useRouter();
  const items: React.ReactNode[] = [];

  if (datos.estado === "suspendida") {
    items.push(
      <Cartel key="susp" tono="error" icono={<XCircle className="h-4 w-4" />} titulo="Tu cuenta está suspendida">
        Escribinos para reactivarla. Tus datos, tu agenda y tus clientes están intactos.
      </Cartel>,
    );
  }

  if (datos.aviso?.estado === "info_solicitada") {
    items.push(
      <Cartel
        key="info"
        tono="aviso"
        icono={<MessageSquareWarning className="h-4 w-4" />}
        titulo="Necesitamos un dato para confirmar tu pago"
        accion={<Button size="sm" onClick={() => router.push("/suscripcion/cambiar/comprobante")}>Responder</Button>}
      >
        {datos.aviso.mensaje_admin}
      </Cartel>,
    );
  } else if (datos.aviso) {
    items.push(
      <Cartel key="rev" tono="info" icono={<Clock className="h-4 w-4" />} titulo="Tu pago está en revisión">
        Informaste una transferencia
        {datos.aviso.monto ? ` de ${pesos(datos.aviso.monto)}` : ""}
        {datos.aviso.plan_etiqueta ? ` (${datos.aviso.plan_etiqueta})` : ""}. La confirmamos dentro
        de las próximas 24 horas hábiles. Mientras tanto tu cuenta sigue funcionando.
      </Cartel>,
    );
  }

  if (datos.aviso_rechazado) {
    items.push(
      <Cartel
        key="rech"
        tono="error"
        icono={<XCircle className="h-4 w-4" />}
        titulo="No pudimos confirmar tu transferencia"
        accion={<Button size="sm" variant="outline" onClick={() => router.push("/suscripcion/cambiar/pago")}>Volver a pagar</Button>}
      >
        {datos.aviso_rechazado.motivo ?? "No la encontramos en el banco."} Si ya pagaste, escribinos con el comprobante.
      </Cartel>,
    );
  }

  if (datos.ultimo_intento?.estado === "rechazado" && !datos.aviso) {
    items.push(
      <Cartel
        key="mprech"
        tono="error"
        icono={<XCircle className="h-4 w-4" />}
        titulo="Mercado Pago rechazó tu pago"
        accion={<Button size="sm" variant="outline" onClick={() => router.push("/suscripcion/cambiar/pago")}>Intentar de nuevo</Button>}
      >
        No se cobró nada. Podés probar con otra tarjeta o pagar por transferencia.
      </Cartel>,
    );
  } else if (datos.ultimo_intento?.estado === "pendiente") {
    items.push(
      <Cartel key="mppend" tono="aviso" icono={<Clock className="h-4 w-4" />} titulo="Tu pago está pendiente en Mercado Pago">
        Cuando Mercado Pago lo acredite, tu suscripción se actualiza sola.
      </Cartel>,
    );
  }

  if (datos.estado === "cancelacion_programada" && datos.cancelacion) {
    items.push(
      <Cartel
        key="canc"
        tono="aviso"
        icono={<CalendarClock className="h-4 w-4" />}
        titulo={`Tu suscripción termina el ${fechaLarga(datos.cancelacion.activa_hasta)}`}
        accion={<Button size="sm" onClick={onReactivar}><RotateCcw className="mr-1.5 h-3.5 w-3.5" />Reactivar</Button>}
      >
        Hasta esa fecha seguís usando todo normalmente. Después no se renueva y tu
        página deja de tomar reservas. Tus datos no se borran.
      </Cartel>,
    );
  }

  if (datos.estado === "cancelada") {
    items.push(
      <Cartel
        key="cancd"
        tono="neutro"
        icono={<Info className="h-4 w-4" />}
        titulo="Tu suscripción está cancelada"
        accion={<Button size="sm" onClick={onReactivar}>Reactivar</Button>}
      >
        Tu agenda, tus clientes y tu historial siguen guardados. Podés volver cuando quieras.
      </Cartel>,
    );
  }

  if (datos.estado_base === "prorroga" && datos.estado !== "en_revision") {
    items.push(
      <Cartel key="gracia" tono="aviso" icono={<AlertTriangle className="h-4 w-4" />} titulo="Estás en el período de gracia">
        Tu suscripción venció, pero todo sigue funcionando hasta el{" "}
        <b>{fechaLarga(datos.corte)}</b>. Pasada esa fecha tu página deja de tomar reservas
        nuevas. Tu agenda, tus clientes y los turnos ya tomados no se tocan.
      </Cartel>,
    );
  }

  if ((datos.estado_base === "vencida" || datos.estado_base === "prueba_vencida") && !datos.reservas_abiertas) {
    items.push(
      <Cartel key="venc" tono="error" icono={<AlertTriangle className="h-4 w-4" />} titulo="Tu página no está tomando reservas">
        {datos.estado_base === "prueba_vencida" ? "Terminó tu prueba." : "Tu suscripción está vencida."}{" "}
        Elegí un plan o pagá la cuota y se reactiva al instante. Tus datos están intactos.
      </Cartel>,
    );
  } else if (datos.estado_base === "prueba_vencida") {
    items.push(
      <Cartel key="pv" tono="aviso" icono={<AlertTriangle className="h-4 w-4" />} titulo="Terminó tu prueba">
        Tenés hasta el <b>{fechaLarga(datos.corte)}</b> para elegir un plan sin que se corte nada.
      </Cartel>,
    );
  }

  if (datos.estado === "activa" && datos.corte && !datos.renovacion_automatica && (datos.dias_restantes ?? 99) <= 7) {
    items.push(
      <Cartel key="prox" tono="info" icono={<Info className="h-4 w-4" />} titulo="Tu suscripción vence pronto">
        Después del vencimiento tenés {datos.dias_prorroga} días de gracia: tu servicio sigue
        andando hasta el <b>{fechaLarga(datos.corte)}</b>.
      </Cartel>,
    );
  }

  if (items.length === 0) return null;
  return <div className="space-y-3">{items}</div>;
}

function Cartel({
  tono,
  icono,
  titulo,
  accion,
  children,
}: {
  tono: string;
  icono: React.ReactNode;
  titulo: string;
  accion?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const e = estiloDe(tono);
  return (
    <div className={`flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center ${e.fondo} ${e.borde}`}>
      <div className="flex min-w-0 flex-1 gap-3">
        <span className={`mt-0.5 shrink-0 ${e.texto}`}>{icono}</span>
        <div className="min-w-0 text-sm">
          <p className="font-semibold">{titulo}</p>
          {children && <p className="mt-0.5 text-muted-foreground">{children}</p>}
        </div>
      </div>
      {accion && <div className="shrink-0 pl-7 sm:pl-0">{accion}</div>}
    </div>
  );
}

const MOTIVOS = [
  "Es muy caro para mí",
  "No lo estoy usando",
  "Me falta una función",
  "Me cambio a otro sistema",
  "Cierro o pauso el negocio",
];

/**
 * Cancelación en DOS pasos: primero qué va a pasar (y por qué se va), después
 * la confirmación con la fecha concreta. Nada se corta en el momento.
 */
function DialogCancelar({
  abierto,
  datos,
  onCerrar,
  onListo,
}: {
  abierto: boolean;
  datos: MiSuscripcion;
  onCerrar: () => void;
  onListo: () => Promise<void> | void;
}) {
  const [paso, setPaso] = useState<1 | 2>(1);
  const [motivo, setMotivo] = useState<string | null>(null);
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setPaso(1);
      setMotivo(null);
      setComentario("");
    }
  }, [abierto]);

  const hasta = datos.vence;
  const enPrueba = datos.estado === "prueba";

  async function confirmarCancelacion() {
    setEnviando(true);
    try {
      const texto = [motivo, comentario.trim()].filter(Boolean).join(" · ") || null;
      const r = await cancelarSuscripcion(texto);
      toast.success(r.detalle);
      onCerrar();
      await onListo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo cancelar");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(v) => !v && !enviando && onCerrar()}>
      <DialogContent className="max-w-lg">
        {paso === 1 ? (
          <>
            <DialogHeader>
              <DialogTitle>Cancelar tu suscripción</DialogTitle>
              <DialogDescription>Antes de confirmar, esto es lo que pasa:</DialogDescription>
            </DialogHeader>
            <ul className="space-y-2 text-sm">
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                {hasta
                  ? `Seguís usando ${enPrueba ? "la prueba" : `el plan ${datos.plan_etiqueta}`} hasta el ${fechaLarga(hasta)}.`
                  : "La cancelación se aplica en el momento."}
              </li>
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                Tus clientes, turnos e historial NO se borran.
              </li>
              <li className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                Después de esa fecha no se renueva y tu página deja de tomar reservas.
              </li>
              {datos.debito && (
                <li className="flex gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  Se corta el débito automático: no se te cobra nada más.
                </li>
              )}
            </ul>
            <div className="space-y-2">
              <p className="text-sm font-medium">¿Por qué te vas? (opcional)</p>
              <div className="flex flex-wrap gap-2">
                {MOTIVOS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMotivo(motivo === m ? null : m)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      motivo === m ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <Textarea
                placeholder="Contanos más si querés"
                value={comentario}
                maxLength={200}
                onChange={(e) => setComentario(e.target.value)}
              />
            </div>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button variant="outline" onClick={onCerrar}>
                Mantener mi suscripción
              </Button>
              <Button variant="destructive" onClick={() => setPaso(2)}>
                Continuar con la cancelación
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>¿Confirmás la cancelación?</DialogTitle>
              <DialogDescription>
                {hasta
                  ? `Tu ${enPrueba ? "prueba" : `plan ${datos.plan_etiqueta}`} queda activo hasta el ${fechaLarga(hasta)} y después no se renueva. Podés reactivarla cuando quieras.`
                  : "Tu suscripción se cancela ahora. Podés reactivarla cuando quieras."}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button variant="outline" onClick={() => setPaso(1)} disabled={enviando}>
                Volver
              </Button>
              <Button variant="destructive" onClick={confirmarCancelacion} disabled={enviando}>
                {enviando ? "Cancelando…" : "Sí, cancelar suscripción"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
