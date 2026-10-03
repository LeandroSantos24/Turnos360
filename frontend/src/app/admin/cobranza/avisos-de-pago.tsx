"use client";

/**
 * Pagos pendientes de revisión: los negocios que informaron una transferencia.
 *
 * Un aviso NO es una cuota cobrada: una transferencia tarda en verse en la
 * cuenta, y dar por pagado lo que alguien dice que pagó convierte el MRR en un
 * número de buena fe. Esto es la lista de lo que hay que ir a buscar al banco.
 *
 * Cada fila muestra lo avisado al lado de lo ESPERADO (que fijó el servidor al
 * recibir el aviso, con el plan que se está comprando). «Revisar» abre todo el
 * contexto —comprobante incluido— y las tres salidas posibles: Aprobar,
 * Rechazar o Solicitar información. Las tres piden una segunda confirmación
 * que dice exactamente qué va a pasar.
 *
 * Los pagos por Mercado Pago no aparecen acá: los confirma el webhook contra
 * la API de MP.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Clock, FileImage, MessageSquare } from "lucide-react";
import { toast } from "sonner";

import {
  AvisoPago,
  aprobarAvisoPago,
  descartarAvisoPago,
  listarAvisosPago,
  solicitarInfoAviso,
  verComprobante,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function cuando(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

/** "2026-10-14" -> "14/10/2026" sin pasar por Date (evita el corrimiento de zona). */
function fecha(iso: string | null): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

const PESOS = (n: number | null | undefined) =>
  n == null ? "—" : `$${Number(n).toLocaleString("es-AR")}`;

const TIPO: Record<string, string> = {
  alta: "Pago inicial",
  renovacion: "Renovación",
  cambio_plan: "Cambio de plan",
  reactivacion: "Reactivación",
};

