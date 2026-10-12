"use client";

/**
 * Auditoría (/admin/auditoria): qué hizo cada super-admin, cuándo y sobre
 * qué negocio. Solo lectura: el registro no se edita ni se borra.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { ApiError } from "@/lib/api";
import { listarAuditoriaFiltrada, type FilaAuditoria } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { Encabezado, Vacio, fechaHora } from "../_ui";
import { PestanasAuditoria } from "./pestanas";

const ACCIONES: [string, string][] = [
  ["aprobar_pago", "Aprobó un pago"],
  ["rechazar_pago", "Rechazó un pago"],
  ["solicitar_info", "Pidió información de un pago"],
  ["registrar_pago", "Registró un pago"],
  ["prorroga", "Dio días de gracia"],
  ["renovar_manual", "Renovó sin pago"],
  ["cambiar_vencimiento", "Cambió el vencimiento"],
  ["cambiar_plan", "Cambió el plan"],
  ["suspender", "Suspendió la cuenta"],
  ["reanudar", "Reanudó la cuenta"],
  ["cancelar", "Canceló la suscripción"],
  ["reactivar", "Reactivó la suscripción"],
  ["revertir", "Revirtió un movimiento"],
  ["ficha", "Editó la ficha comercial"],
  ["ver_comprobante", "Vio un comprobante"],
  ["devolucion", "Devolución"],
  ["conciliar", "Concilió un pago"],
  ["desconciliar", "Desconcilió un pago"],
  ["anular_pago", "Anuló un pago"],
  ["anular_intento", "Anuló un pago pendiente"],
  ["cierre_preparado", "Preparó un cierre de caja"],
  ["cierre_confirmado", "Cerró la caja"],
  ["cierre_reabierto", "Reabrió un cierre"],
  ["cierre_descartado", "Descartó un borrador de cierre"],
  ["acceso_usuario", "Cambió un acceso"],
  ["restablecer_clave", "Restablecimiento de contraseña"],
  ["exportar", "Exportó un reporte"],
];

function Cambio({ antes, despues }: { antes: FilaAuditoria["antes"]; despues: FilaAuditoria["despues"] }) {
  if (!antes && !despues) return null;
  const claves = Array.from(new Set([...Object.keys(antes ?? {}), ...Object.keys(despues ?? {})]));
  const txt = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
  return (
    <details className="mt-1 text-xs">
      <summary className="cursor-pointer text-muted-foreground">Ver cambio</summary>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-lg bg-muted/50 p-2">
        {claves.map((k) => (
          <div key={k} className="contents">
            <dt className="font-medium">{k.replace(/_/g, " ")}</dt>
            <dd className="break-all">
              <span className="text-muted-foreground line-through">{txt(antes?.[k])}</span> → {txt(despues?.[k])}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export default function AuditoriaAdmin() {
  const [accion, setAccion] = useState("");
  const [email, setEmail] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [filtros, setFiltros] = useState({ accion: "", email: "", desde: "", hasta: "" });
  const [filas, setFilas] = useState<FilaAuditoria[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(() => {
    setError(null);
    listarAuditoriaFiltrada({
      accion: filtros.accion || undefined,
      admin_email: filtros.email || undefined,
      desde: filtros.desde || undefined,
      hasta: filtros.hasta || undefined,
      limite: 300,
    })
      .then(setFilas)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo leer la auditoría."));
  }, [filtros]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <div>
      <Encabezado titulo="Auditoría y configuración" bajada="Cada acción de un super-admin queda registrada. El registro no se puede editar ni borrar." />
      <PestanasAuditoria />
      <form
        className="mb-4 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setFiltros({ accion, email: email.trim(), desde, hasta });
        }}
      >
        <label className="text-xs text-muted-foreground">
          Acción
          <select value={accion} onChange={(e) => setAccion(e.target.value)}
            className="mt-1 block max-w-[220px] rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground">
            <option value="">Todas</option>
            {ACCIONES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Admin
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email"
            className="mt-1 block w-44 rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <label className="text-xs text-muted-foreground">
          Desde
          <input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)}
            className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <label className="text-xs text-muted-foreground">
          Hasta
          <input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)}
            className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <Button type="submit" size="sm" variant="outline">Filtrar</Button>
      </form>

      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!filas ? (
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
      ) : filas.length === 0 ? (
        <Vacio>No hay acciones registradas con esos filtros.</Vacio>
      ) : (
        <ol className="divide-y rounded-2xl border bg-card">
          {filas.map((f) => (
            <li key={f.id} className="px-4 py-3 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="font-medium">
                  {f.accion_etiqueta}
                  {f.empresa_id && (
                    <>
                      {" · "}
                      <Link href={`/admin/empresas/${f.empresa_id}`} className="font-normal underline-offset-4 hover:underline">
                        {f.empresa_nombre ?? `Empresa #${f.empresa_id}`}
                      </Link>
                    </>
                  )}
                </p>
                <p className="text-xs tabular-nums text-muted-foreground">{fechaHora(f.creado_en)}</p>
              </div>
              {f.descripcion && <p className="text-muted-foreground">{f.descripcion}</p>}
              <p className="text-xs text-muted-foreground">{f.admin_email}{f.ip ? ` · IP ${f.ip}` : ""}</p>
              <Cambio antes={f.antes} despues={f.despues} />
            </li>
          ))}
        </ol>
      )}
      {filas && filas.length >= 300 && <p className="mt-2 text-xs text-muted-foreground">Se muestran las últimas 300. Achicá el período para ver más atrás.</p>}
    </div>
  );
}
