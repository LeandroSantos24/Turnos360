/**
 * Verifica `src/lib/telefono.ts` con los MISMOS casos que el backend
 * (backend/tests/test_whatsapp_fix011.py). Las dos copias tienen que decir
 * lo mismo: el recordatorio por WhatsApp del panel arma el número acá, y un
 * número mal armado le manda el horario del cliente a un desconocido.
 *
 * Igual que check:seguimiento: transpila el .ts con el TypeScript del
 * proyecto y ejecuta el resultado. Sin dependencias nuevas.
 *
 *     npm run check:telefono
 */

import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import ts from "typescript";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const js = ts.transpileModule(
  readFileSync(join(raiz, "src", "lib", "telefono.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } },
).outputText;
const archivo = join(mkdtempSync(join(tmpdir(), "tel-")), "telefono.mjs");
writeFileSync(archivo, js);
const { telefonoWa, linkWaCliente } = await import(pathToFileURL(archivo).href);

const mismos = [
  "2614123456", "261 4123456", "261 412-3456", "0261 15 4123456",
  "(0261) 15-4123456", "+54 9 261 412-3456", "5492614123456",
  "54 261 4123456", "0054 9 261 4123456", "  2614123456  ",
];
const areas = [
  ["11 1234-5678", "5491112345678"],
  ["011 15 1234-5678", "5491112345678"],
  ["+5491112345678", "5491112345678"],
  ["3514123456", "5493514123456"],
  ["2966412345", "5492966412345"],
];
const invalidos = [null, undefined, "", "   ", "sin telefono", "123",
  "26141234567890", "0000000000", "1111111111", "261a3f2b1c", "123456"];

let fallas = 0;
const ok = (cond, msg) => { if (!cond) { fallas++; console.error("FALLA:", msg); } };

for (const e of mismos) ok(telefonoWa(e) === "5492614123456", `${JSON.stringify(e)} → ${telefonoWa(e)}`);
for (const [e, esp] of areas) ok(telefonoWa(e) === esp, `${e} → ${telefonoWa(e)} (esperaba ${esp})`);
for (const e of invalidos) ok(telefonoWa(e) === null, `${JSON.stringify(e)} debería ser inválido y dio ${telefonoWa(e)}`);

const link = linkWaCliente("0261 15 4123456", "Hola Ana! Tu turno es mañana a las 10:00 & te esperamos");
ok(link === "https://wa.me/5492614123456?text=Hola%20Ana!%20Tu%20turno%20es%20ma%C3%B1ana%20a%20las%2010%3A00%20%26%20te%20esperamos", `link: ${link}`);
ok(linkWaCliente("123", "x") === null, "sin número válido no hay link");

const total = mismos.length + areas.length + invalidos.length + 2;
if (fallas) {
  console.error(`\n${fallas} de ${total} casos fallaron.`);
  process.exit(1);
}
console.log(`telefono.ts: ${total} casos OK (los mismos que el backend).`);
