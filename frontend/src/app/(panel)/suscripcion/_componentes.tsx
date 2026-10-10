"use client";

/**
 * Piezas compartidas por los apartados de «Mi suscripción».
 */

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  AlertTriangle,
  CalendarClock,
  Clock,
  Info,
  MessageSquareWarning,
  RotateCcw,
  XCircle,
} from "lucide-react";

import { reactivarSuscripcion, type MiSuscripcion } from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import { useConfirmar } from "@/components/confirmar";
import { estiloDe, fechaLarga, pesos } from "./_suscripcion";

export const ESTADO_PAGO: Record<string, { texto: string; clase: string }> = {
  al_dia: { texto: "Al día", clase: "text-emerald-700 dark:text-emerald-400" },
  en_revision: { texto: "En revisión", clase: "text-sky-700 dark:text-sky-400" },
  info_solicitada: { texto: "Falta un dato", clase: "text-amber-700 dark:text-amber-400" },
  rechazado: { texto: "Rechazado", clase: "text-red-700 dark:text-red-400" },
  pendiente: { texto: "Pendiente de acreditación", clase: "text-amber-700 dark:text-amber-400" },
  adeuda: { texto: "Pendiente de pago", clase: "text-red-700 dark:text-red-400" },
};

/** Reactivar con confirmación: lo usan el resumen y los avisos. */
export function useReactivar(datos: MiSuscripcion | null, cargar: () => Promise<void>) {
  const confirmar = useConfirmar();
  return async function reactivar() {
    if (!datos) return;
    const cancelada = datos.estado === "cancelada";
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
  };
}

export function Dato({
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

export function BarraUso({ etiqueta, usados, tope }: { etiqueta: string; usados: number; tope: number | null }) {
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
export function Avisos({ datos, onReactivar }: { datos: MiSuscripcion; onReactivar: () => void }) {
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

export function Cartel({
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

