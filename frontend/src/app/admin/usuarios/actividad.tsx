"use client";

/**
 * Sesiones y actividad de un usuario (panel lateral del super-admin).
 *
 * Muestra lo que el servidor sabe de verdad: cada ingreso abre una sesión con
 * su dispositivo, último uso y estado. Se puede cerrar una sola (por ejemplo,
 * la de un celular perdido) o todas. Las dos cosas piden motivo y quedan en la
 * auditoría. Si la cuenta vino por invitación y todavía no se activó, muestra
 * el estado de la invitación y deja reenviarla o revocarla.
 */

import { useCallback, useEffect, useState } from "react";
import { Activity, Loader2, LogOut, Mail, RotateCcw, XCircle } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  cerrarTodasLasSesiones,
  reenviarInvitacion,
  revocarInvitacion,
  revocarSesion,
  verActividad,
  type ActividadUsuario,
  type EstadoInvitacion,
  type SesionAdmin,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { fechaHora } from "../_ui";

const ESTADO_SESION: Record<SesionAdmin["estado"], [string, string]> = {
  activa: ["Activa", "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"],
  revocada: ["Cerrada", "bg-muted text-foreground"],
  invalidada: ["Invalidada", "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"],
  vencida: ["Vencida", "bg-muted text-muted-foreground"],
};

export const ETIQUETA_INVITACION: Record<EstadoInvitacion["estado"], string> = {
  enviando: "Invitación en envío",
  enviada: "Invitación enviada",
  envio_fallido: "No se pudo enviar la invitación",
  vencida: "Invitación vencida",
  sin_invitacion: "Sin invitación vigente",
};

const err = (e: unknown, d: string) => (e instanceof ApiError ? e.message : d);

export function BotonActividad({ usuario }: { usuario: { id: number; nombre: string } }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setAbierto(true)} aria-label={`Sesiones y actividad de ${usuario.nombre}`}>
        <Activity className="h-4 w-4" aria-hidden /> <span className="hidden sm:inline">Actividad</span>
      </Button>
      {abierto && <PanelActividad usuarioId={usuario.id} onCerrar={() => setAbierto(false)} />}
    </>
  );
}

