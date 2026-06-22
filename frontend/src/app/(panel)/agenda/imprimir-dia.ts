/**
 * Imprime el listado de turnos del día en una ventana nueva y limpia.
 *
 * No depende del layout de la app: arma un HTML mínimo y dispara el diálogo de
 * impresión del navegador (que también permite "Guardar como PDF").
 */
 
export interface FilaImprimible {
  hora: string;
  cliente: string;
  servicio: string;
  estado: string;
}
 
interface ImprimirDiaOpts {
  /** Título principal (ej. nombre del negocio). */
  titulo: string;
  /** Subtítulo (ej. "Juan · lunes 22 de junio"). */
  subtitulo: string;
  filas: FilaImprimible[];
}
 
/** Escapa caracteres especiales para no romper el HTML. */
function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
 
export function imprimirDia({ titulo, subtitulo, filas }: ImprimirDiaOpts) {
  const cuerpo =
    filas.length === 0
      ? `<tr><td colspan="5" class="vacio">Sin turnos para este día.</td></tr>`
      : filas
          .map(
            (f) => `
            <tr>
              <td class="hora">${esc(f.hora)}</td>
              <td>${esc(f.cliente)}</td>
              <td>${esc(f.servicio)}</td>
              <td>${esc(f.estado)}</td>
              <td class="check"></td>
            </tr>`,
          )
          .join("");
 
  const generado = new Date().toLocaleString("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  });
 
  const html = `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>${esc(titulo)} — ${esc(subtitulo)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      color: #111;
      margin: 32px;
    }
    h1 { font-size: 20px; margin: 0 0 2px; }
    .sub { color: #555; font-size: 13px; margin: 0 0 20px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #ddd; }
    th { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #666; border-bottom: 2px solid #333; }
    td.hora { font-weight: 700; white-space: nowrap; }
    td.check { width: 28px; }
    td.check::after { content: ""; display: inline-block; width: 15px; height: 15px; border: 1.5px solid #999; border-radius: 3px; }
    td.vacio { text-align: center; color: #888; padding: 24px; }
    .pie { margin-top: 24px; font-size: 11px; color: #999; }
    @media print { body { margin: 0; } .noprint { display: none; } }
    .btn {
      display: inline-block; margin-bottom: 16px; padding: 8px 16px;
      background: #111; color: #fff; border: 0; border-radius: 8px;
      font-size: 13px; cursor: pointer;
    }
  </style>
</head>
<body>
  <button class="btn noprint" onclick="window.print()">Imprimir</button>
  <h1>${esc(titulo)}</h1>
  <p class="sub">${esc(subtitulo)}</p>
  <table>
    <thead>
      <tr><th>Hora</th><th>Cliente</th><th>Servicio</th><th>Estado</th><th></th></tr>
    </thead>
    <tbody>${cuerpo}</tbody>
  </table>
  <p class="pie">Generado el ${esc(generado)} · Turnos360</p>
</body>
</html>`;
 
  const win = window.open("", "_blank", "width=860,height=700");
  if (!win) {
    alert("El navegador bloqueó la ventana. Permití las ventanas emergentes para imprimir.");
    return;
  }
  win.document.write(html);
  win.document.close();
  win.focus();
}