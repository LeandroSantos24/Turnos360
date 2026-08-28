"use client";

/**
 * Piezas compartidas entre los tabs de la ficha clínica del paciente:
 * secciones con card, campos con label, y el botón de borrar con
 * confirmación inline (primer click pregunta, segundo confirma).
 */

import { Trash2 } from "lucide-react";
import { useConfirmar } from "@/components/confirmar";

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

/**
 * Borrar un registro de la ficha del cliente (evolución, medición, adjunto).
 *
 * Antes esto confirmaba "inline": primer click ponía "¿Seguro?" y el segundo
 * borraba, con 3 s de ventana. El problema es que un DOBLE CLICK entra como
 * dos clicks seguidos y borraba el registro al instante, sin que nadie llegue
 * a leer la advertencia. Y lo que hay detrás de este botón —historia clínica,
 * mediciones, adjuntos— es lo menos recuperable de todo el sistema: no hay
 * papelera ni baja lógica.
 *
 * Ahora usa el mismo diálogo modal que el resto de las acciones críticas, que
 * además obliga a mover el mouse a otro botón antes de confirmar.
 */
export function BotonBorrar({
  onConfirm,
  deshabilitado = false,
  que = "este registro",
}: {
  onConfirm: () => void;
  deshabilitado?: boolean;
  /** Qué se borra, para nombrarlo en el diálogo: "esta medición", "el adjunto…". */
  que?: string;
}) {
  const confirmar = useConfirmar();

  async function click() {
    if (
      !(await confirmar({
        titulo: `¿Borrar ${que}?`,
        descripcion:
          "Se elimina de la ficha del cliente y no se puede recuperar.",
        textoAccion: "Sí, borrar",
        destructivo: true,
      }))
    )
      return;
    onConfirm();
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={deshabilitado}
      onClick={click}
    >
      <Trash2 className="mr-1 h-3.5 w-3.5" />
      Borrar
    </Button>
  );
}
