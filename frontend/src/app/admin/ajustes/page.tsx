"use client";

/**
 * Ajustes administrativos (/admin/ajustes).
 *
 * Todo lo que se le cambió a una suscripción sin plata: días de cortesía,
 * extensiones por incidencias, correcciones, cambios de plan. No entra en la
 * caja ni en los ingresos; acá se ve qué se dio, a quién, quién y por qué.
 */

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/api";
import { listarAjustesAdmin, type AjusteAdmin } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { Encabezado, Vacio, fecha, fechaHora } from "../_ui";
import { PestanasSuscripciones } from "../planes/pestanas";

const COLOR: Record<string, string> = {
  cortesia: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  incidencia: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  correccion: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  plan: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
};

type Datos = { total: number; pagina: number; limite: number; filas: AjusteAdmin[]; categorias: Record<string, string> };

function Contenido() {
  const params = useSearchParams();
  const empresaId = params.get("empresa_id") ? Number(params.get("empresa_id")) : undefined;
  const [categoria, setCategoria] = useState("");
  const [admin, setAdmin] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [f, setF] = useState({ categoria: "", admin: "", desde: "", hasta: "" });
  const [pagina, setPagina] = useState(1);
  const [d, setD] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(() => {
    setError(null);
    listarAjustesAdmin({
      empresa_id: empresaId,
      categoria: f.categoria || undefined,
      admin_email: f.admin || undefined,
      desde: f.desde || undefined,
      hasta: f.hasta || undefined,
      pagina,
    })
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los ajustes."));
  }, [empresaId, f, pagina]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const paginas = d ? Math.max(1, Math.ceil(d.total / d.limite)) : 1;

  return (
    <div>
      <Encabezado
        titulo="Suscripciones y planes"
        bajada="Ajustes administrativos: lo que se cambió a mano en una suscripción. Son días y planes, no plata: no entran en la caja ni en los ingresos."
      />
      <PestanasSuscripciones />
      <form
        className="mb-4 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setPagina(1);
          setF({ categoria, admin: admin.trim(), desde, hasta });
        }}
      >
        <label className="text-xs text-muted-foreground">
          Tipo de ajuste
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}
            className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground">
            <option value="">Todos</option>
            {Object.entries(d?.categorias ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Administrador
          <input value={admin} onChange={(e) => setAdmin(e.target.value)} placeholder="email"
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
        {empresaId && (
          <Link href="/admin/ajustes" className="rounded-full border px-3 py-1.5 text-xs">Empresa #{empresaId} ✕</Link>
        )}
      </form>

      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
      ) : d.filas.length === 0 ? (
        <Vacio>No hay ajustes con esos filtros.</Vacio>
      ) : (
        <>
          <p className="mb-2 text-xs text-muted-foreground">{d.total} ajuste(s)</p>
          <ul className="divide-y rounded-2xl border bg-card">
            {d.filas.map((a) => (
              <li key={a.id} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="font-medium">
                    <Link href={`/admin/empresas/${a.empresa_id}`} className="underline-offset-4 hover:underline">{a.empresa}</Link>
                    {" · "}{a.tipo_etiqueta}{" "}
                    <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-semibold ${a.categoria ? COLOR[a.categoria] ?? "bg-muted" : "bg-muted text-muted-foreground"}`}>
                      {a.categoria_etiqueta}
                    </span>
                    {a.estado === "revertido" && <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">Revertido</span>}
                  </p>
                  <p className="text-xs tabular-nums text-muted-foreground">{fechaHora(a.fecha)}</p>
                </div>
                <p className="mt-0.5 tabular-nums">
                  {a.vence_antes || a.vence_despues ? <>Vence {fecha(a.vence_antes)} → {fecha(a.vence_despues)}</> : null}
                  {a.dias ? <b> ({a.dias > 0 ? "+" : ""}{a.dias} días)</b> : null}
                  {a.plan_antes || a.plan_despues ? <> · Plan {a.plan_antes ?? "—"} → {a.plan_despues ?? "—"}</> : null}
                </p>
                <p className="text-muted-foreground">
                  {a.motivo ? `Motivo: ${a.motivo}` : a.detalle ?? "Sin motivo registrado (anterior a que fuera obligatorio)"}
                  {a.hecho_por ? ` · ${a.hecho_por}` : ""}
                </p>
              </li>
            ))}
          </ul>
          {paginas > 1 && (
            <div className="mt-4 flex items-center justify-center gap-3 text-sm">
              <Button size="sm" variant="outline" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>Anterior</Button>
              <span className="tabular-nums">{pagina} de {paginas}</span>
              <Button size="sm" variant="outline" disabled={pagina >= paginas} onClick={() => setPagina((p) => p + 1)}>Siguiente</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function AjustesAdmin() {
  return (
    <Suspense fallback={<div className="h-40 animate-pulse rounded-2xl bg-muted" />}>
      <Contenido />
    </Suspense>
  );
}
