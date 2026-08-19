#!/usr/bin/env node
/**
 * Guardián de tipos con línea de base.
 *
 * El problema que resuelve: el panel arrastra ~27 errores de tipos
 * preexistentes (cambio de firma de @base-ui). Por eso next.config.mjs tiene
 * `ignoreBuildErrors: true` y nadie corre `tsc`. Resultado: TypeScript quedó
 * apagado como red de seguridad, y un error NUEVO de verdad —como el de
 * /cuenta con el estado "prueba"— llega hasta el navegador sin que nada avise.
 *
 * La solución no es arreglar los 27 de golpe: es congelarlos y no dejar entrar
 * uno más. Este script compara la salida de `tsc` contra typecheck-baseline.txt
 * y falla SOLO si aparece un error que no estaba.
 *
 *   npm run typecheck              -> verifica contra la línea de base
 *   npm run typecheck:actualizar   -> regenera la línea de base
 *
 * Las firmas se guardan SIN número de línea a propósito: agregar un comentario
 * corre todas las líneas de un archivo y no debería romper la verificación.
 */

import { execSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");
const BASELINE = join(RAIZ, "typecheck-baseline.txt");
const ACTUALIZAR = process.argv.includes("--actualizar");

const V = "\x1b[0;32m", R = "\x1b[0;31m", A = "\x1b[0;33m", C = "\x1b[0;36m", N = "\x1b[0m";

/**
 * Comprueba que tsc se pueda ejecutar de verdad.
 *
 * Sin esto, si `npx` o `typescript` no están, execSync tira una excepción sin
 * salida parseable y el script concluye "0 errores": una línea de base vacía
 * y un guardián que no guarda nada. Un falso verde es peor que un rojo.
 */
/**
 * Preferimos el binario local a `npx`: npx puede no estar en el PATH (nvm a
 * medio cargar, cron, un script no interactivo) y además, si no encuentra el
 * paquete, se lo baja de internet, que no es lo que queremos acá.
 */
const TSC_LOCAL = join(RAIZ, "node_modules", ".bin", "tsc");
const TSC = existsSync(TSC_LOCAL) ? JSON.stringify(TSC_LOCAL) : "npx tsc";

function exigirTsc() {
  try {
    const v = execSync(`${TSC} --version`, { cwd: RAIZ, encoding: "utf8", stdio: "pipe" });
    if (!/Version\s+\d/.test(v)) throw new Error(`respuesta rara: ${v.trim()}`);
  } catch (e) {
    console.error(`${R}✘${N} No puedo ejecutar TypeScript.`);
    console.error();
    if (!existsSync(TSC_LOCAL)) {
      console.error("  No existe node_modules/.bin/tsc. Faltan las dependencias:");
      console.error("      cd frontend && npm ci");
    } else {
      console.error("  El binario existe pero no corre. ¿Node muy viejo, o permisos?");
      console.error(`      ${TSC_LOCAL}`);
    }
    console.error();
    console.error(`  Detalle: ${(e.message ?? e).toString().split("\n")[0]}`);
    process.exit(1);
  }
}

/** Corre tsc y devuelve las líneas de error crudas. */
function correrTsc() {
  try {
    execSync(`${TSC} --noEmit`, { cwd: RAIZ, encoding: "utf8", stdio: "pipe" });
    return [];
  } catch (e) {
    const salida = `${e.stdout ?? ""}${e.stderr ?? ""}`;
    const errores = salida.split("\n").filter((l) => /^\S.*\(\d+,\d+\): error TS\d+:/.test(l));
    // tsc falló pero no escupió ni un error con formato: no fue un problema de
    // tipos sino de ejecución (falta un módulo, tsconfig roto, se quedó sin
    // memoria). Tratarlo como "cero errores" sería mentirle al usuario.
    if (errores.length === 0) {
      console.error(`${R}✘${N} tsc terminó con error pero no devolvió errores de tipos.`);
      console.error("  No es un problema de tipos: algo impide compilar.");
      console.error();
      console.error(salida.trim().split("\n").slice(0, 15).join("\n"));
      process.exit(1);
    }
    return errores;
  }
}

/**
 * archivo(12,34): error TS2322: Blah  ->  archivo :: TS2322 :: Blah
 * Sin línea ni columna: mover código no invalida la línea de base.
 */
function firma(linea) {
  const m = /^(.*?)\(\d+,\d+\): error (TS\d+): (.*)$/.exec(linea);
  if (!m) return linea.trim();
  return `${m[1]} :: ${m[2]} :: ${m[3].trim()}`;
}

exigirTsc();
const actuales = correrTsc().map(firma).sort();

// ── Modo actualizar ─────────────────────────────────────────────────────────
if (ACTUALIZAR) {
  const cabecera = [
    "# Línea de base de errores de tipos del panel de Turnos360.",
    "#",
    "# Estos errores YA EXISTÍAN cuando se puso el guardián. Son deuda técnica",
    "# conocida (cambio de firma de @base-ui: asChild en Button, onValueChange",
    "# en Select) y no afectan el runtime.",
    "#",
    "# `npm run typecheck` falla si aparece un error que NO esté en esta lista.",
    "# El objetivo es que este archivo solo se achique con el tiempo.",
    "#",
    "# Para regenerarlo (solo después de arreglar errores de verdad):",
    "#     npm run typecheck:actualizar",
    "#",
    `# Errores congelados: ${actuales.length}`,
    "",
  ].join("\n");
  writeFileSync(BASELINE, cabecera + actuales.join("\n") + "\n", "utf8");
  console.log(`${V}✔${N} Línea de base regenerada: ${actuales.length} errores congelados`);
  console.log(`  ${BASELINE}`);
  process.exit(0);
}

// ── Modo verificar ──────────────────────────────────────────────────────────
if (!existsSync(BASELINE)) {
  console.error(`${R}✘${N} No existe typecheck-baseline.txt`);
  console.error(`  Generalo con:  npm run typecheck:actualizar`);
  process.exit(1);
}

const base = readFileSync(BASELINE, "utf8")
  .split("\n")
  .map((l) => l.trim())
  .filter((l) => l && !l.startsWith("#"));

// Comparamos con multiconjuntos: si un archivo pasa de 1 a 3 errores iguales,
// eso también es una regresión.
function contar(lista) {
  const m = new Map();
  for (const x of lista) m.set(x, (m.get(x) ?? 0) + 1);
  return m;
}

const mapaBase = contar(base);
const mapaAct = contar(actuales);

const nuevos = [];
for (const [k, n] of mapaAct) {
  const extra = n - (mapaBase.get(k) ?? 0);
  for (let i = 0; i < extra; i++) nuevos.push(k);
}

const arreglados = [];
for (const [k, n] of mapaBase) {
  const menos = n - (mapaAct.get(k) ?? 0);
  for (let i = 0; i < menos; i++) arreglados.push(k);
}

console.log(`${C}Verificación de tipos${N}  ·  base: ${base.length}  ·  ahora: ${actuales.length}`);
console.log();

if (arreglados.length) {
  console.log(`${V}✔${N} Arreglaste ${arreglados.length} error(es) que estaban en la base:`);
  for (const e of arreglados.slice(0, 10)) console.log(`    ${e}`);
  if (arreglados.length > 10) console.log(`    … y ${arreglados.length - 10} más`);
  console.log(`${A}  !${N} Bajá la línea de base:  npm run typecheck:actualizar`);
  console.log();
}

if (nuevos.length) {
  console.log(`${R}✘ ${nuevos.length} ERROR(ES) DE TIPOS NUEVO(S)${N}`);
  console.log();
  for (const e of nuevos) console.log(`  ${R}•${N} ${e.replace(/ :: /g, "\n      ")}`);
  console.log();
  console.log("  Estos no estaban antes. Arreglalos.");
  console.log("  Si de verdad son inevitables y los aceptás a conciencia,");
  console.log("  congelalos con:  npm run typecheck:actualizar");
  process.exit(1);
}

console.log(`${V}✔${N} Sin errores de tipos nuevos.`);
process.exit(0);
