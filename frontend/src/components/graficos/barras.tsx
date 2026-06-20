/**
 * Gráfico de barras horizontales reutilizable. Sin dependencias (puro CSS).
 *
 * Genérico: recibe { label, valor, color? } y dibuja una barra por fila,
 * proporcional al valor máximo. Ideal para rankings (servicios, profesionales…).
 *
 * Uso:
 *   <Barras datos={[{ label: "Corte", valor: 18 }, ...]} color="#00d4aa" />
 */

export interface BarraDato {
  label: string;
  valor: number;
  /** Color propio de la barra; si no, usa el color general. */
  color?: string;
}

interface BarrasProps {
  datos: BarraDato[];
  /** Color por defecto de las barras. */
  color?: string;
  /** Formato del número mostrado a la derecha (ej. money). */
  formato?: (v: number) => string;
}

export function Barras({ datos, color = "#00d4aa", formato }: BarrasProps) {
  const max = Math.max(...datos.map((d) => d.valor), 1);

  return (
    <ul className="flex flex-col gap-3">
      {datos.map((d) => (
        <li key={d.label} className="flex items-center gap-3">
          <span className="w-28 shrink-0 truncate text-sm" title={d.label}>
            {d.label}
          </span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted/40">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(d.valor / max) * 100}%`,
                backgroundColor: d.color ?? color,
              }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-sm font-medium tabular-nums">
            {formato ? formato(d.valor) : d.valor}
          </span>
        </li>
      ))}
    </ul>
  );
}