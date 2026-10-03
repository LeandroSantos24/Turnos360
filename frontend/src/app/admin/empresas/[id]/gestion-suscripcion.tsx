"use client";

/**
 * Acciones críticas sobre la suscripción de una empresa, y la auditoría.
 *
 * Todas siguen el mismo patrón de DOS pasos: primero un diálogo que explica
 * la consecuencia y pide el motivo; después la confirmación con el texto
 * concreto (empresa, fecha, qué se corta). Cada acción queda en la auditoría
 * del super-admin con el antes y el después.
 */

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, PlayCircle, RotateCcw, ShieldCheck, XCircle } from "lucide-react";

import {
  FichaEmpresa,
  FilaAuditoria,
  cancelarSuscripcionAdmin,
  fichaEmpresa,
  listarAuditoria,
  pausarEmpresa,
  reactivarSuscripcionAdmin,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const TONO: Record<string, string> = {
  ok: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
  info: "bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30",
  aviso: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30",
  error: "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/30",
  neutro: "bg-muted text-muted-foreground border-border",
};

/** "2026-10-14" -> "14/10/2026" sin pasar por Date. */
function fecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

type Accion = "cancelar" | "suspender";

export function GestionSuscripcion({
  empresaId,
  version,
  onCambio,
}: {
  empresaId: number;
  /** Cambia cuando otra parte de la pantalla modificó algo. */
  version: number;
  onCambio: () => void;
}) {
  const confirmar = useConfirmar();
  const [f, setF] = useState<FichaEmpresa | null>(null);
  const [abierta, setAbierta] = useState<Accion | null>(null);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setF(await fichaEmpresa(empresaId));
    } catch {
      setF(null);
    }
  }, [empresaId]);

  useEffect(() => {
    cargar();
  }, [cargar, version]);

  if (!f) return null;
  const s = f.suscripcion;
  const hasta = s.vence ?? s.prueba_hasta;

  async function hecho(texto: string) {
    toast.success(texto);
    setAbierta(null);
    setMotivo("");
    await cargar();
    onCambio();
  }

  async function confirmarDialogo() {
    if (!f || !abierta) return;
    const ok =
      abierta === "cancelar"
        ? await confirmar({
            titulo: `¿Cancelar la suscripción de ${f.nombre}?`,
            descripcion: hasta
              ? `Sigue activa hasta el ${fecha(hasta)} y después no se renueva. No se borra ningún dato y se puede reactivar.`
              : "Queda cancelada ahora. No se borra ningún dato y se puede reactivar.",
            textoAccion: "Sí, cancelar suscripción",
            textoCancelar: "Volver",
            destructivo: true,
          })
        : await confirmar({
            titulo: `¿Suspender la cuenta de ${f.nombre}?`,
            descripcion:
              "Se corta el acceso al panel de todo el equipo y la página deja de tomar reservas hasta que la reanudes. " +
              "Los datos no se tocan. Queda registrado en la auditoría.",
            textoAccion: "Sí, suspender",
            textoCancelar: "Volver",
            destructivo: true,
          });
    if (!ok) return;
    setEnviando(true);
    try {
      if (abierta === "cancelar") {
        await cancelarSuscripcionAdmin(f.id, motivo.trim() || null);
        await hecho("Suscripción cancelada");
      } else {
        await pausarEmpresa(f.id, false, motivo.trim() || null);
        await hecho("Cuenta suspendida");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo completar la acción");
    } finally {
      setEnviando(false);
    }
  }

  async function reactivar() {
    if (!f) return;
    const ok = await confirmar({
      titulo: `¿Reactivar la suscripción de ${f.nombre}?`,
      descripcion:
        s.estado === "cancelada"
          ? "Se deshace la cancelación. Si el período ya terminó, queda vencida hasta que pague."
          : `Se deshace la cancelación programada: sigue renovándose después del ${fecha(hasta)}.`,
      textoAccion: "Sí, reactivar",
      textoCancelar: "Volver",
    });
    if (!ok) return;
    try {
      await reactivarSuscripcionAdmin(f.id);
      await hecho("Suscripción reactivada");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo reactivar");
    }
  }

  async function reanudar() {
    if (!f) return;
    const ok = await confirmar({
      titulo: `¿Reanudar la cuenta de ${f.nombre}?`,
      descripcion: "Vuelve a funcionar con el estado de suscripción que le corresponda por sus fechas.",
      textoAccion: "Sí, reanudar",
      textoCancelar: "Volver",
    });
    if (!ok) return;
    try {
      await pausarEmpresa(f.id, true);
      await hecho("Cuenta reanudada");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo reanudar");
    }
  }

  return (
    <section className="rounded-2xl border bg-card p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Suscripción</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="text-lg font-bold" style={{ fontFamily: "var(--fuente-titulos)" }}>
              {f.plan.etiqueta}
            </span>
            <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONO[s.tono] ?? TONO.neutro}`}>
              {s.etiqueta}
            </span>
            {!s.reservas_abiertas && (
              <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-xs text-red-700 dark:text-red-400">
                reservas web cerradas
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {s.vence ? `Vence ${fecha(s.vence)}` : "Sin vencimiento"} · ${f.plan.precio.toLocaleString("es-AR")}/mes
            {f.plan.precio_pactado ? " (pactado)" : ""}
            {s.plan_programado ? ` · baja programada a ${s.plan_programado}` : ""}
          </p>
          {s.cancela_al_vencer && (
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-400">
              Cancelación pedida{s.cancelacion_solicitada_en ? ` el ${fechaHora(s.cancelacion_solicitada_en)}` : ""}
              {s.cancelacion_motivo ? ` · «${s.cancelacion_motivo}»` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {f.activa && !s.cancela_al_vencer && (
            <Button variant="outline" size="sm" onClick={() => setAbierta("cancelar")}>
              <XCircle className="mr-1.5 h-4 w-4" /> Cancelar suscripción
            </Button>
          )}
          {f.activa && s.cancela_al_vencer && (
            <Button size="sm" onClick={reactivar}>
              <RotateCcw className="mr-1.5 h-4 w-4" /> Reactivar
            </Button>
          )}
          {f.activa ? (
            <Button variant="destructive" size="sm" onClick={() => setAbierta("suspender")}>
              <Ban className="mr-1.5 h-4 w-4" /> Suspender
            </Button>
          ) : (
            <Button size="sm" onClick={reanudar}>
              <PlayCircle className="mr-1.5 h-4 w-4" /> Reanudar
            </Button>
          )}
        </div>
      </div>

      <Dialog open={abierta !== null} onOpenChange={(o) => !o && !enviando && setAbierta(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {abierta === "cancelar" ? `Cancelar la suscripción de ${f.nombre}` : `Suspender a ${f.nombre}`}
            </DialogTitle>
            <DialogDescription>
              {abierta === "cancelar"
                ? hasta
                  ? `No se corta nada hoy: sigue activa hasta el ${fecha(hasta)}. Si tiene débito automático, se corta en Mercado Pago.`
                  : "No tiene un período pago: queda cancelada al confirmar."
                : "Nadie de la empresa puede entrar al panel y la página deja de tomar reservas. Los datos no se tocan y se reanuda con un click."}
            </DialogDescription>
          </DialogHeader>
          <Textarea
            placeholder="Motivo (queda en la auditoría)"
            value={motivo}
            maxLength={200}
            onChange={(e) => setMotivo(e.target.value)}
          />
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setAbierta(null)} disabled={enviando}>
              Volver
            </Button>
            <Button variant="destructive" onClick={confirmarDialogo} disabled={enviando}>
              Continuar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

const CAMPOS: Record<string, string> = {
  plan: "Plan",
  plan_programado: "Baja programada",
  suscripcion_vence: "Vence",
  prueba_hasta: "Prueba hasta",
  activa: "Activa",
  precio_mensual: "Precio pactado",
  limite_recursos: "Tope profesionales",
  limite_sucursales: "Tope sucursales",
  cancela_al_vencer: "Cancela al vencer",
  estado: "Estado",
};

function diferencias(antes: Record<string, unknown> | null, despues: Record<string, unknown> | null) {
  if (!antes || !despues) return [];
  return Object.keys(CAMPOS)
    .filter((k) => JSON.stringify(antes[k]) !== JSON.stringify(despues[k]))
    .map((k) => ({ campo: CAMPOS[k], antes: String(antes[k] ?? "—"), despues: String(despues[k] ?? "—") }));
}

/** Quién hizo qué sobre esta empresa desde el panel de super-admin. Solo lectura. */
export function AuditoriaEmpresa({ empresaId, version }: { empresaId: number; version: number }) {
  const [filas, setFilas] = useState<FilaAuditoria[] | null>(null);

  useEffect(() => {
    listarAuditoria(empresaId, 50)
      .then(setFilas)
      .catch(() => setFilas([]));
  }, [empresaId, version]);

  return (
    <div className="space-y-3">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <ShieldCheck className="h-5 w-5 text-muted-foreground" /> Auditoría de administración
        </h2>
        <p className="text-sm text-muted-foreground">
          Cada acción del panel sobre esta empresa: quién, cuándo y qué cambió. No se puede editar.
        </p>
      </div>
      {filas === null ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : filas.length === 0 ? (
        <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Todavía no hay acciones registradas.
        </div>
      ) : (
        <ul className="divide-y rounded-2xl border bg-card">
          {filas.map((a) => {
            const cambios = diferencias(a.antes, a.despues);
            return (
              <li key={a.id} className="p-3 text-sm">
                <p className="flex flex-wrap items-center gap-x-2">
                  <span className="font-medium">{a.accion_etiqueta}</span>
                  {a.descripcion && <span className="text-muted-foreground">· {a.descripcion}</span>}
                </p>
                <p className="text-xs text-muted-foreground">
                  {fechaHora(a.creado_en)} · {a.admin_email}
                  {a.ip ? ` · ${a.ip}` : ""}
                </p>
                {cambios.length > 0 && (
                  <ul className="mt-1.5 flex flex-wrap gap-1.5">
                    {cambios.map((c) => (
                      <li key={c.campo} className="rounded-md bg-muted px-2 py-0.5 text-xs tabular-nums">
                        {c.campo}: {c.antes} → <b>{c.despues}</b>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
