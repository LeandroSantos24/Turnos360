"use client";

/**
 * Gráfico de línea SVG casero (sin dependencias) para la evolución temporal
 * de una métrica del paciente: peso, IMC, cintura, sumatoria de pliegues…
 * Mismo espíritu que graficos/torta.tsx: liviano y del color del tema.
 */

import { useMemo } from "react";

export interface PuntoLinea {
  fecha: string; // "YYYY-MM-DD"
  valor: number;
}

function fechaCorta(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

export function GraficoLinea({
  datos,
  color = "#00a880",
  unidad = "",
}: {
  datos: PuntoLinea[];
  color?: string;
  unidad?: string;
}) {
  const W = 640;
  const H = 240;
  const PAD_X = 44;
  const PAD_Y = 26;

  const calc = useMemo(() => {
    if (datos.length < 2) return null;
    const valores = datos.map((d) => d.valor);
    let min = Math.min(...valores);
    let max = Math.max(...valores);
    if (min === max) {
      // Serie plana: abrimos un rango artificial para que se vea la línea.
      min -= 1;
      max += 1;
    }
    const rango = max - min;
    // 8% de aire arriba y abajo
    const yMin = min - rango * 0.08;
    const yMax = max + rango * 0.08;

    const x = (i: number) =>
      PAD_X + (i / (datos.length - 1)) * (W - PAD_X * 2);
    const y = (v: number) =>
      H - PAD_Y - ((v - yMin) / (yMax - yMin)) * (H - PAD_Y * 2);

    const puntos = datos.map((d, i) => ({ ...d, cx: x(i), cy: y(d.valor) }));
    const path = puntos
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.cx.toFixed(1)} ${p.cy.toFixed(1)}`)
      .join(" ");
    const area = `${path} L ${puntos[puntos.length - 1].cx.toFixed(1)} ${H - PAD_Y} L ${puntos[0].cx.toFixed(1)} ${H - PAD_Y} Z`;

    // 3 guías horizontales con su valor
    const guias = [0.25, 0.5, 0.75].map((f) => {
      const v = yMin + (yMax - yMin) * f;
      return { v, gy: y(v) };
    });

    return { puntos, path, area, guias, min, max };
  }, [datos]);

  if (!calc) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Se necesitan al menos 2 mediciones para graficar la evolución.
      </p>
    );
  }

  const primero = datos[0];
  const ultimo = datos[datos.length - 1];
  const delta = ultimo.valor - primero.valor;
  const deltaTxt = `${delta > 0 ? "+" : ""}${delta.toFixed(1)}${unidad}`;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Evolución">
        {/* Guías */}
        {calc.guias.map((g) => (
          <g key={g.gy}>
            <line
              x1={PAD_X} x2={W - PAD_X} y1={g.gy} y2={g.gy}
              stroke="currentColor" strokeOpacity="0.1" strokeDasharray="4 4"
            />
            <text
              x={PAD_X - 6} y={g.gy + 3.5} textAnchor="end"
              fontSize="10" fill="currentColor" fillOpacity="0.5"
            >
              {g.v.toFixed(1)}
            </text>
          </g>
        ))}

        {/* Área + línea */}
        <path d={calc.area} fill={color} fillOpacity="0.08" />
        <path d={calc.path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

        {/* Puntos con tooltip nativo */}
        {calc.puntos.map((p) => (
          <circle key={p.fecha + p.cx} cx={p.cx} cy={p.cy} r="4" fill={color} stroke="white" strokeWidth="1.5">
            <title>{`${fechaCorta(p.fecha)} · ${p.valor}${unidad}`}</title>
          </circle>
        ))}

        {/* Fechas extremas */}
        <text x={PAD_X} y={H - 6} fontSize="10" fill="currentColor" fillOpacity="0.55">
          {fechaCorta(primero.fecha)}
        </text>
        <text x={W - PAD_X} y={H - 6} textAnchor="end" fontSize="10" fill="currentColor" fillOpacity="0.55">
          {fechaCorta(ultimo.fecha)}
        </text>
      </svg>
      <p className="mt-1 text-center text-xs text-muted-foreground">
        {primero.valor}
        {unidad} → <span className="font-semibold text-foreground">{ultimo.valor}{unidad}</span>{" "}
        ({deltaTxt} en {datos.length} mediciones)
      </p>
    </div>
  );
}