export function AvisosDePago({
  recargar = 0,
  onCambio,
}: {
  /** Se vuelve a pedir la lista cada vez que este número cambia. */
  recargar?: number;
  /** Después de aprobar/rechazar: el resto del panel se recarga. */
  onCambio?: () => void;
}) {
  const [avisos, setAvisos] = useState<AvisoPago[]>([]);
  const [revisando, setRevisando] = useState<AvisoPago | null>(null);

  const cargar = useCallback(async () => {
    try {
      setAvisos(await listarAvisosPago());
    } catch {
      setAvisos([]);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar, recargar]);

  if (avisos.length === 0) return null;

  const pendientes = avisos.filter((a) => a.estado === "pendiente");
  const esperando = avisos.length - pendientes.length;

  return (
    <div id="pagos-pendientes" className="scroll-mt-4 rounded-2xl border border-sky-500/40 bg-sky-500/5 p-4">
      <p className="flex items-center gap-2 font-medium">
        <Clock className="h-4 w-4 text-sky-600 dark:text-sky-400" />
        Pagos pendientes de revisión
        <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-xs font-semibold text-sky-700 dark:text-sky-300">
          {pendientes.length}
        </span>
      </p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Buscá cada transferencia en el banco y revisala.
        {esperando > 0 && ` ${esperando} esperando respuesta del negocio.`}
      </p>

      {/* Escritorio: tabla. Celular: tarjetas. */}
      <div className="mt-3 hidden overflow-x-auto rounded-xl border bg-background md:block">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Empresa</th>
              <th className="px-3 py-2 font-medium">Plan</th>
              <th className="px-3 py-2 text-right font-medium">Informado</th>
              <th className="px-3 py-2 text-right font-medium">Esperado</th>
              <th className="px-3 py-2 font-medium">Fecha</th>
              <th className="px-3 py-2 font-medium">Referencia</th>
              <th className="px-3 py-2 font-medium">Estado</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {avisos.map((a) => (
              <tr key={a.id} className={a.coincide ? undefined : "bg-amber-500/[0.04]"}>
                <td className="px-3 py-2.5 font-medium">{a.empresa_nombre}</td>
                <td className="px-3 py-2.5">
                  {a.plan_etiqueta}
                  <span className="block text-xs text-muted-foreground">{TIPO[a.tipo] ?? a.tipo}</span>
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">{PESOS(a.monto)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  {PESOS(a.monto_esperado)}
                  {a.coincide ? (
                    <Check className="ml-1 inline h-3.5 w-3.5 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="ml-1 inline h-3.5 w-3.5 text-amber-600" />
                  )}
                </td>
                <td className="px-3 py-2.5 whitespace-nowrap text-muted-foreground">{cuando(a.creado_en)}</td>
                <td className="max-w-[180px] truncate px-3 py-2.5 font-mono text-xs" title={a.referencia ?? ""}>
                  {a.referencia ?? "—"}
                  {a.tiene_comprobante && <FileImage className="ml-1 inline h-3.5 w-3.5 text-sky-600" />}
                </td>
                <td className="px-3 py-2.5">
                  <EstadoAviso estado={a.estado} />
                </td>
                <td className="px-3 py-2.5 text-right">
                  <Button size="sm" onClick={() => setRevisando(a)}>
                    Revisar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 space-y-2 md:hidden">
        {avisos.map((a) => (
          <div key={a.id} className="rounded-xl border bg-background p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-medium">{a.empresa_nombre}</p>
                <p className="text-xs text-muted-foreground">
                  {a.plan_etiqueta} · {cuando(a.creado_en)}
                </p>
              </div>
              <EstadoAviso estado={a.estado} />
            </div>
            <div className="mt-2 flex items-center justify-between gap-2 text-sm">
              <span>
                <span className="font-semibold tabular-nums">{PESOS(a.monto)}</span>
                <span className="text-muted-foreground"> / esperado {PESOS(a.monto_esperado)}</span>
              </span>
              <Button size="sm" onClick={() => setRevisando(a)}>
                Revisar
              </Button>
            </div>
          </div>
        ))}
      </div>

      {revisando && (
        <DialogRevisar
          aviso={revisando}
          onCerrar={() => setRevisando(null)}
          onListo={() => {
            setRevisando(null);
            cargar();
            onCambio?.();
          }}
        />
      )}
    </div>
  );
}

function EstadoAviso({ estado }: { estado: AvisoPago["estado"] }) {
  return estado === "info_solicitada" ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
      <MessageSquare className="h-3 w-3" /> Esperando respuesta
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-700 dark:text-sky-400">
      <Clock className="h-3 w-3" /> En revisión
    </span>
  );
}

/** Los motivos que se repiten. Escribirlos a mano cada vez termina en «no». */
const MOTIVOS = [
  "No apareció en el banco",
  "Vino por otro importe",
  "Ya estaba cobrado (duplicado)",
  "No pude identificar quién la mandó",
];

type Modo = "ver" | "aprobar" | "rechazar" | "info";

/**
 * Revisar un pago: todo el contexto en una pantalla y las tres salidas.
 *
 * Paso 1 = elegir la acción y completar lo que pide (monto, motivo, mensaje).
 * Paso 2 = la confirmación, que repite empresa, monto y consecuencia.
 */
function DialogRevisar({
  aviso,
  onCerrar,
  onListo,
}: {
  aviso: AvisoPago;
  onCerrar: () => void;
  onListo: () => void;
}) {
  const confirmar = useConfirmar();
  const [modo, setModo] = useState<Modo>("ver");
  const [monto, setMonto] = useState(String(aviso.monto ?? aviso.monto_esperado ?? ""));
  const [motivo, setMotivo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [imagen, setImagen] = useState<string | null>(null);
  const [cargandoImg, setCargandoImg] = useState(false);

  useEffect(() => {
    return () => {
      if (imagen) URL.revokeObjectURL(imagen);
    };
  }, [imagen]);

  async function abrirComprobante() {
    setCargandoImg(true);
    try {
      setImagen(await verComprobante(aviso.id));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo abrir el comprobante");
    } finally {
      setCargandoImg(false);
    }
  }

  const valor = Number(monto);
  const difiere = aviso.monto_esperado != null && !!valor && Math.abs(valor - aviso.monto_esperado) >= 1;
  const cambiaPlan = aviso.plan_etiqueta !== aviso.plan_actual_etiqueta;

  async function ejecutar() {
    let ok = false;
    if (modo === "aprobar") {
      if (!valor || valor <= 0) {
        toast.error("Ingresá el monto que entró");
        return;
      }
      ok = await confirmar({
        titulo: `¿Aprobar el pago de ${PESOS(valor)} de ${aviso.empresa_nombre}?`,
        descripcion:
          `Se registra la cuota${cambiaPlan ? `, pasa de ${aviso.plan_actual_etiqueta} a ${aviso.plan_etiqueta}` : ""} ` +
          `y el vencimiento se corre 30 días (hoy: ${fecha(aviso.vence)}).` +
          (difiere ? ` Ojo: lo esperado era ${PESOS(aviso.monto_esperado)}.` : ""),
        textoAccion: "Sí, aprobar pago",
        textoCancelar: "Volver",
      });
      if (!ok) return;
    } else if (modo === "rechazar") {
      ok = await confirmar({
        titulo: `¿Rechazar la transferencia de ${aviso.empresa_nombre}?`,
        descripcion: `No se registra ninguna cuota y el negocio ve el motivo: «${motivo || "sin motivo"}». La suscripción vuelve al estado que tenía.`,
        textoAccion: "Sí, rechazar",
        textoCancelar: "Volver",
        destructivo: true,
      });
      if (!ok) return;
    } else if (modo === "info") {
      if (mensaje.trim().length < 3) {
        toast.error("Escribí qué necesitás");
        return;
      }
      ok = await confirmar({
        titulo: `¿Enviarle este pedido a ${aviso.empresa_nombre}?`,
        descripcion: `«${mensaje.trim()}». El pago sigue en revisión y el negocio lo ve en «Mi suscripción».`,
        textoAccion: "Sí, enviar",
        textoCancelar: "Volver",
      });
      if (!ok) return;
    }

    setEnviando(true);
    try {
      if (modo === "aprobar") {
        await aprobarAvisoPago(aviso.id, { monto: valor });
        toast.success(`Pago de ${aviso.empresa_nombre} aprobado`);
      } else if (modo === "rechazar") {
        await descartarAvisoPago(aviso.id, motivo);
        toast.success("Transferencia rechazada");
      } else if (modo === "info") {
        await solicitarInfoAviso(aviso.id, mensaje.trim());
        toast.success("Pedido enviado");
      }
      onListo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo completar la acción");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !enviando && onCerrar()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: "var(--fuente-titulos)" }}>
            Revisar pago · {aviso.empresa_nombre}
          </DialogTitle>
          <DialogDescription>
            {TIPO[aviso.tipo] ?? aviso.tipo} · informado el {cuando(aviso.creado_en)}
            {aviso.avisado_por ? ` por ${aviso.avisado_por}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3 rounded-xl border p-3">
            <div>
              <p className="text-xs text-muted-foreground">Informó</p>
              <p className="text-lg font-bold tabular-nums">{PESOS(aviso.monto)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Se esperaba</p>
              <p className="text-lg font-bold tabular-nums">{PESOS(aviso.monto_esperado)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Plan</p>
              <p className="font-medium">
                {cambiaPlan ? `${aviso.plan_actual_etiqueta} → ${aviso.plan_etiqueta}` : aviso.plan_etiqueta}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Vence hoy</p>
              <p className="font-medium">{fecha(aviso.vence)}</p>
            </div>
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground">Referencia</p>
              <p className="break-all font-mono text-xs">{aviso.referencia ?? "—"}</p>
            </div>
          </div>

          {!aviso.coincide && (
            <p className="flex items-center gap-2 rounded-xl border border-amber-500/50 bg-amber-500/5 p-2.5 text-amber-800 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              El monto informado no coincide con lo esperado.
            </p>
          )}

          {aviso.mensaje_admin && (
            <p className="rounded-xl border bg-muted/40 p-2.5">
              <span className="text-muted-foreground">Le pediste: </span>
              {aviso.mensaje_admin}
            </p>
          )}

          {aviso.tiene_comprobante && (
            <div className="rounded-xl border p-2.5">
              {imagen ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagen} alt="Comprobante de la transferencia" className="max-h-80 w-full rounded-lg object-contain" />
              ) : (
                <Button size="sm" variant="outline" onClick={abrirComprobante} disabled={cargandoImg}>
                  <FileImage className="mr-1.5 h-4 w-4" />
                  {cargandoImg ? "Abriendo…" : "Ver comprobante"}
                </Button>
              )}
            </div>
          )}

          {modo === "ver" && (
            <div className="grid gap-2 pt-1 sm:grid-cols-3">
              <Button onClick={() => setModo("aprobar")}>Aprobar</Button>
              <Button variant="destructive" onClick={() => setModo("rechazar")}>
                Rechazar
              </Button>
              <Button variant="outline" onClick={() => setModo("info")}>
                Pedir info
              </Button>
            </div>
          )}

          {modo === "aprobar" && (
            <div className="space-y-2 rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-3">
              <label className="block space-y-1.5">
                <span className="text-muted-foreground">Monto que entró en el banco</span>
                <Input type="number" value={monto} onChange={(e) => setMonto(e.target.value)} />
              </label>
              {difiere && (
                <button
                  type="button"
                  className="text-xs underline"
                  onClick={() => setMonto(String(aviso.monto_esperado))}
                >
                  Usar lo esperado ({PESOS(aviso.monto_esperado)})
                </button>
              )}
            </div>
          )}

          {modo === "rechazar" && (
            <div className="space-y-2 rounded-xl border border-red-500/40 bg-red-500/5 p-3">
              <div className="flex flex-wrap gap-1.5">
                {MOTIVOS.map((m) => (
                  <button
                    key={m}
                    onClick={() => setMotivo(m)}
                    className={`rounded-full border px-2.5 py-1 text-xs transition ${
                      motivo === m ? "border-primary bg-primary/10 font-medium" : "hover:bg-muted/50"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <Input
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                placeholder="O escribí el motivo…"
                maxLength={200}
              />
            </div>
          )}

          {modo === "info" && (
            <div className="space-y-2 rounded-xl border p-3">
              <Textarea
                value={mensaje}
                onChange={(e) => setMensaje(e.target.value)}
                placeholder="Ej: Mandanos el comprobante o el número de operación"
                maxLength={300}
              />
            </div>
          )}

          {modo !== "ver" && (
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setModo("ver")} disabled={enviando}>
                Volver
              </Button>
              <Button
                variant={modo === "rechazar" ? "destructive" : "default"}
                onClick={ejecutar}
                disabled={enviando}
              >
                {enviando
                  ? "Un momento…"
                  : modo === "aprobar"
                    ? "Aprobar pago"
                    : modo === "rechazar"
                      ? "Rechazar transferencia"
                      : "Enviar pedido"}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
