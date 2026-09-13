/**
 * Regenera las cuatro capturas del panel que muestra la landing.
 *
 * POR QUÉ EXISTE
 * ──────────────
 * `panel-inicio.webp`, `panel-estadisticas.webp`, `panel-campanas.webp` y
 * `panel-caja.webp` son fotos del producto. Cada vez que cambia el panel
 * quedan viejas, y sacarlas a mano significa acordarse de ocho cosas: el
 * tamaño exacto, apagar el cartel de "confirmá tu email", que la sidebar no
 * diga "Prueba", que Inicio esté en "Mes" y no en "Hoy"...
 *
 * Con esto es un comando.
 *
 * ANTES DE CORRER
 * ───────────────
 *   docker compose -f infra/docker-compose.yml up -d
 *   docker compose -f infra/docker-compose.yml exec backend python -m app.seeds
 *   docker compose -f infra/docker-compose.yml exec backend python -m app.seeds_demo --empresa 1
 *
 * `seeds_demo` es el que reparte las fechas hacia atrás: sin él "Mes pasado"
 * sale vacío y la curva de facturación es una línea recta.
 *
 * Después, con el front levantado:
 *   node scripts/capturas-landing.mjs
 *
 * OJO CON EL ORIGEN: se entra por `localhost` y no por `127.0.0.1`. El CORS
 * del backend permite `http://localhost:3000`, y desde 127.0.0.1 el navegador
 * manda otro Origin, la llamada a /auth/me falla y el panel rebota al login.
 * Cuesta media hora darse cuenta.
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..');
const API = process.env.API ?? 'http://127.0.0.1:8000';
const APP = process.env.APP ?? 'http://localhost:3000';
const EMAIL = process.env.EMAIL ?? 'dueno@lacueva.com';
const CLAVE = process.env.CLAVE ?? 'demo1234';

// El tamaño de las que ya están en la landing. No lo cambies sin cambiar
// también las cuatro: si una sola mide distinto, el visor de pestañas salta
// de alto al cruzar de una a otra.
const ANCHO = 1356;
const ALTO = 762;

// El período por vista. Estadísticas va en "Mes pasado" a propósito: el mes
// en curso está a mitad de camino y la comparación contra el anterior sale en
// rojo. Es cierto, pero compara once días contra treinta, y en la landing se
// lee como si al negocio le fuera mal.
const VISTAS = [
  { nombre: 'inicio', ruta: '/inicio', periodo: 'Mes' },
  { nombre: 'estadisticas', ruta: '/estadisticas', periodo: 'Mes pasado' },
  { nombre: 'campanas', ruta: '/campanas', periodo: null },
  { nombre: 'caja', ruta: '/caja', periodo: null },
];

const r = await fetch(`${API}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: EMAIL, clave: CLAVE }),
});
if (!r.ok) {
  console.error(`No pude entrar como ${EMAIL}. ¿Corriste los seeds?`);
  process.exit(1);
}
const t = await r.json();

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: ANCHO, height: ALTO },
  // El doble, para que la captura se vea nítida en pantallas retina. Se baja
  // a 1356x762 al convertir a webp.
  deviceScaleFactor: 2,
  locale: 'es-AR',
  timezoneId: 'America/Argentina/Buenos_Aires',
});

// addInitScript y no evaluate(): el token queda puesto ANTES de que corra
// cualquier script de la página y en TODAS las navegaciones. Con evaluate
// sobre /login no alcanza — esa pantalla limpia la sesión al montarse.
await ctx.addInitScript(([a, rt]) => {
  localStorage.setItem('turnos360_token', a);
  localStorage.setItem('turnos360_refresh', rt);
}, [t.access_token, t.refresh_token]);

const page = await ctx.newPage();
const salida = join(RAIZ, 'scripts', '.capturas');
mkdirSync(salida, { recursive: true });

for (const { nombre, ruta, periodo } of VISTAS) {
  await page.goto(`${APP}${ruta}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);

  if (periodo) {
    const b = page.getByRole('button', { name: periodo, exact: true });
    if (await b.count()) {
      await b.first().click();
      await page.waitForTimeout(2500);
    }
  }
  // Las donas y la curva entran con animación: sin esta espera se fotografían
  // a medio dibujar.
  await page.waitForTimeout(1500);

  if (page.url().includes('/login')) {
    console.error(`  ${nombre}: rebotó al login. Mirá la nota del CORS arriba.`);
    continue;
  }
  await page.screenshot({ path: join(salida, `panel-${nombre}.png`) });
  console.log(`  panel-${nombre}.png`);
}

await browser.close();

console.log(`
Listas en scripts/.capturas/ (a ${ANCHO * 2}x${ALTO * 2}).

Antes de convertirlas, mirá que no se haya colado:
  · el cartel amarillo de "Confirmá tu email"  -> verificá el mail del usuario
  · "Prueba" debajo del nombre en la sidebar   -> poné un plan pago a la empresa
  · "Gastos $0" en Caja                        -> cargá algún gasto
  · "1 de 5 prendidas" en Campañas             -> prendé más campañas

Después, a webp del tamaño final:
  python3 -c "
from PIL import Image
for n in ('inicio','estadisticas','campanas','caja'):
    im = Image.open(f'scripts/.capturas/panel-{n}.png').convert('RGB')
    im.resize((${ANCHO}, ${ALTO}), Image.LANCZOS).save(
        f'public/img/panel-{n}.webp', 'WEBP', quality=82, method=6)
"`);
