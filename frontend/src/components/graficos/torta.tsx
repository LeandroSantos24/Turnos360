/**
 * Gráfico de torta (estilo donut) reutilizable, en SVG puro. Sin dependencias.
 *
 * Genérico: recibe segmentos { label, valor, color } y dibuja el anillo + leyenda.
 * Pensado para reusarse en cualquier pantalla (dashboard, salud/mediciones, packs).
 *
 * Uso:
 *   <Torta datos={[{ label: "Instagram", valor: 12, color: "#e1306c" }, ...]} />
 */

export interface SegmentoTorta {
  label: string;
  valor: number;
  color: string;
}

interface TortaProps {
  datos: SegmentoTorta[];
  /** Diámetro del anillo en px. */
  size?: number;
  /** Texto del centro; por defecto, el total. */
  centro?: string;
}

/** Punto sobre el círculo para un ángulo dado (0° = arriba, sentido horario). */
function punto(
  cx: number,
  cy: number,
  r: number,
  anguloDeg: number,
): [number, number] {
  const rad = ((anguloDeg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

export function Torta({ datos, size = 160, centro }: TortaProps) {
  const total = datos.reduce((acc, d) => acc + d.valor, 0);
  const grosor = Math.round(size * 0.16);
  const radio = (size - grosor) / 2;
  const cx = size / 2;
  const cy = size / 2;

  // Construyo los arcos acumulando ángulos (solo segmentos con valor > 0)
  let anguloAcum = 0;
  const arcos = datos
    .filter((d) => d.valor > 0)
    .map((d) => {
      const barrido = (d.valor / total) * 360;
      const inicio = anguloAcum;
      const fin = anguloAcum + barrido;
      anguloAcum = fin;
      return { color: d.color, inicio, fin, barrido };
    });

  return (
    <div className="flex items-center gap-5">
      {/* Anillo */}
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {/* Aro de fondo (tenue, respeta el tema) */}
          <circle
            cx={cx}
            cy={cy}
            r={radio}
            fill="none"
            stroke="currentColor"
            strokeWidth={grosor}
            className="text-muted-foreground/15"
          />
          {/* Segmentos */}
          {total > 0 &&
            arcos.map((a, i) => {
              // Un único segmento del 100% → círculo completo
              if (a.barrido >= 359.999) {
                return (
                  <circle
                    key={i}
                    cx={cx}
                    cy={cy}
                    r={radio}
                    fill="none"
                    stroke={a.color}
                    strokeWidth={grosor}
                  />
                );
              }
              const [x1, y1] = punto(cx, cy, radio, a.inicio);
              const [x2, y2] = punto(cx, cy, radio, a.fin);
              const largeArc = a.barrido > 180 ? 1 : 0;
              const d = `M ${x1} ${y1} A ${radio} ${radio} 0 ${largeArc} 1 ${x2} ${y2}`;
              return (
                <path
                  key={i}
                  d={d}
                  fill="none"
                  stroke={a.color}
                  strokeWidth={grosor}
                />
              );
            })}
        </svg>
        {/* Total en el centro */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-xl font-bold tabular-nums"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            {centro ?? total}
          </span>
          <span className="text-[11px] text-muted-foreground">total</span>
        </div>
      </div>

      {/* Leyenda */}
      <ul className="flex min-w-0 flex-1 flex-col gap-1.5">
        {datos.map((d) => {
          const pct = total > 0 ? Math.round((d.valor / total) * 100) : 0;
          return (
            <li key={d.label} className="flex items-center gap-2 text-sm">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: d.color }}
              />
              <span className="min-w-0 flex-1 truncate text-muted-foreground">
                {d.label}
              </span>
              <span className="shrink-0 font-medium tabular-nums">{d.valor}</span>
              <span className="w-9 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}