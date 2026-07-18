"use client";

/**
 * La tarjeta de regalo tal como se ve / se imprime / se manda.
 *
 * - El protagonista es EL NEGOCIO (su nombre arriba); Turnos360 va chiquito
 *   al pie como sello ("Emitida con Turnos360" — marketing gratis en cada
 *   tarjeta que circula).
 * - Temas de color elegibles al momento de ver/imprimir: clásico navy, blanca,
 *   rosa, celeste, cumpleaños, regalo, Argentina y Halloween. No se guardan en
 *   la base: la misma gift card se puede reimprimir con otro tema.
 * - El monto va SIEMPRE en una sola línea (achica la letra si es largo).
 */

import { useState } from "react";
import { Printer, X } from "lucide-react";

import { GiftCard } from "@/lib/giftcards-api";
import { CodigoQR } from "@/components/codigo-qr";
import { Button } from "@/components/ui/button";

interface Tema {
  id: string;
  nombre: string;
  fondo: string;       // parte superior
  fondoMedio: string;  // franja del QR y datos
  acento: string;      // color del monto y la marquita
  texto: string;       // color del texto principal
  suave: string;       // texto secundario
  deco?: string;       // emoji decorativo del tema
}

const TEMAS: Tema[] = [
  { id: "clasico", nombre: "Clásico", fondo: "#0a0f1e", fondoMedio: "#111827", acento: "#00f5c4", texto: "#ffffff", suave: "rgba(255,255,255,0.55)" },
  { id: "blanco", nombre: "Elegante", fondo: "#ffffff", fondoMedio: "#f2f4f7", acento: "#0e6b5c", texto: "#0c1015", suave: "#6b7280" },
  { id: "rosa", nombre: "Rosa", fondo: "#fdf2f8", fondoMedio: "#fce7f3", acento: "#db2777", texto: "#500724", suave: "#9d5a7a" },
  { id: "celeste", nombre: "Celeste", fondo: "#eff6ff", fondoMedio: "#dbeafe", acento: "#1d4ed8", texto: "#172554", suave: "#5a76a8" },
  { id: "cumple", nombre: "Cumpleaños", fondo: "#faf5ff", fondoMedio: "#f3e8ff", acento: "#9333ea", texto: "#3b0764", suave: "#8b6aa8", deco: "🎂" },
  { id: "regalo", nombre: "Regalo", fondo: "#7f1d1d", fondoMedio: "#991b1b", acento: "#fecaca", texto: "#ffffff", suave: "rgba(255,255,255,0.6)", deco: "🎁" },
  { id: "argentina", nombre: "Argentina", fondo: "#74acdf", fondoMedio: "#5b9bd0", acento: "#fcd34d", texto: "#ffffff", suave: "rgba(255,255,255,0.75)", deco: "🇦🇷" },
  { id: "halloween", nombre: "Halloween", fondo: "#1c1917", fondoMedio: "#292524", acento: "#f97316", texto: "#ffffff", suave: "rgba(255,255,255,0.5)", deco: "🎃" },
];

