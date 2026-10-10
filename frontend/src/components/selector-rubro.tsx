"use client";

/**
 * Elegir el rubro con tarjetas visuales (foto, nombre, descripción).
 *
 * Es un grupo de radio: Tab entra al grupo, las flechas mueven la selección y
 * el elegido queda marcado con borde y tilde. Si una foto no carga, la tarjeta
 * cae a un fondo con el ícono del rubro en vez de mostrar una imagen rota.
 */

import { useRef, useState } from "react";
import { Check } from "lucide-react";

import { infoRubro, ordenarRubros } from "@/lib/rubros";

export interface OpcionRubro {
  codigo: string;
  nombre: string;
}

export function SelectorRubro({
  rubros,
  valor,
  onCambio,
  etiqueta = "Rubro del negocio",
  compacto = false,
}: {
  rubros: OpcionRubro[];
  valor: string;
  onCambio: (codigo: string) => void;
  etiqueta?: string;
  /** Tarjetas más bajas (para formularios dentro de un diálogo). */
  compacto?: boolean;
}) {
  const ordenados = ordenarRubros(rubros);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function teclas(e: React.KeyboardEvent, i: number) {
    const mover = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!mover) return;
    e.preventDefault();
    const sig = (i + mover + ordenados.length) % ordenados.length;
    onCambio(ordenados[sig].codigo);
    refs.current[sig]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={etiqueta}
      className={`grid gap-3 ${compacto ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"}`}
    >
      {ordenados.map((r, i) => {
        const elegido = r.codigo === valor;
        const activoEnTab = elegido || (!valor && i === 0);
        return (
          <button
            key={r.codigo}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={elegido}
            tabIndex={activoEnTab ? 0 : -1}
            onClick={() => onCambio(r.codigo)}
            onKeyDown={(e) => teclas(e, i)}
            className={`group relative overflow-hidden rounded-2xl border bg-card text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 motion-safe:hover:-translate-y-0.5 ${
              elegido ? "border-primary ring-2 ring-primary/60" : "hover:border-foreground/20 hover:shadow-md"
            }`}
          >
            <FotoRubro codigo={r.codigo} compacto={compacto} />
            <span className="block p-3">
              <span className="block text-sm font-semibold leading-tight">{r.nombre}</span>
              {!compacto && (
                <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                  {infoRubro(r.codigo).descripcion}
                </span>
              )}
            </span>
            {elegido && (
              <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground shadow">
                <Check className="h-4 w-4" aria-hidden />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function FotoRubro({ codigo, compacto = false, className = "" }: { codigo: string; compacto?: boolean; className?: string }) {
  const info = infoRubro(codigo);
  const [fallo, setFallo] = useState(false);
  const Icono = info.icono;
  const alto = compacto ? "aspect-[16/9]" : "aspect-[4/3]";
  if (!info.imagen || fallo) {
    return (
      <span className={`flex ${alto} w-full items-center justify-center bg-gradient-to-br from-primary/15 to-muted ${className}`}>
        <Icono className="h-8 w-8 text-foreground/50" aria-hidden />
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={info.imagen}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setFallo(true)}
      className={`block ${alto} w-full object-cover transition-transform duration-300 motion-safe:group-hover:scale-[1.03] ${className}`}
    />
  );
}
