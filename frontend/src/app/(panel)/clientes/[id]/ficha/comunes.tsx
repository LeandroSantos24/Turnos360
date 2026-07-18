"use client";

/**
 * Piezas compartidas entre los tabs de la ficha clínica del paciente:
 * secciones con card, campos con label, y el botón de borrar con
 * confirmación inline (primer click pregunta, segundo confirma).
 */

import { useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** Una sección con título Syne y card (patrón visual del panel). */
export function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <Card className="space-y-4 rounded-2xl p-5">
      <h2 className="font-[family-name:var(--font-syne)] text-lg font-semibold">{titulo}</h2>
      {children}
    </Card>
  );
}

/** Un input corto con label. */
export function Campo({
  label, valor, onChange, tipo = "text", placeholder,
}: {
  label: string;
  valor: string;
  onChange: (v: string) => void;
  tipo?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input type={tipo} value={valor} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

/** Un textarea con label, para texto largo. */
export function CampoArea({
  label, valor, onChange, rows = 2, placeholder,
}: {
  label: string;
  valor: string;
  onChange: (v: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Textarea rows={rows} value={valor} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

/** Input numérico compacto para mediciones (label chico arriba). */
export function CampoNum({
  label, valor, onChange, sufijo,
}: {
  label: string;
  valor: string;
  onChange: (v: string) => void;
  sufijo?: string;
}) {
  return (
    <div className="space-y-1">
      <Label className="block truncate text-[11px] text-muted-foreground" title={label}>
        {label}
        {sufijo ? <span className="opacity-70"> ({sufijo})</span> : null}
      </Label>
      <Input
        type="number"
        inputMode="decimal"
        step="0.1"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        className="h-9"
      />
    </div>
  );
}

/** "YYYY-MM-DD" → "dd/mm/aaaa" sin corrimientos de zona horaria. */
export function fechaLegible(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

/** Hoy como "YYYY-MM-DD" en hora local (para defaults de formularios). */
export function hoyISO(): string {
  const h = new Date();
  const mm = String(h.getMonth() + 1).padStart(2, "0");
  const dd = String(h.getDate()).padStart(2, "0");
  return `${h.getFullYear()}-${mm}-${dd}`;
}

/** Borrar con confirmación inline: 1er click pregunta, 2do confirma (3s para arrepentirse). */
export function BotonBorrar({
  onConfirm, deshabilitado = false,
}: {
  onConfirm: () => void;
  deshabilitado?: boolean;
}) {
  const [confirmando, setConfirmando] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  function click() {
    if (!confirmando) {
      setConfirmando(true);
      timer.current = setTimeout(() => setConfirmando(false), 3000);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    setConfirmando(false);
    onConfirm();
  }

  return (
    <Button
      type="button"
      variant={confirmando ? "destructive" : "ghost"}
      size="sm"
      disabled={deshabilitado}
      onClick={click}
    >
      <Trash2 className="mr-1 h-3.5 w-3.5" />
      {confirmando ? "¿Seguro?" : "Borrar"}
    </Button>
  );
}
