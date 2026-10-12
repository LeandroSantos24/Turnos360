"use client";

/**
 * Cobros y pagos · Operaciones (/admin/cobros).
 *
 * Una lista con todo lo que es o fue un cobro de cuota: pagos acreditados,
 * transferencias informadas que todavía no son pago e intentos de Mercado
 * Pago sin terminar. Filtros arriba, en una fila; el detalle de cada pago se
 * abre al costado con sus devoluciones, su historial y las acciones que el
 * backend dice que se pueden hacer.
 */

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Download, Loader2, Search } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  anularIntento,
  exportarCobros,
  listarCobros,
  type FiltrosCobros,
  type ListaCobros,
  type Operacion,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { ChipEstado, Encabezado, METODOS, Vacio, fecha, pesos } from "../_ui";
import { PestanasCobros } from "./pestanas";
import { DetallePagoPanel } from "./detalle-pago";

const ESTADOS = [
  ["", "Todos los estados"],
  ["acreditado", "Acreditado"],
  ["en_revision", "En revisión"],
  ["pendiente", "Pendiente"],
  ["rechazado", "Rechazado"],
  ["cancelado", "Cancelado"],
  ["anulado", "Anulado"],
  ["reembolso_solicitado", "Reembolso solicitado"],
  ["reembolso_parcial", "Reembolso parcial"],
  ["reembolso_total", "Reembolso total"],
];

