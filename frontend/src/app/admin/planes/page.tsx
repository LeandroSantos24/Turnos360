"use client";

/**
 * Suscripciones y planes (/admin/planes).
 *
 * El catálogo sale de app/core/planes.py (no se edita desde acá: precio y
 * límites viven en el código y en la config). Al lado, cuántos negocios
 * activos hay en cada plan y en qué estado está su suscripción hoy.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiError } from "@/lib/api";
import { listarPlanes, type PlanAdmin } from "@/lib/admin-api";
import { Encabezado, pesos } from "../_ui";
import { PestanasSuscripciones } from "./pestanas";

const ESTADOS: Record<string, string> = {
  activa: "Activa",
  prueba: "En prueba",
  prueba_vencida: "Prueba vencida",
  pendiente_pago: "Pago pendiente",
  en_revision: "En revisión",
  prorroga: "Prórroga",
  vencida: "Vencida",
  cancelacion_programada: "Cancelación programada",
  cancelada: "Cancelada",
  suspendida: "Suspendida",
  sin_vencimiento: "Sin vencimiento",
  desconocido: "Sin dato",
};

const limite = (n: number | null) => (n === null ? "Sin límite" : n);

export default function PlanesAdmin() {
  const [planes, setPlanes] = useState<PlanAdmin[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listarPlanes()
      .then(setPlanes)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron leer los planes."));
  }, []);

  return (
    <div>
      <Encabezado
        titulo="Suscripciones y planes"
        bajada="Los planes que existen y cuántos negocios activos hay en cada uno, según el estado de su suscripción hoy."
        acciones={<Link href="/admin/empresas" className="text-sm font-medium underline underline-offset-4">Ver empresas</Link>}
      />
      <PestanasSuscripciones />
      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!planes ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2].map((i) => <div key={i} className="h-48 animate-pulse rounded-2xl bg-muted" />)}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {planes.map((p) => (
            <article key={p.codigo} className="flex flex-col rounded-2xl border bg-card p-4">
              <header className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-lg font-bold">{p.etiqueta}</h2>
                  <p className="text-xs text-muted-foreground">
                    {p.se_vende_solo ? "Se contrata desde la web" : "Se habilita a mano"} · código {p.codigo}
                  </p>
                </div>
                <p className="text-right">
                  <span className="text-xl font-bold tabular-nums">{p.precio === null ? "A medida" : pesos(p.precio)}</span>
                  {p.precio !== null && <span className="block text-xs text-muted-foreground">por mes</span>}
                </p>
              </header>
              <dl className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-muted/50 p-2 text-center text-sm">
                <div><dt className="text-xs text-muted-foreground">Profesionales</dt><dd className="font-semibold">{limite(p.profesionales)}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Usuarios</dt><dd className="font-semibold">{limite(p.usuarios)}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Sucursales</dt><dd className="font-semibold">{p.sucursales}</dd></div>
              </dl>
              <div className="mt-4">
                <p className="text-sm"><b className="tabular-nums">{p.empresas}</b> negocio(s) activo(s)</p>
                {p.empresas > 0 && (
                  <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
                    {Object.entries(p.por_estado).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <li key={k} className="rounded-full bg-muted px-2.5 py-1">{ESTADOS[k] ?? k}: <b>{v}</b></li>
                    ))}
                  </ul>
                )}
              </div>
              {p.funciones.length > 0 && (
                <details className="mt-auto pt-4 text-sm">
                  <summary className="cursor-pointer text-muted-foreground">{p.funciones.length} función(es) incluidas</summary>
                  <ul className="mt-2 flex flex-wrap gap-1 text-xs">
                    {p.funciones.map((f) => <li key={f} className="rounded border px-2 py-0.5">{f.replace(/_/g, " ")}</li>)}
                  </ul>
                </details>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
