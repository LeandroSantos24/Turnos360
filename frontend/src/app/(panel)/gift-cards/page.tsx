"use client";

/**
 * Gift cards (/gift-cards). Tres partes:
 * - Generar: el formulario que crea una tarjeta nueva (código único auto).
 * - Validar / canjear: el escáner por código.
 * - Listado: todas las tarjetas con su estado, para reimprimir o borrar.
 *
 * Gateada por el módulo gift_cards del preset (barbería lo tiene; nutrición no).
 */

import { useCallback, useEffect, useState } from "react";
import { Gift, Plus, Printer, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  listarGiftCards,
  crearGiftCard,
  borrarGiftCard,
  GiftCard,
} from "@/lib/giftcards-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { obtenerConfigEmpresa } from "@/lib/empresa-api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TarjetaGift } from "./tarjeta-gift";
import { ValidadorGift } from "./validador-gift";

function montoFmt(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

const ESTADO_CHIP: Record<string, { txt: string; cls: string }> = {
  activa: { txt: "Activa", cls: "bg-emerald-400/15 text-emerald-600 dark:text-emerald-400" },
  canjeada: { txt: "Canjeada", cls: "bg-muted text-muted-foreground" },
  vencida: { txt: "Vencida", cls: "bg-orange-400/15 text-orange-600 dark:text-orange-400" },
};

export default function GiftCardsPage() {
  const [cards, setCards] = useState<GiftCard[]>([]);
  const [cargando, setCargando] = useState(true);
  const [creando, setCreando] = useState(false);
  const [ver, setVer] = useState<GiftCard | null>(null);
  const [aBorrar, setABorrar] = useState<GiftCard | null>(null);
  const [nombreNegocio, setNombreNegocio] = useState("");

  // Form de alta
  const [monto, setMonto] = useState("");
  const [concepto, setConcepto] = useState("");
  const [beneficiario, setBeneficiario] = useState("");
  const [deParte, setDeParte] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [vence, setVence] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setCards(await listarGiftCards());
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudieron cargar las gift cards");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
    obtenerConfigEmpresa()
      .then((c) => setNombreNegocio(c.nombre))
      .catch(() => {});
  }, [cargar]);

  async function generar() {
    const m = Number(monto);
    if (!m || m <= 0) {
      toast.error("Poné un monto válido");
      return;
    }
    setGuardando(true);
    try {
      const gc = await crearGiftCard({
        monto: m,
        concepto: concepto.trim() || null,
        beneficiario: beneficiario.trim() || null,
        de_parte_de: deParte.trim() || null,
        mensaje: mensaje.trim() || null,
        vence: vence || null,
      });
      toast.success("Gift card generada");
      setMonto(""); setConcepto(""); setBeneficiario(""); setDeParte(""); setMensaje(""); setVence("");
      setCreando(false);
      setCards((prev) => [gc, ...prev]);
      setVer(gc); // abre la tarjeta lista para imprimir
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo generar");
    } finally {
      setGuardando(false);
    }
  }

  async function borrar(id: number) {
    setABorrar(null);
    try {
      await borrarGiftCard(id);
      setCards((prev) => prev.filter((c) => c.id !== id));
      toast.success("Gift card eliminada");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo eliminar");
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Gift className="h-6 w-6 text-primary" />
          <h1 className="font-[family-name:var(--font-syne)] text-2xl font-bold">Gift cards</h1>
        </div>
        {!creando && (
          <Button onClick={() => setCreando(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> Nueva gift card
          </Button>
        )}
      </div>

      {/* Alta */}
      {creando && (
        <div className="rounded-2xl border bg-card p-5">
          <h2 className="font-[family-name:var(--font-syne)] text-lg font-semibold">
            Generar gift card
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Monto (ARS) *</Label>
              <Input type="number" inputMode="numeric" min={0} placeholder="10000" value={monto} onChange={(e) => setMonto(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Concepto (opcional)</Label>
              <Input placeholder="Corte + barba" value={concepto} onChange={(e) => setConcepto(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Para (opcional)</Label>
              <Input placeholder="Nombre de quien recibe" value={beneficiario} onChange={(e) => setBeneficiario(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">De parte de (opcional)</Label>
              <Input placeholder="Quien regala" value={deParte} onChange={(e) => setDeParte(e.target.value)} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="text-xs text-muted-foreground">Mensaje (opcional)</Label>
              <Input placeholder="¡Feliz cumple!" value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Vencimiento (opcional)</Label>
              <Input type="date" value={vence} onChange={(e) => setVence(e.target.value)} />
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCreando(false)}>Cancelar</Button>
            <Button onClick={generar} disabled={guardando}>
              {guardando ? "Generando…" : "Generar y ver tarjeta"}
            </Button>
          </div>
        </div>
      )}

      {/* Validador */}
      <ValidadorGift onCanjeada={cargar} />

      {/* Listado */}
      <div>
        <h2 className="mb-3 font-[family-name:var(--font-syne)] text-lg font-semibold">
          Emitidas
        </h2>
        {cargando ? (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        ) : cards.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Todavía no generaste ninguna gift card.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-2xl border bg-card">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5">Código</th>
                  <th className="px-4 py-2.5">Monto</th>
                  <th className="px-4 py-2.5">Para</th>
                  <th className="px-4 py-2.5">Estado</th>
                  <th className="px-4 py-2.5">Vence</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {cards.map((c) => {
                  const chip = ESTADO_CHIP[c.estado] ?? ESTADO_CHIP.activa;
                  return (
                    <tr key={c.id} className="border-b last:border-0">
                      <td className="px-4 py-2.5 font-mono font-medium tracking-wider">{c.codigo}</td>
                      <td className="px-4 py-2.5 font-semibold tabular-nums">{montoFmt(c.monto)}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.beneficiario ?? "—"}</td>
                      <td className="px-4 py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${chip.cls}`}>
                          {chip.txt}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">
                        {c.vence ? c.vence.split("-").reverse().join("/") : "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => setVer(c)}>
                            <Printer className="h-3.5 w-3.5" />
                          </Button>
                          {c.estado !== "canjeada" && (
                            <Button variant="ghost" size="sm" onClick={() => setABorrar(c)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Doble confirmación de borrado */}
      <AlertDialog open={aBorrar !== null} onOpenChange={(o) => !o && setABorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar esta gift card?</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a eliminar <b>{aBorrar?.codigo}</b>
              {aBorrar ? ` (${`$${Number(aBorrar.monto).toLocaleString("es-AR")}`})` : ""}.
              Si ya la entregaste, el código dejará de ser válido. Esta acción no
              se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => aBorrar && borrar(aBorrar.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Modal de la tarjeta */}
      <Dialog open={!!ver} onOpenChange={(o) => !o && setVer(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Gift card</DialogTitle>
          </DialogHeader>
          {ver && <TarjetaGift gc={ver} nombreNegocio={nombreNegocio} onCerrar={() => setVer(null)} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
