"use client";

/**
 * Integraciones (/admin/integraciones): estado de Mercado Pago para el cobro
 * de las cuotas de Turnos360.
 *
 * Solo dice lo que se puede afirmar con datos: si hay token, si hay secreto
 * del webhook, en qué modo está la firma y qué avisos llegaron de verdad.
 * Tener credenciales no es «funciona»: hasta que no se procesa un aviso real
 * queda marcado como no comprobado.
 */

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Copy, XCircle } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { estadoMercadoPago, type EstadoMP, type EventoMPAdmin } from "@/lib/admin-api";
import { Encabezado, Tile, fechaHora } from "../_ui";

const RESULTADO: Record<string, string> = {
  procesado: "Procesado",
  ignorado: "Ignorado",
  error: "Error",
  firma_invalida: "Firma inválida",
};

function Evento({ e, vacio }: { e: EventoMPAdmin | null; vacio: string }) {
  if (!e) return <span className="text-muted-foreground">{vacio}</span>;
  return (
    <span>
      {fechaHora(e.recibido_en)} · {e.tipo}{e.accion ? ` (${e.accion})` : ""} · <b>{RESULTADO[e.resultado] ?? e.resultado}</b>
      {e.detalle && <span className="block text-xs text-muted-foreground">{e.detalle}</span>}
    </span>
  );
}

function Fila({ ok, titulo, children }: { ok: boolean | null; titulo: string; children: React.ReactNode }) {
  const Icono = ok === null ? CircleDashed : ok ? CheckCircle2 : XCircle;
  const color = ok === null ? "text-muted-foreground" : ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400";
  return (
    <li className="flex gap-3 px-4 py-3 text-sm">
      <Icono className={`mt-0.5 h-4 w-4 shrink-0 ${color}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{titulo}</p>
        <div className="text-muted-foreground [&_b]:text-foreground">{children}</div>
      </div>
    </li>
  );
}

export default function IntegracionesAdmin() {
  const [d, setD] = useState<EstadoMP | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    estadoMercadoPago()
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo leer el estado."));
  }, []);

  return (
    <div>
      <Encabezado
        titulo="Integraciones"
        bajada="Mercado Pago para cobrar las cuotas de Turnos360. Acá se ve lo que está comprobado con avisos reales, no solo lo que está configurado."
      />
      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="h-48 animate-pulse rounded-2xl bg-muted" />
      ) : (
        <div className="space-y-6">
          <div
            role="status"
            className={`flex items-start gap-2 rounded-2xl border p-4 text-sm ${
              d.comprobado
                ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
                : "border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
            }`}
          >
            {d.comprobado ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
            <div>
              <p className="font-semibold">
                {d.comprobado ? "Comprobado: hay avisos procesados" : !d.configurado ? "Mercado Pago no está configurado" : "Configurado, sin comprobar de punta a punta"}
              </p>
              {d.falta_comprobar.length > 0 && (
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {d.falta_comprobar.map((f) => <li key={f}>{f}</li>)}
                </ul>
              )}
            </div>
          </div>

          <section aria-labelledby="t-config" className="rounded-2xl border bg-card">
            <h2 id="t-config" className="border-b px-4 py-3 text-sm font-semibold">Configuración y avisos</h2>
            <ul className="divide-y">
              <Fila ok={d.configurado} titulo="Token de acceso">
                {d.configurado
                  ? d.entorno === "pruebas"
                    ? <>Cargado, de <b>pruebas</b> (TEST-).</>
                    : <>Cargado (APP_USR-). Puede ser de producción o de un usuario de prueba: con el token solo no se distingue.</>
                  : "No cargado (MP_SAAS_ACCESS_TOKEN)."}
              </Fila>
              <Fila ok={d.webhook_secreto} titulo="Secreto del webhook">
                {d.webhook_secreto ? "Cargado." : "No cargado (MP_SAAS_WEBHOOK_SECRET): no se puede validar la firma."}
              </Fila>
              <Fila ok={d.firma_modo === "enforce" ? true : d.firma_modo === "log" ? null : false} titulo="Validación de firma">
                Modo <b>{d.firma_modo}</b>.{" "}
                {d.firma_modo === "enforce" ? "Los avisos sin firma válida se rechazan." : d.firma_modo === "log" ? "Se registra si la firma no cierra, pero se procesa igual." : "No se valida."}
              </Fila>
              <Fila ok={null} titulo="URL del webhook (cargarla en Mercado Pago)">
                <span className="flex items-center gap-2">
                  <code className="break-all rounded bg-muted px-1.5 py-0.5 text-xs text-foreground">{d.webhook_url}</code>
                  <button
                    type="button"
                    aria-label="Copiar URL del webhook"
                    onClick={() => navigator.clipboard.writeText(d.webhook_url).then(() => toast.success("Copiada"))}
                    className="rounded p-1 hover:bg-muted"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                </span>
              </Fila>
              <Fila ok={d.ultimo_evento ? true : null} titulo="Último aviso recibido">
                <Evento e={d.ultimo_evento} vacio="Todavía no llegó ninguno." />
              </Fila>
              <Fila ok={d.ultimo_procesado ? true : null} titulo="Último aviso procesado">
                <Evento e={d.ultimo_procesado} vacio="Ninguno procesado todavía." />
              </Fila>
            </ul>
          </section>

          <div className="grid gap-3 sm:grid-cols-3">
            <Tile etiqueta="Pagos sin terminar (+24 h)" valor={d.intentos_pendientes_24h} tono={d.intentos_pendientes_24h ? "aviso" : "neutro"} />
            <Tile etiqueta="Pagos MP sin conciliar" valor={d.pagos_mp_sin_conciliar} />
            <Tile etiqueta="Devoluciones abiertas en MP" valor={d.devoluciones_abiertas} tono={d.devoluciones_abiertas ? "aviso" : "neutro"} />
          </div>

          <section aria-labelledby="t-errores" className="rounded-2xl border bg-card">
            <h2 id="t-errores" className="border-b px-4 py-3 text-sm font-semibold">Errores de los últimos 7 días</h2>
            {d.errores_recientes.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">Ninguno.</p>
            ) : (
              <ul className="divide-y text-sm">
                {d.errores_recientes.map((e, i) => (
                  <li key={`${e.recibido_en}-${i}`} className="px-4 py-2.5"><Evento e={e} vacio="" /></li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