export function PanelActividad({ usuarioId, onCerrar }: { usuarioId: number; onCerrar: () => void }) {
  const [d, setD] = useState<ActividadUsuario | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const confirmar = useConfirmar();

  const cargar = useCallback(() => {
    verActividad(usuarioId).then(setD).catch((e) => setError(err(e, "No se pudo cargar la actividad.")));
  }, [usuarioId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const motivoOk = motivo.trim().length >= 4;

  async function cerrarUna(s: SesionAdmin) {
    if (!motivoOk || !d) return;
    const ok = await confirmar({
      titulo: "¿Cerrar esta sesión?",
      descripcion: `${s.dispositivo ?? "Dispositivo sin identificar"} de ${d.usuario.nombre} deja de funcionar en el próximo clic. Las demás sesiones siguen abiertas.`,
      textoAccion: "Sí, cerrar",
      destructivo: true,
    });
    if (!ok) return;
    setOcupado(`s${s.id}`);
    try {
      setD(await revocarSesion(usuarioId, s.id, motivo.trim()));
      toast.success("Sesión cerrada");
    } catch (e) {
      toast.error(err(e, "No se pudo cerrar la sesión."));
    } finally {
      setOcupado(null);
    }
  }

  async function cerrarTodas() {
    if (!motivoOk || !d) return;
    const ok = await confirmar({
      titulo: `¿Cerrar todas las sesiones de ${d.usuario.nombre}?`,
      descripcion: "Sale de todos los dispositivos, incluidas las sesiones abiertas antes de que existiera esta lista. Tiene que volver a entrar con su contraseña.",
      textoAccion: "Sí, cerrar todas",
      destructivo: true,
    });
    if (!ok) return;
    setOcupado("todas");
    try {
      setD(await cerrarTodasLasSesiones(usuarioId, motivo.trim()));
      toast.success("Se cerraron todas las sesiones");
      setMotivo("");
    } catch (e) {
      toast.error(err(e, "No se pudieron cerrar las sesiones."));
    } finally {
      setOcupado(null);
    }
  }

  async function invitacion(accion: "reenviar" | "revocar") {
    if (!d) return;
    const ok = await confirmar(
      accion === "reenviar"
        ? {
            titulo: "¿Reenviar la invitación?",
            descripcion: `Se manda un link nuevo a ${d.usuario.email}. El anterior deja de servir.`,
            textoAccion: "Reenviar",
          }
        : {
            titulo: "¿Revocar la invitación?",
            descripcion: "El link deja de servir y la cuenta queda sin activar. Se puede volver a invitar.",
            textoAccion: "Revocar",
            destructivo: true,
          },
    );
    if (!ok) return;
    setOcupado(accion);
    try {
      await (accion === "reenviar" ? reenviarInvitacion(usuarioId) : revocarInvitacion(usuarioId));
      toast.success(accion === "reenviar" ? "Invitación reenviada" : "Invitación revocada");
      cargar();
    } catch (e) {
      toast.error(err(e, "No se pudo completar."));
    } finally {
      setOcupado(null);
    }
  }

  return (
    <Sheet open onOpenChange={(o) => !o && onCerrar()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Sesiones y actividad</SheetTitle>
          <SheetDescription>{d ? `${d.usuario.nombre} · ${d.usuario.email}` : "Cargando…"}</SheetDescription>
        </SheetHeader>
        {error && <p role="alert" className="mx-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
        {!d ? (
          <div className="mx-4 h-40 animate-pulse rounded-2xl bg-muted" />
        ) : (
          <div className="space-y-5 px-4 pb-6 text-sm">
            <dl className="grid grid-cols-2 gap-2">
              <div className="rounded-xl bg-muted/50 p-3">
                <dt className="text-xs text-muted-foreground">Último ingreso</dt>
                <dd className="font-semibold">{d.usuario.ultimo_ingreso_en ? fechaHora(d.usuario.ultimo_ingreso_en) : "Sin registro"}</dd>
              </div>
              <div className="rounded-xl bg-muted/50 p-3">
                <dt className="text-xs text-muted-foreground">Sesiones activas</dt>
                <dd className="font-semibold tabular-nums">{d.activas}</dd>
              </div>
            </dl>

            {d.invitacion && (
              <section aria-labelledby="t-inv" className="rounded-2xl border p-3">
                <h3 id="t-inv" className="flex items-center gap-1.5 font-semibold"><Mail className="h-4 w-4" aria-hidden /> Cuenta sin activar</h3>
                <p className="mt-1">{ETIQUETA_INVITACION[d.invitacion.estado]}
                  {d.invitacion.expira_en && d.invitacion.estado !== "vencida" ? ` · vence ${fechaHora(d.invitacion.expira_en)}` : ""}</p>
                {d.invitacion.envio_error && <p className="mt-1 text-destructive">{d.invitacion.envio_error}</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" disabled={ocupado !== null} onClick={() => invitacion("reenviar")}>
                    <RotateCcw className="h-4 w-4" aria-hidden /> Reenviar invitación
                  </Button>
                  {d.invitacion.estado !== "sin_invitacion" && (
                    <Button size="sm" variant="destructive" disabled={ocupado !== null} onClick={() => invitacion("revocar")}>
                      <XCircle className="h-4 w-4" aria-hidden /> Revocar
                    </Button>
                  )}
                </div>
              </section>
            )}

            <section aria-labelledby="t-ses">
              <h3 id="t-ses" className="font-semibold">Sesiones</h3>
              <label className="mt-2 block text-xs text-muted-foreground">
                Motivo para cerrar (queda en la auditoría)
                <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={200}
                  placeholder="Ej.: perdió el celular"
                  className="mt-1 block w-full rounded-lg border bg-background px-3 py-1.5 text-sm text-foreground" />
              </label>
              {d.sesiones.length === 0 ? (
                <p className="mt-2 text-muted-foreground">No hay sesiones registradas.</p>
              ) : (
                <ul className="mt-2 divide-y rounded-2xl border">
                  {d.sesiones.map((s) => {
                    const [et, color] = ESTADO_SESION[s.estado];
                    return (
                      <li key={s.id} className="flex flex-wrap items-start gap-2 p-3">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">
                            {s.dispositivo ?? "Dispositivo sin identificar"}{" "}
                            <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{et}</span>
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Inició {fechaHora(s.creada_en)} · último uso {fechaHora(s.ultimo_uso_en)}
                          </p>
                          {s.revocada_en && (
                            <p className="text-xs text-muted-foreground">
                              Cerrada {fechaHora(s.revocada_en)}{s.motivo ? ` · ${s.motivo}` : ""}{s.revocada_por ? ` · por ${s.revocada_por}` : ""}
                            </p>
                          )}
                        </div>
                        {s.estado === "activa" && (
                          <Button size="sm" variant="destructive" disabled={!motivoOk || ocupado !== null} onClick={() => cerrarUna(s)}
                            title={motivoOk ? undefined : "Escribí el motivo arriba"}>
                            {ocupado === `s${s.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" aria-hidden />} Cerrar
                          </Button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
              <Button className="mt-3" size="sm" variant="destructive" disabled={!motivoOk || ocupado !== null} onClick={cerrarTodas}>
                {ocupado === "todas" && <Loader2 className="h-4 w-4 animate-spin" />} Cerrar todas las sesiones
              </Button>
              {!motivoOk && <p className="mt-1 text-xs text-muted-foreground">Para cerrar sesiones, escribí primero el motivo.</p>}
            </section>

            <section aria-labelledby="t-hist">
              <h3 id="t-hist" className="font-semibold">Ingresos y cierres</h3>
              {d.historial.length === 0 ? (
                <p className="mt-1 text-muted-foreground">Sin movimientos.</p>
              ) : (
                <ol className="mt-2 space-y-1">
                  {d.historial.slice(0, 30).map((h, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="w-28 shrink-0 tabular-nums text-muted-foreground">{fechaHora(h.fecha)}</span>
                      <span>{h.tipo === "ingreso" ? "Ingresó" : "Se cerró"} · {h.detalle}{h.por ? ` (${h.por})` : ""}</span>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
              {d.notas.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