function Contenido() {
  const params = useSearchParams();
  const [f, setF] = useState<FiltrosCobros>({
    estado: params.get("estado") ?? "",
    empresa_id: params.get("empresa_id") ? Number(params.get("empresa_id")) : null,
    pagina: 1,
    limite: 50,
  });
  const [buscar, setBuscar] = useState("");
  const [datos, setDatos] = useState<ListaCobros | null>(null);
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState<number | null>(null);
  const [exportando, setExportando] = useState(false);
  const confirmar = useConfirmar();

  const cargar = useCallback(() => {
    setCargando(true);
    listarCobros(f)
      .then(setDatos)
      .catch((e) => toast.error(e instanceof ApiError ? e.message : "No se pudo cargar"))
      .finally(() => setCargando(false));
  }, [f]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // La búsqueda espera a que se termine de escribir.
  useEffect(() => {
    const t = setTimeout(() => setF((x) => ({ ...x, buscar, pagina: 1 })), 350);
    return () => clearTimeout(t);
  }, [buscar]);

  const set = (k: keyof FiltrosCobros, v: unknown) => setF((x) => ({ ...x, [k]: v === "" ? undefined : v, pagina: 1 }));

  async function anular(o: Operacion) {
    const ok = await confirmar({
      titulo: "¿Anular este cobro pendiente?",
      descripcion: o.id_proveedor
        ? `Se le pide a Mercado Pago que cancele el pago ${o.id_proveedor}. Si ya se aprobó, no se puede: hay que devolverlo.`
        : "El cliente no llegó a pagar. Se cierra el intento.",
      textoAccion: "Sí, anular",
      destructivo: true,
    });
    if (!ok) return;
    try {
      await anularIntento(o.id, "Anulado desde el panel de cobros");
      toast.success("Cobro pendiente anulado");
      cargar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo anular");
    }
  }

  const paginas = datos ? Math.max(1, Math.ceil(datos.total / (datos.limite || 50))) : 1;

  return (
    <div>
      <Encabezado
        titulo="Cobros y pagos"
        bajada="Cada cobro de cuota con su estado real. Lo en revisión y lo pendiente no es plata cobrada."
        acciones={
          <Button
            variant="outline"
            disabled={exportando}
            onClick={async () => {
              setExportando(true);
              try {
                await exportarCobros(f);
              } catch (e) {
                toast.error(e instanceof ApiError ? e.message : "No se pudo exportar");
              } finally {
                setExportando(false);
              }
            }}
          >
            {exportando ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
            Exportar CSV
          </Button>
        }
      />
      <PestanasCobros />

      <div className="mb-4 flex flex-wrap items-end gap-2" role="search">
        <label className="text-xs text-muted-foreground">
          Desde
          <input type="date" value={f.desde ?? ""} onChange={(e) => set("desde", e.target.value)} className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <label className="text-xs text-muted-foreground">
          Hasta
          <input type="date" value={f.hasta ?? ""} onChange={(e) => set("hasta", e.target.value)} className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <label className="text-xs text-muted-foreground">
          Método
          <select value={f.metodo ?? ""} onChange={(e) => set("metodo", e.target.value)} className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground">
            <option value="">Todos</option>
            {Object.entries(METODOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Estado
          <select value={f.estado ?? ""} onChange={(e) => set("estado", e.target.value)} className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground">
            {ESTADOS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Importe mín.
          <input type="number" min={0} inputMode="numeric" value={f.monto_min ?? ""} onChange={(e) => set("monto_min", e.target.value ? Number(e.target.value) : "")} className="mt-1 block w-28 rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <label className="text-xs text-muted-foreground">
          Importe máx.
          <input type="number" min={0} inputMode="numeric" value={f.monto_max ?? ""} onChange={(e) => set("monto_max", e.target.value ? Number(e.target.value) : "")} className="mt-1 block w-28 rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
        </label>
        <label className="min-w-[220px] flex-1 text-xs text-muted-foreground">
          Buscar
          <span className="relative mt-1 block">
            <Search className="absolute left-2 top-2 h-4 w-4" aria-hidden />
            <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Empresa, id, id de MP o referencia"
              className="block w-full rounded-lg border bg-background py-1.5 pl-8 pr-2 text-sm text-foreground" />
          </span>
        </label>
        {f.empresa_id && (
          <button type="button" onClick={() => set("empresa_id", null)} className="rounded-full border px-3 py-1.5 text-xs">
            Empresa #{f.empresa_id} ✕
          </button>
        )}
      </div>

      {datos && (
        <dl className="mb-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
          {[
            ["Acreditado", datos.sumas.acreditado],
            ["En revisión", datos.sumas.en_revision],
            ["Pendiente", datos.sumas.pendiente],
            ["Rechazado", datos.sumas.rechazado],
            ["Devuelto", datos.sumas.devuelto],
          ].map(([k, v]) => (
            <div key={k as string} className="rounded-xl bg-muted/50 px-3 py-2">
              <dt className="text-xs text-muted-foreground">{k}</dt>
              <dd className="font-semibold tabular-nums">{pesos(v as number)}</dd>
            </div>
          ))}
        </dl>
      )}

      {cargando && !datos ? (
        <div className="h-60 animate-pulse rounded-2xl bg-muted" />
      ) : !datos || datos.filas.length === 0 ? (
        <Vacio>No hay operaciones con esos filtros.</Vacio>
      ) : (
        <>
          {/* Tabla en pantallas grandes, tarjetas en el celular. */}
          <div className="relative hidden overflow-x-auto rounded-2xl border lg:block">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Fecha</th>
                  <th className="px-3 py-2 font-medium">Empresa</th>
                  <th className="px-3 py-2 font-medium">Concepto</th>
                  <th className="px-3 py-2 font-medium">Método</th>
                  <th className="px-3 py-2 text-right font-medium">Importe</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                  <th className="px-3 py-2 font-medium">Ids</th>
                  <th className="px-3 py-2"><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {datos.filas.map((o) => (
                  <tr key={o.clave} className="hover:bg-muted/30">
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">{fecha(o.fecha)}</td>
                    <td className="max-w-[180px] truncate px-3 py-2">
                      <Link href={`/admin/empresas/${o.empresa_id}`} className="hover:underline">{o.empresa}</Link>
                    </td>
                    <td className="px-3 py-2">{o.concepto}</td>
                    <td className="whitespace-nowrap px-3 py-2">{METODOS[o.metodo] ?? o.metodo}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-right font-medium tabular-nums">
                      {pesos(o.monto)}
                      {o.devuelto > 0 && <span className="block text-xs text-muted-foreground">−{pesos(o.devuelto)} devuelto</span>}
                    </td>
                    <td className="px-3 py-2"><ChipEstado estado={o.estado} etiqueta={o.estado_etiqueta} /></td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      <span className="block font-mono">{o.clave}</span>
                      {o.id_proveedor && <span className="block font-mono">MP {o.id_proveedor}</span>}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-right">
                      {o.tipo === "pago" && <Button size="sm" variant="outline" onClick={() => setAbierto(o.id)}>Ver</Button>}
                      {o.tipo === "intento_mp" && o.estado === "pendiente" && (
                        <Button size="sm" variant="ghost" onClick={() => anular(o)}>Anular</Button>
                      )}
                      {o.tipo === "transferencia_informada" && o.estado === "en_revision" && (
                        <Link href="/admin/cobranza" className="text-xs font-medium underline">Revisar</Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-2 lg:hidden">
            {datos.filas.map((o) => (
              <li key={o.clave} className="rounded-2xl border bg-card p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{o.empresa}</p>
                    <p className="text-xs text-muted-foreground">{fecha(o.fecha)} · {METODOS[o.metodo] ?? o.metodo}</p>
                  </div>
                  <p className="font-semibold tabular-nums">{pesos(o.monto)}</p>
                </div>
                <p className="mt-1 text-sm">{o.concepto}</p>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <ChipEstado estado={o.estado} etiqueta={o.estado_etiqueta} />
                  {o.tipo === "pago" && <Button size="sm" variant="outline" onClick={() => setAbierto(o.id)}>Ver detalle</Button>}
                  {o.tipo === "intento_mp" && o.estado === "pendiente" && <Button size="sm" variant="ghost" onClick={() => anular(o)}>Anular</Button>}
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
            <span>{datos.total} operación(es)</span>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" disabled={(f.pagina ?? 1) <= 1} onClick={() => setF((x) => ({ ...x, pagina: (x.pagina ?? 1) - 1 }))}>Anterior</Button>
              <span>{f.pagina ?? 1} de {paginas}</span>
              <Button size="sm" variant="outline" disabled={(f.pagina ?? 1) >= paginas} onClick={() => setF((x) => ({ ...x, pagina: (x.pagina ?? 1) + 1 }))}>Siguiente</Button>
            </div>
          </div>
        </>
      )}

      <DetallePagoPanel pagoId={abierto} onCerrar={() => setAbierto(null)} onCambio={cargar} />
    </div>
  );
}

export default function CobrosPage() {
  return (
    <Suspense fallback={<div className="h-60 animate-pulse rounded-2xl bg-muted" />}>
      <Contenido />
    </Suspense>
  );
}