function montoFmt(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

function fechaFmt(iso: string | null): string {
  if (!iso) return "Sin vencimiento";
  const [a, m, d] = iso.split("-");
  return `Vence ${d}/${m}/${a}`;
}

export function TarjetaGift({
  gc,
  nombreNegocio,
  onCerrar,
}: {
  gc: GiftCard;
  nombreNegocio?: string;
  onCerrar?: () => void;
}) {
  const [tema, setTema] = useState<Tema>(TEMAS[0]);

  const monto = montoFmt(gc.monto);
  // Monto SIEMPRE en una línea: si es largo (>$999.999) achica la letra.
  const tamMonto = monto.length > 8 ? "text-4xl" : "text-5xl";
  const negocio = (nombreNegocio ?? "").trim() || "Gift Card";

  function imprimir() {
    const ventana = window.open("", "_blank", "width=520,height=760");
    if (!ventana) return;
    const qrImg = document.getElementById(`qr-${gc.id}`)?.querySelector("img");
    const qrSrc = qrImg?.getAttribute("src") ?? "";
    const fontMonto = monto.length > 8 ? "44px" : "52px";
    ventana.document.write(`
      <html>
        <head><title>Gift Card ${gc.codigo}</title>
        <style>
          @page { margin: 0; }
          body { margin:0; font-family: Arial, sans-serif; }
          .card { width:420px; margin:24px auto; border-radius:20px; overflow:hidden;
                  background:${tema.fondo}; color:${tema.texto};
                  border:1px solid rgba(0,0,0,0.08); }
          .top { padding:28px 28px 18px; }
          .negocio { font-size:22px; font-weight:800; }
          .tit { font-size:13px; letter-spacing:2px; color:${tema.acento}; font-weight:bold;
                 text-transform:uppercase; margin-top:2px; }
          .monto { font-size:${fontMonto}; font-weight:800; color:${tema.acento};
                   margin:14px 0 4px; white-space:nowrap; }
          .mid { background:${tema.fondoMedio}; padding:22px 28px; display:flex; gap:20px; align-items:center; }
          .qr { background:#fff; padding:10px; border-radius:12px; }
          .qr img { display:block; width:130px; height:130px; }
          .codigo { font-size:19px; font-weight:800; letter-spacing:2px; }
          .lbl { font-size:10px; color:${tema.suave}; text-transform:uppercase; letter-spacing:1px; }
          .row { margin:8px 0; }
          .bot { padding:18px 28px 14px; font-size:12px; color:${tema.suave}; }
          .sello { padding:0 28px 16px; font-size:10px; color:${tema.suave}; letter-spacing:0.5px; }
          .deco { font-size:26px; float:right; }
        </style></head>
        <body>
          <div class="card">
            <div class="top">
              ${tema.deco ? `<span class="deco">${tema.deco}</span>` : ""}
              <div class="negocio">${negocio}</div>
              <div class="tit">Gift Card</div>
              <div class="monto">${monto}</div>
              ${gc.concepto ? `<div>${gc.concepto}</div>` : ""}
            </div>
            <div class="mid">
              <div class="qr"><img src="${qrSrc}" /></div>
              <div>
                <div class="row"><div class="lbl">Código</div><div class="codigo">${gc.codigo}</div></div>
                ${gc.beneficiario ? `<div class="row"><div class="lbl">Para</div><div>${gc.beneficiario}</div></div>` : ""}
                ${gc.de_parte_de ? `<div class="row"><div class="lbl">De parte de</div><div>${gc.de_parte_de}</div></div>` : ""}
              </div>
            </div>
            <div class="bot">
              ${gc.mensaje ? `"${gc.mensaje}"<br/><br/>` : ""}
              ${fechaFmt(gc.vence)} · Presentá este código en el local para canjearlo.
            </div>
            <div class="sello">Emitida con Turnos360</div>
          </div>
          <script>window.onload = () => { window.print(); }</script>
        </body>
      </html>`);
    ventana.document.close();
  }

  return (
    <div>
      {/* Selector de tema */}
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {TEMAS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTema(t)}
            title={t.nombre}
            aria-label={`Tema ${t.nombre}`}
            className="h-7 w-7 rounded-full border-2 transition-transform hover:scale-110"
            style={{
              background: `linear-gradient(135deg, ${t.fondo} 55%, ${t.acento} 55%)`,
              borderColor: tema.id === t.id ? "#17a08a" : "transparent",
            }}
          />
        ))}
        <span className="ml-1 text-xs text-muted-foreground">{tema.nombre}</span>
      </div>

      {/* Tarjeta en pantalla */}
      <div
        className="overflow-hidden rounded-3xl border border-black/10"
        style={{ background: tema.fondo, color: tema.texto }}
        id={`qr-${gc.id}`}
      >
        <div className="relative p-6 pb-4">
          {tema.deco && <span className="absolute right-5 top-5 text-3xl">{tema.deco}</span>}
          <p className="pr-10 text-xl font-extrabold leading-tight" style={{ fontFamily: "Syne, sans-serif" }}>
            {negocio}
          </p>
          <p className="mt-0.5 text-[11px] font-bold uppercase tracking-[0.2em]" style={{ color: tema.acento }}>
            Gift Card
          </p>
          <p
            className={`mt-3 ${tamMonto} whitespace-nowrap font-extrabold tabular-nums`}
            style={{ color: tema.acento, fontFamily: "Syne, sans-serif" }}
          >
            {monto}
          </p>
          {gc.concepto && (
            <p className="mt-1 text-sm" style={{ color: tema.suave }}>
              {gc.concepto}
            </p>
          )}
        </div>
        <div className="flex items-center gap-5 p-6" style={{ background: tema.fondoMedio }}>
          <div className="shrink-0 rounded-xl bg-white p-2.5">
            <CodigoQR texto={gc.codigo} tam={120} />
          </div>
          <div className="min-w-0 space-y-2.5">
            <div>
              <p className="text-[10px] uppercase tracking-wider" style={{ color: tema.suave }}>
                Código
              </p>
              <p className="text-lg font-extrabold tracking-wider">{gc.codigo}</p>
            </div>
            {gc.beneficiario && (
              <div>
                <p className="text-[10px] uppercase tracking-wider" style={{ color: tema.suave }}>
                  Para
                </p>
                <p className="truncate text-sm">{gc.beneficiario}</p>
              </div>
            )}
            {gc.de_parte_de && (
              <div>
                <p className="text-[10px] uppercase tracking-wider" style={{ color: tema.suave }}>
                  De parte de
                </p>
                <p className="truncate text-sm">{gc.de_parte_de}</p>
              </div>
            )}
          </div>
        </div>
        <div className="p-5 pb-2 text-xs" style={{ color: tema.suave }}>
          {gc.mensaje && <p className="mb-2 italic">&ldquo;{gc.mensaje}&rdquo;</p>}
          {fechaFmt(gc.vence)} · Presentá este código en el local para canjearlo.
        </div>
        <p className="px-5 pb-4 text-[10px] tracking-wide" style={{ color: tema.suave }}>
          Emitida con Turnos360
        </p>
      </div>

      <div className="mt-4 flex gap-2">
        <Button onClick={imprimir} className="flex-1">
          <Printer className="mr-1.5 h-4 w-4" /> Imprimir / Guardar PDF
        </Button>
        {onCerrar && (
          <Button variant="outline" onClick={onCerrar}>
            <X className="mr-1.5 h-4 w-4" /> Cerrar
          </Button>
        )}
      </div>
    </div>
  );
}
