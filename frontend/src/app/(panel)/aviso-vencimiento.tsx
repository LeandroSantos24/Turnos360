"use client";

/**
 * El cartel de «se está por vencer», arriba de todo el panel.
 *
 * POR QUÉ NO ALCANZA CON LA PANTALLA «MI SUSCRIPCIÓN»
 * ───────────────────────────────────────────────────
 * Porque nadie entra ahí. El dueño abre la agenda, atiende, cierra la caja y
 * se va: «Mi suscripción» es la pantalla que visita el día que quiere pagar,
 * no la que le avisa que tiene que pagar. Un aviso que vive solamente donde
 * hay que ir a buscarlo no es un aviso.
 *
 * Lo pidió así Leandro: «te sale un cartel se está por vencer». Este es el
 * cartel, y aparece en la agenda, en la caja y en todas las demás.
 *
 * LA ESCALERA, QUE ES LO QUE HACE QUE FUNCIONE
 * ────────────────────────────────────────────
 * Un cartel que dice siempre lo mismo se vuelve parte del fondo en una
 * semana. Este cambia de tono según cuánto falta, y cada escalón dice algo
 * distinto:
 *
 *   · faltan ≤ 7 días  → gris/ámbar, informativo. «Vence el 12.»
 *   · vence hoy        → ámbar. «Vence hoy.»
 *   · en gracia        → rojo, con la fecha del corte. Ahí sí urge.
 *   · vencida          → rojo, y ya no dice cuándo: dice qué se apagó.
 *   · cobro rebotado   → rojo, y es el único que aparece ESTANDO al día:
 *                        la tarjeta falló y todavía hay tiempo de arreglarlo.
 *
 * Antes de los 7 días no se muestra nada. Un cartel de cobranza colgado
 * veintitrés días por mes es ruido, y el precio del ruido lo paga el aviso
 * que sí importaba.
 *
 * A QUIÉN NO SE LE MUESTRA
 * ────────────────────────
 * · A quien está en período de prueba: todavía no le toca pagar, y un aviso
 *   de vencimiento en la prueba es la mejor forma de que no convierta.
 * · A quien tiene débito automático andando y sin fallas: se le cobra solo.
 *   Avisarle de un vencimiento que se va a resolver sin él es pedirle que se
 *   preocupe por algo que ya resolvió — y es exactamente lo contrario de lo
 *   que se le prometió al activarlo.
 * · A quien no es dueño: la cuota no es asunto de quien atiende.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertTriangle, CreditCard } from "lucide-react";

import { leerMiSuscripcion, type MiSuscripcion } from "@/lib/empresa-api";

/** Desde cuántos días antes empieza a avisar. */
const DIAS_DE_ANTICIPACION = 7;

type Aviso = {
  tono: "ambar" | "rojo";
  texto: React.ReactNode;
  accion: string;
};

/**
 * Qué cartel corresponde, o null si no corresponde ninguno.
 *
 * Se exporta para poder verificarla sin montar el componente: es una función
 * de datos a texto, y ese es justo el tipo de lógica que se rompe en silencio
 * cuando cambia la regla de negocio (la prórroga bajó de 10 días a 3).
 */
export function avisoDe(d: MiSuscripcion): Aviso | null {
  // En prueba no se avisa de vencimientos: no hay ninguno.
  if (d.estado === "prueba") return null;

  const deb = d.debito;
  const cobroRebotado = Boolean(deb && deb.cobros_fallidos > 0);

  // El débito automático andando resuelve el vencimiento sin el dueño. El
  // único caso en que igual hay que hablarle es cuando el cobro rebotó.
  if (deb && deb.estado === "authorized" && !cobroRebotado) return null;

  if (cobroRebotado) {
    return {
      tono: "rojo",
      texto: (
        <>
          <b>No pudimos cobrar tu cuota.</b> Mercado Pago va a reintentar, pero
          si querés que no se corte nada, revisá la tarjeta o pagá a mano.
        </>
      ),
      accion: "Revisar",
    };
  }

  if (d.estado === "vencida") {
    return {
      tono: "rojo",
      texto: (
        <>
          {/* Dice EXACTAMENTE lo que pasa, ni más ni menos. La versión
              anterior de este texto prometía que se apagaba la agenda entera,
              y no es cierto: lo único que se corta son las reservas nuevas
              por la web. Un cartel que exagera se descubre en un día y a
              partir de ahí no se le cree tampoco cuando dice la verdad. */}
          <b>Tu suscripción está vencida.</b> Tu página dejó de tomar reservas
          nuevas. Tu agenda, tus clientes y los turnos ya tomados están intactos.
        </>
      ),
      accion: "Pagar ahora",
    };
  }

  if (d.estado === "prorroga") {
    const quedan = d.dias_hasta_corte;
    return {
      tono: "rojo",
      texto: (
        <>
          <b>Tu suscripción venció.</b>{" "}
          {quedan !== null && quedan > 0 ? (
            <>
              Te {quedan === 1 ? "queda" : "quedan"} {quedan}{" "}
              {quedan === 1 ? "día" : "días"} antes de que tu página deje de
              tomar reservas.
            </>
          ) : (
            <>Hoy es el último día antes de que tu página deje de tomar reservas.</>
          )}
        </>
      ),
      accion: "Pagar ahora",
    };
  }

  if (d.estado === "activa" && d.dias_restantes !== null) {
    if (d.dias_restantes > DIAS_DE_ANTICIPACION) return null;
    return {
      tono: "ambar",
      texto:
        d.dias_restantes <= 0 ? (
          <>
            <b>Tu suscripción vence hoy.</b> Después tenés {d.dias_prorroga}{" "}
            {d.dias_prorroga === 1 ? "día" : "días"} de gracia.
          </>
        ) : (
          <>
            <b>
              Tu suscripción vence en {d.dias_restantes}{" "}
              {d.dias_restantes === 1 ? "día" : "días"}.
            </b>{" "}
            Activá el débito automático y no lo pensás más.
          </>
        ),
      accion: "Ver mi suscripción",
    };
  }

  return null;
}

export function AvisoVencimiento() {
  const [datos, setDatos] = useState<MiSuscripcion | null>(null);
  const ruta = usePathname();

  useEffect(() => {
    let vivo = true;
    leerMiSuscripcion()
      .then((d) => vivo && setDatos(d))
      // Que la cobranza no cargue no puede romper el panel entero. Sin
      // cartel se sigue trabajando; con un panel roto, no.
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, []);

  if (!datos) return null;

  // Estando ya en «Mi suscripción», el cartel sobra: la pantalla entera dice
  // lo mismo con más detalle, y repetirlo arriba lo vuelve decorado.
  if (ruta?.startsWith("/suscripcion")) return null;

  const aviso = avisoDe(datos);
  if (!aviso) return null;

  const rojo = aviso.tono === "rojo";

  return (
    <div
      className={`flex flex-wrap items-center gap-3 border-b px-6 py-2.5 text-sm ${
        rojo
          ? "border-red-500/30 bg-red-500/10"
          : "border-amber-500/30 bg-amber-500/10"
      }`}
    >
      {rojo ? (
        <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
      ) : (
        <CreditCard className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      )}
      <span className="min-w-0 flex-1">{aviso.texto}</span>
      <Link
        href="/suscripcion"
        className="shrink-0 font-medium underline-offset-4 hover:underline"
      >
        {aviso.accion} →
      </Link>
    </div>
  );
}
