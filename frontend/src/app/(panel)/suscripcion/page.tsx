"use client";

/**
 * PASO 1 — Mi suscripción (/suscripcion).
 *
 * En qué estado está, cuánto paga, hasta cuándo, qué pagó antes, y la grilla
 * para cambiar de plan. El objetivo sigue siendo que nunca tenga que escribir
 * para preguntar "¿cuándo me vence?".
 *
 * LO QUE YA NO ESTÁ ACÁ
 * ─────────────────────
 * Todo el circuito de cobro. Antes esta pantalla era una sola de 33 KB donde
 * convivían el estado, la grilla, el checkout de Mercado Pago, los datos de
 * transferencia y el aviso de pago, apareciendo y desapareciendo con cuatro
 * banderas de estado. Eso tenía un problema concreto y no estético: la sección
 * "Cómo pagar" SOLO se renderizaba si la empresa ya estaba por vencer, así que
 * durante la prueba el botón de comprar hacía scroll a un elemento que no
 * existía en el DOM. Alguien que quería pagar se quedaba sin camino, y del
 * intento no quedaba ni rastro.
 *
 * Ahora cada paso es una ruta:
 *
 *   /suscripcion                          1 · elegir plan   (esta pantalla)
 *   /suscripcion/cambiar                  2 · resumen
 *   /suscripcion/cambiar/pago             3 · medio de pago
 *   /suscripcion/cambiar/transferencia    4 · datos del banco
 *   /suscripcion/cambiar/comprobante      5 · avisar el pago
 *   /suscripcion/cambiar/listo            6 · confirmación
 *
 * El plan elegido viaja en el `?plan=` de la URL, así el botón "atrás", el F5
 * y el volver del checkout caen donde corresponde.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  AlertTriangle,
  Clock,
  CreditCard,
  ExternalLink,
} from "lucide-react";

import { sincronizarDebitoAutomatico } from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import { WA_LINK_ENTERPRISE } from "@/lib/contacto";
import { DebitoAutomatico } from "./debito-automatico";
import {
  Cargando,
  ESTILO_ESTADO,
  SYNE,
  fechaCorta,
  fechaLarga,
  miPrecioActual,
  pesos,
  useSuscripcion,
} from "./_suscripcion";

export default function SuscripcionPage() {
  const router = useRouter();
  const { datos, cargando, cargar } = useSuscripcion();

  /**
   * La vuelta del checkout de Mercado Pago.
   *
   * EL PROBLEMA QUE RESUELVE, que es de confianza y no técnico: el dueño pone
   * la tarjeta, Mercado Pago lo devuelve acá, y nuestra fila todavía dice
   * `pending` porque el webhook no llegó. La pantalla le diría «te falta poner
   * la tarjeta» justo después de que la puso. La persona hizo exactamente lo
   * que le pedimos y le contestamos que no lo hizo.
   *
   * Al volver con `?debito=listo` se le pregunta a Mercado Pago en el acto y
   * se limpia el parámetro de la URL, para que un F5 más tarde no vuelva a
   * disparar la consulta.
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
        // Que Mercado Pago no conteste no puede romper la vuelta: se recarga
        // igual y, si todavía dice "pending", el webhook lo va a resolver.
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

  if (cargando || !datos) return <Cargando />;

  const est = ESTILO_ESTADO[datos.estado] ?? ESTILO_ESTADO.sin_vencimiento;
  // LA CUOTA VIENE RESUELTA DEL SERVIDOR, y esta pantalla no la vuelve a
  // calcular. Antes acá se mezclaba `precio_mensual` —una foto del precio de
  // lista tomada el día del alta— con la grilla que se dibuja más abajo, y
  // los dos números se contradecían en la misma pantalla: así fue como
  // apareció «$14.990» arriba de una grilla que decía $13.900.
  const precioAPagar = datos.cuota;
  // El precio del plan que tiene hoy. Es lo que decide si cada botón dice
  // "Pasar a" o "Bajar a" — se compara por PRECIO y no por el orden de la
  // grilla, igual que en el backend, para que digan lo mismo siempre.
  const miPrecio = miPrecioActual(datos);
  const c = datos.cobro;
  const hayCobro =
    Boolean(c.cbu || c.alias) || Boolean(c.mp_link) || c.mp_checkout;

  /** Entra al circuito. Sin plan = pagar el que ya tiene. */
  function irAlCircuito(plan?: string) {
    router.push(plan ? `/suscripcion/cambiar?plan=${plan}` : "/suscripcion/cambiar/pago");
  }

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
              {pesos(datos.cuota ?? datos.ultimo_monto)}
            </p>
            {datos.cuota === null && datos.ultimo_monto !== null && (
              <p className="text-xs text-muted-foreground">según tu último pago</p>
            )}
            {datos.precio_pactado && (
              <p className="text-xs text-muted-foreground">tu precio acordado</p>
            )}
          </div>
        </div>

        {datos.estado === "prueba" && (
          <p className="mt-4 text-sm">
            {/* El precio que se promete es el del PLAN DE ENTRADA, que es a
                lo que cae quien no elige nada. El de lista puede tener una
                promo encima y prometería un número que después no es. */}
            Estás usando Turnos360 gratis, con todas las funciones. Cuando
            termine la prueba podés seguir desde acá
            {datos.precio_entrada ? ` desde ${pesos(datos.precio_entrada)} por mes` : ""}
            , sin que nadie tenga que hacer nada. Durante la prueba no te
            cobramos ni te pedimos tarjeta.
          </p>
        )}

        {datos.estado === "activa" && datos.corte && !datos.debito && (
          <p className="mt-4 text-sm">
            {/* Solo si NO tiene débito automático. A quien paga solo, contarle
                el plazo de gracia es información que no necesita y que
                además suena a advertencia. */}
            Después del vencimiento tenés{" "}
            <strong>
              {datos.dias_prorroga} día{datos.dias_prorroga === 1 ? "" : "s"} de
              gracia
            </strong>{" "}
            para pagar sin que se corte nada: tu servicio sigue andando hasta el{" "}
            <strong>{fechaLarga(datos.corte)}</strong>.
          </p>
        )}

        {datos.estado === "prorroga" && (
          <p className="mt-4 flex items-start gap-2 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Tu cuenta sigue funcionando con normalidad. Tenés tiempo de
              pagar hasta el <strong>{fechaLarga(datos.corte)}</strong>; pasada
              esa fecha, tu página deja de tomar reservas nuevas. Tu agenda,
              tus clientes y los turnos ya tomados no se tocan.
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
            {/* En prueba manda a ELEGIR (la grilla está acá abajo); con un
                plan ya elegido, entra derecho al paso 3 a pagar el que tiene.
                Antes este botón hacía scroll a una sección que durante la
                prueba ni siquiera existía en el DOM. */}
            <Button
              size="lg"
              onClick={() =>
                datos.estado === "prueba"
                  ? document
                      .getElementById("planes")
                      ?.scrollIntoView({ behavior: "smooth", block: "start" })
                  : irAlCircuito()
              }
            >
              {datos.estado === "prueba" ? "Elegir mi plan" : "Pagar este mes"}
            </Button>
            {precioAPagar !== null && (
              <span className="text-sm text-muted-foreground">
                {pesos(precioAPagar)} por mes
              </span>
            )}
          </div>
        )}
      </section>

      {/* EL DÉBITO AUTOMÁTICO VA ACÁ, pegado al estado y arriba de todo el
          resto. Es la opción que le saca trabajo a los dos lados y la que
          queremos que elija. */}
      <DebitoAutomatico datos={datos} onCambio={cargar} />

      {/* Qué incluye tu plan, y cuánto estás usando.
          El dueño tiene que ver que se está quedando sin lugar antes de
          chocarse con el error al cargar el profesional número cuatro. */}
      {datos.plan_etiqueta && (
        <section id="planes" className="rounded-2xl border bg-card p-5 md:p-6">
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

          {/* La baja anotada. Va ARRIBA de la grilla y no abajo: es el estado
              más importante de la pantalla para quien la pidió, y quien se
              arrepintió tiene que encontrar cómo deshacerla sin buscar. */}
          {datos.plan_programado && (
            <div className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-amber-400/50 bg-amber-50 p-3.5 text-sm dark:border-amber-700/50 dark:bg-amber-950/40">
              <Clock className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
              <p className="min-w-0 flex-1 text-amber-900 dark:text-amber-200">
                El mes que ya pagaste lo usás entero: seguís en{" "}
                <b>{datos.plan_etiqueta}</b>
                {datos.vence ? ` hasta el ${datos.vence}` : ""} y ahí pasás a{" "}
                <b>{datos.plan_programado_etiqueta}</b>.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => irAlCircuito(datos.plan_codigo)}
              >
                Seguir en {datos.plan_etiqueta}
              </Button>
            </div>
          )}

          {datos.grilla.length > 0 && (
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {datos.grilla.map((p) => {
                const esElMio = p.codigo === datos.plan_codigo;
                return (
                  <div
                    key={p.codigo}
                    className={`flex flex-col rounded-xl border p-4 ${
                      esElMio ? "border-primary/60 bg-primary/5" : ""
                    }`}
                  >
                    <p className="flex flex-wrap items-center gap-1.5 text-sm font-semibold">
                      {p.etiqueta}
                      {esElMio && (
                        <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-semibold text-primary">
                          Tu plan
                        </span>
                      )}
                    </p>

                    <p className="mt-1 text-lg font-bold tabular-nums">
                      {p.a_convenir ? "A convenir" : pesos(p.precio)}
                    </p>
                    <p className="text-xs text-muted-foreground">{p.resumen}</p>

                    <p className="mt-2 flex-1 text-xs text-muted-foreground">
                      {p.para_quien}
                    </p>

                    <div className="mt-3">
                      {p.a_convenir ? (
                        /* Enterprise no se contrata online: los cupos y el
                           precio se arman con cada cliente. */
                        <a
                          href={WA_LINK_ENTERPRISE}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold transition-colors hover:bg-muted"
                        >
                          Hablemos <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : esElMio && !datos.plan_programado ? (
                        <p className="py-2 text-center text-xs text-muted-foreground">
                          Es el que tenés
                        </p>
                      ) : (
                        <Button
                          size="sm"
                          variant={p.precio > (miPrecio ?? 0) ? "default" : "outline"}
                          className="w-full"
                          onClick={() => irAlCircuito(p.codigo)}
                        >
                          {esElMio
                            ? `Seguir en ${p.etiqueta}`
                            : p.precio > (miPrecio ?? 0)
                              ? `Pasar a ${p.etiqueta}`
                              : `Bajar a ${p.etiqueta}`}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
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
