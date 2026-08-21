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
 *
 * QUÉ CUENTA COMO "EL MISMO ERROR"  (y por qué NO es el texto del mensaje)
 * ═══════════════════════════════════════════════════════════════════════
 * La primera versión comparaba `archivo :: TSxxxx :: mensaje completo`, y eso
 * daba FALSOS POSITIVOS: el texto que imprime tsc no es estable entre
 * corridas. TypeScript ordena los miembros de una unión según el orden en que
 * los fue resolviendo, y eso cambia cuando cambia el conjunto de archivos del
 * proyecto. El MISMO error se imprime distinto:
 *
 *   ... type '(value: "persona" | "box" | "equipo" | null, ...
 *   ... type '(value: "equipo" | "persona" | "box" | null, ...
 *
 * Peor todavía cuando la unión es larga y tsc la abrevia, porque también
 * cambia CUÁL miembro sobrevive al recorte:
 *
 *   ... Omit<..., "color"     | ... 3 more ... | "defaultValue"> ...
 *   ... Omit<..., "className" | ... 3 more ... | "defaultValue"> ...
 *
 * Agregar un archivo nuevo y sin errores alcanzaba para que 4 errores viejos
 * se vieran como nuevos. Un guardián que grita cuando no pasó nada se termina
 * ignorando, y ese día deja de servir para lo único que existe.
 *
 * Así que la identidad es `archivo :: código`, CONTADA:
 *
 *   · aparece un TS2322 en un archivo que no tenía  -> ROJO
 *   · un archivo pasa de 1 a 2 errores TS2322       -> ROJO
 *   · el mismo error con el texto reordenado        -> verde, como debe ser
 *
 * Lo que se resigna: cambiar un TS2322 por OTRO TS2322 distinto en el mismo
 * archivo, en la misma corrida, pasa desapercibido. Es un caso raro y de bajo
 * riesgo al lado de un guardián que da rojo porque sí.
 *
 * El mensaje se sigue guardando en typecheck-baseline.txt: sirve para leerlo y
 * saber qué deuda hay, no para comparar.
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
 * Preferimos el binario local a `npx`: npx puede no estar en el PATH (nvm a
 * medio cargar, cron, un script no interactivo) y además, si no encuentra el
 * paquete, se lo baja de internet, que no es lo que queremos acá.
 */
const TSC_LOCAL = join(RAIZ, "node_modules", ".bin", "tsc");
const TSC = existsSync(TSC_LOCAL) ? JSON.stringify(TSC_LOCAL) : "npx tsc";

/**
 * Comprueba que tsc se pueda ejecutar de verdad.
 *
 * Sin esto, si `npx` o `typescript` no están, execSync tira una excepción sin
 * salida parseable y el script concluye "0 errores": una línea de base vacía
 * y un guardián que no guarda nada. Un falso verde es peor que un rojo.
 */
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

/** `archivo(12,34): error TS2322: Blah` -> { archivo, codigo, mensaje } */
function partirError(linea) {
  const m = /^(.*?)\(\d+,\d+\): error (TS\d+): (.*)$/.exec(linea);
  if (!m) return { archivo: linea.trim(), codigo: "TS?", mensaje: "" };
  return { archivo: m[1], codigo: m[2], mensaje: m[3].trim() };
}

/** `archivo :: TS2322 :: Blah` (formato del baseline) -> lo mismo. */
function partirLineaBase(linea) {
  const p = linea.split(" :: ");
  if (p.length < 2) return { archivo: linea.trim(), codigo: "TS?", mensaje: "" };
  return { archivo: p[0].trim(), codigo: p[1].trim(), mensaje: p.slice(2).join(" :: ").trim() };
}

/** La identidad que se compara. El mensaje queda AFUERA a propósito (ver arriba). */
const clave = (e) => `${e.archivo} :: ${e.codigo}`;

/** Cuenta cuántas veces aparece cada clave. */
function contar(errores) {
  const m = new Map();
  for (const e of errores) m.set(clave(e), (m.get(clave(e)) ?? 0) + 1);
  return m;
}

exigirTsc();
const actuales = correrTsc()
  .map(partirError)
  .sort((a, b) => `${a.archivo}${a.codigo}${a.mensaje}`.localeCompare(`${b.archivo}${b.codigo}${b.mensaje}`));

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
    "# La comparación se hace por ARCHIVO + CÓDIGO, contando cuántos hay de cada",
    "# uno. El texto del mensaje se guarda para poder leerlo, pero NO se compara:",
    "# tsc reordena los miembros de las uniones entre corridas y el mismo error",
    "# se imprime distinto. Ver el comentario de scripts/typecheck-baseline.mjs.",
    "#",
    "# Para regenerarlo (solo después de arreglar errores de verdad):",
    "#     npm run typecheck:actualizar",
    "#",
    `# Errores congelados: ${actuales.length}`,
    "",
  ].join("\n");
  const cuerpo = actuales.map((e) => `${e.archivo} :: ${e.codigo} :: ${e.mensaje}`);
  writeFileSync(BASELINE, cabecera + cuerpo.join("\n") + "\n", "utf8");
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
  .filter((l) => l && !l.startsWith("#"))
  .map(partirLineaBase);

const mapaBase = contar(base);
const mapaAct = contar(actuales);

// Un error es NUEVO si su (archivo, código) aparece más veces que en la base.
// Mostramos los mensajes de verdad, que para leer sí sirven.
const porClave = new Map();
for (const e of actuales) {
  if (!porClave.has(clave(e))) porClave.set(clave(e), []);
  porClave.get(clave(e)).push(e);
}

const nuevos = [];
for (const [k, n] of mapaAct) {
  const extra = n - (mapaBase.get(k) ?? 0);
  if (extra > 0) nuevos.push(...porClave.get(k).slice(-extra));
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
  for (const e of nuevos) {
    console.log(`  ${R}•${N} ${e.archivo}`);
    console.log(`      ${e.codigo}`);
    console.log(`      ${e.mensaje}`);
  }
  console.log();
  console.log("  Estos no estaban antes. Arreglalos.");
  console.log("  Si de verdad son inevitables y los aceptás a conciencia,");
  console.log("  congelalos con:  npm run typecheck:actualizar");
  process.exit(1);
}

console.log(`${V}✔${N} Sin errores de tipos nuevos.`);
process.exit(0);
