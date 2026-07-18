"use client";

/**
 * Validador de gift cards. El comercio escribe (o escanea al teclado) el
 * código y verifica: el sistema dice si es genuino, y con un segundo click
 * lo canjea de forma definitiva. Un código ya canjeado o vencido se rechaza.
 *
 * El "escaneo" del QR con la cámara queda para más adelante (requiere permisos
 * y una lib de lectura); por ahora el flujo real es tipear el código, que es
 * corto y a prueba de errores (GIFT-XXXX-XXXX, sin caracteres ambiguos).
 */

import { useState } from "react";
import { CheckCircle2, XCircle, Search, BadgeCheck } from "lucide-react";
import { toast } from "sonner";

import {
  verificarGiftCard,
  canjearGiftCard,
  GiftCardVerificacion,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function montoFmt(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

const MOTIVOS: Record<string, string> = {
  "no existe": "Ese código no existe en este negocio.",
  "ya canjeada": "Esta gift card YA fue canjeada.",
  vencida: "Esta gift card está vencida.",
};

export function ValidadorGift({ onCanjeada }: { onCanjeada: () => void }) {
  const [codigo, setCodigo] = useState("");
  const [res, setRes] = useState<GiftCardVerificacion | null>(null);
  const [cargando, setCargando] = useState(false);
  const [canjeando, setCanjeando] = useState(false);
  const [confirmarCanje, setConfirmarCanje] = useState(false);

  async function verificar() {
    const c = codigo.trim();
    if (!c) return;
    setCargando(true);
    setRes(null);
    try {
      setRes(await verificarGiftCard(c));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo verificar");
    } finally {
      setCargando(false);
    }
  }

  async function canjear() {
    if (!res?.gift_card) return;
    setConfirmarCanje(false);
    setCanjeando(true);
    try {
      const r = await canjearGiftCard(res.gift_card.codigo);
      setRes(r);
      if (r.valida) {
        toast.success("Gift card canjeada");
        onCanjeada();
      } else {
        toast.error(MOTIVOS[r.motivo ?? ""] ?? "No se pudo canjear");
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo canjear");
    } finally {
      setCanjeando(false);
    }
  }

  const gc = res?.gift_card;
  const yaCanjeada = gc?.estado === "canjeada" && res?.valida === false;

  return (
    <div className="rounded-2xl border bg-card p-5">
      <div className="flex items-center gap-2">
        <BadgeCheck className="h-5 w-5 text-primary" />
        <h2 className="font-[family-name:var(--font-syne)] text-lg font-semibold">
          Validar / canjear
        </h2>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Escribí el código de la gift card para verificar que sea genuina y canjearla.
      </p>

      <div className="mt-4 flex items-end gap-2">
        <div className="flex-1 space-y-1.5">
          <Label className="text-xs text-muted-foreground">Código</Label>
          <Input
            placeholder="GIFT-XXXX-XXXX"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && verificar()}
            className="font-mono tracking-wider"
            autoComplete="off"
          />
        </div>
        <Button onClick={verificar} disabled={cargando}>
          <Search className="mr-1.5 h-4 w-4" />
          {cargando ? "Buscando…" : "Verificar"}
        </Button>
      </div>

      {/* Resultado */}
      {res && (
        <div
          className="mt-4 rounded-xl border p-4"
          style={
            res.valida
              ? { borderColor: "#17a08a", background: "#e8f7f0" }
              : { borderColor: "#e5484d", background: "#fdecec" }
          }
        >
          {res.valida && gc ? (
            <>
              <div className="flex items-center gap-2 text-[#0e6b5c]">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-bold">Gift card válida</span>
              </div>
              <div className="mt-2 space-y-0.5 text-sm text-[#0e6b5c]">
                <p className="text-2xl font-extrabold">{montoFmt(gc.monto)}</p>
                {gc.concepto && <p>{gc.concepto}</p>}
                {gc.beneficiario && <p>Para: {gc.beneficiario}</p>}
                {gc.vence && <p className="text-xs">Vence: {gc.vence.split("-").reverse().join("/")}</p>}
              </div>
              <Button
                onClick={() => setConfirmarCanje(true)}
                disabled={canjeando}
                className="mt-3 w-full"
                style={{ background: "#17a08a" }}
              >
                {canjeando ? "Canjeando…" : "Canjear ahora…"}
              </Button>
            </>
          ) : (
            <div>
              <div className="flex items-center gap-2 text-[#9f1d21]">
                <XCircle className="h-5 w-5" />
                <span className="font-bold">
                  {res.valida === false && gc && res.motivo === "ya canjeada"
                    ? "Recién canjeada"
                    : "No válida"}
                </span>
              </div>
              <p className="mt-1 text-sm text-[#9f1d21]">
                {MOTIVOS[res.motivo ?? ""] ?? "No se pudo validar el código."}
              </p>
              {yaCanjeada && gc?.canjeada_en && (
                <p className="mt-1 text-xs text-[#9f1d21]">
                  Canjeada el {new Date(gc.canjeada_en).toLocaleDateString("es-AR")}
                  {gc.canjeada_por ? ` por ${gc.canjeada_por}` : ""}.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Doble confirmación: el canje es definitivo, no se puede deshacer. */}
      <AlertDialog open={confirmarCanje} onOpenChange={setConfirmarCanje}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Canjear esta gift card?</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a canjear <b>{gc?.codigo}</b> por{" "}
              <b>{gc ? montoFmt(gc.monto) : ""}</b>
              {gc?.beneficiario ? ` (para ${gc.beneficiario})` : ""}. Esta acción
              es <b>definitiva</b>: la tarjeta queda usada y no se puede volver
              atrás.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={canjear} style={{ background: "#17a08a" }}>
              Sí, canjear
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
