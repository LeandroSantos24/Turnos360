# Turnos360 · Qué le falta a la landing frente a Ágora y Turnau

Fecha: 3 de septiembre de 2026
Referencias analizadas: [agora.red](https://agora.red) y [turnau.com.ar](https://www.turnau.com.ar)
Estado de la landing propia: `frontend/src/app/page.tsx`, 760 líneas, 11 secciones.

---

## 0. Lo primero: hay una contradicción viva en la página

Antes de agregar nada, hay que resolver esto, porque hoy la landing se
contradice a sí misma en tres lugares distintos:

| Dónde | Qué dice |
|---|---|
| Nav (arriba a la derecha) | **"Comenzar gratis"** → `/registro` |
| Hero (debajo del botón) | *"Sin autoservicio: te lo configuramos nosotros y te lo entregamos andando."* |
| CTA principal del hero | **"Hablemos por WhatsApp"** |
| Precios | **"Probalo gratis 14 días"** → WhatsApp |
| FAQ #6 | *"Arrancamos por WhatsApp: te damos de alta el negocio…"* |

El que llega de la publicidad ve un botón que dice "Comenzar gratis", y dos
centímetros más abajo lee que no hay autoservicio. Uno de los dos miente.

Ya está construido el registro self-service y lo vas a probar ahora. **La
decisión es tuya, pero hay que tomarla y que la página entera diga lo mismo.**
Las dos opciones son defendibles:

- **A · Autoservicio primero (lo que hacen Ágora y Turnau).** El CTA principal
  pasa a ser "Crear mi cuenta gratis", WhatsApp queda como CTA secundario
  ("¿Preferís que lo hagamos nosotros? Escribinos"). Escala sin tu tiempo.
- **B · Onboarding asistido como *diferenciador*.** WhatsApp sigue siendo el
  CTA, pero entonces el botón del nav no puede decir "Comenzar gratis": dice
  "Ingresar", y el argumento se convierte en un beneficio explícito —
  *"No te damos un software: te lo dejamos andando con tus servicios, tu
  equipo y tus precios cargados. Gratis."* Eso ni Ágora ni Turnau lo ofrecen.

Mi recomendación: **A con B de refuerzo**. El botón grande crea la cuenta, y
justo abajo, en chico: *"¿Preferís que te lo dejemos configurado? Te lo hacemos
gratis por WhatsApp."* Ganás el volumen del autoservicio y no perdés el
diferencial del alta asistida.

---

## 1. Lo que ellos tienen y vos no (ordenado por impacto)

### 1.1 Prueba social — no hay nada. Cero. `IMPACTO MUY ALTO`

Es la diferencia más grande y la más barata de cerrar.

- **Ágora:** *"Cientos de negocios ya eligen Ágora"* + 5 estudios con foto de
  avatar y rubro (Akira Studio, Nicole Leaniz, Marea, Pulgar Barbería, Browlash).
- **Turnau:** 6 testimonios con nombre, rubro, barrio **y una métrica dura**:
  *"Martín D., Barbería, Belgrano — empecé a cobrar la seña antes del turno y
  las ausencias bajaron casi a cero · −85% ausencias en 30 días."* Más
  *"+50.000 turnos gestionados"* y *"4.8 ★ en App Store y Google Play"*.
- **Turnos360:** nada. Ni un logo, ni un nombre, ni un número.

**Cómo cerrarla sin inventar nada** — y esto es en serio: no inventes
testimonios ni métricas. Es ilegal (Ley de Defensa del Consumidor 24.240,
publicidad engañosa), y en un rubro donde todos se conocen, una peluquera que
te googlea y no encuentra a "Camila R. de Palermo" ya no vuelve.

Lo que sí podés hacer hoy:

1. **Barbería El Faro.** Ya está en los mockups de la landing. Si es un cliente
   real, pedile tres renglones y una foto, y ponelo con nombre y apellido. Un
   testimonio verificable vale más que seis inventados.
2. **Contador vivo, no inventado.** El backend ya tiene los datos: turnos
   gestionados, negocios activos. Un endpoint público `/publico/metricas` que
   devuelva números reales y una franja que diga *"X turnos gestionados ·
   Y negocios en Argentina"*. Arranca chico y crece solo. Si el número todavía
   es chico para mostrarlo, esperá — pero dejá el endpoint hecho.
3. **Prueba social prestada.** Los logos de Mercado Pago, WhatsApp, Google
   Calendar y Maps ya están, pero enterrados en una franja gris de 44px.
   Ágora los usa como sección propia. Subilos de jerarquía.
4. **"Hecho en Mendoza".** Hoy está en letra chica en el footer. Turnau pone
   *"Hecho en Argentina"* con orgullo y Ágora vende el soporte por personas
   reales. Para un dueño de barbería mendocina, "el que lo hizo está acá y te
   atiende él" es un argumento fuerte contra un SaaS anónimo.

### 1.2 No hay CTA final antes del footer `IMPACTO ALTO · 30 MINUTOS`

Los dos competidores cierran con una sección a página completa:

- Ágora: *"¿Qué esperás para empezar a vivir de lo que amás?"* → Crear tienda
- Turnau: *"Tu próximo cliente ya está buscando un profesional. Asegurate de
  que te encuentre en Turnau"* → Empezar gratis

Tu página termina en el FAQ y cae directo al footer. El que leyó todo y se
convenció se queda sin dónde hacer clic, y tiene que scrollear para arriba.
Es lo más barato de arreglar de toda esta lista.

### 1.3 La galería de tres fotos no dice nada `IMPACTO MEDIO`

Entre Precios y FAQ hay tres fotos stock de 260px sin texto ni CTA. Ese es
exactamente el lugar donde Ágora pone los testimonios. Es espacio caro
gastado en decoración. Reemplazalo por prueba social o por el CTA final.

### 1.4 Falta el marketplace / directorio `IMPACTO ALTO · ESFUERZO ALTO`

Este es el argumento de venta **número dos** de Turnau, con sección propia de
cuatro pasos ("Te encuentran → Ven tu perfil → Eligen en tu agenda real →
Turno confirmado"), y es el que justifica sus planes caros: el Elite de
$69.990 vende *"boost de posicionamiento"* y *"máxima prioridad en el
Marketplace"*. Ágora también tiene directorio por rubro.

Vos ya tenés casi todas las piezas: vidrieras públicas por slug, rubros,
sitemap que las indexa y, desde esta semana, sucursales con dirección. Falta
la página que las junte: `/barberias/mendoza`, `/peluquerias/godoy-cruz`.

Vale la pena separar las dos cosas, porque son ventas distintas:

- **Para el dueño:** "no solo te ordeno la agenda, además te traigo clientes."
  Es lo que convierte $14.990/mes de gasto en inversión.
- **Para vos:** cada vidriera es una página indexable más. Es el único canal
  de adquisición que no cuesta plata por clic y que crece solo con cada
  cliente nuevo.

### 1.5 Escalera de planes vs. plan único `IMPACTO ALTO · DECISIÓN COMERCIAL`

| | Plan de entrada | Plan medio | Plan alto |
|---|---|---|---|
| **Ágora** | $11.900 único, todo incluido | — | — |
| **Turnau** | Basic $14.990 · **1 profesional** | Pro $24.990 · hasta 4 | Elite $69.990 · ilimitados + **multisucursal** |
| **Turnos360** | **$14.990 todo incluido, ilimitado** | — | — |

Mirá bien esa fila. **Por el mismo precio al que Turnau te da un solo
profesional, vos das profesionales ilimitados, caja, comisiones y ahora
multisucursal — que en Turnau es el plan de $69.990.**

Dos lecturas de eso, las dos ciertas:

- **Como argumento de venta es un misil, y no lo estás usando.** La landing
  dice *"Un solo plan, todo incluido. Sin niveles, sin funciones bloqueadas"*,
  que está bien escrito pero es abstracto. Comparado contra el precio real de
  la competencia se vuelve concreto. Una tabla honesta — sin nombrar al
  competidor si no querés — cierra ventas.
- **Como negocio, estás regalando margen.** El que tiene tres locales y
  veinte empleados te paga lo mismo que la manicura que trabaja sola. Turnau
  le cobra $69.990.

No hace falta romper el plan estrella. La forma de subir el techo sin tocarlo:

```
Individual   $9.990   1 profesional, 1 local        ← nuevo piso, gana a Ágora
Negocio     $14.990   ilimitados, 1 local           ← EL DE SIEMPRE, destacado
Multi       $29.990   varios locales + comparativas ← lo que acabás de construir
```

El de $14.990 queda intacto y encima gana: puesto en el medio de tres, con el
sello "el más elegido", se ve como la decisión sensata en vez de como el único
precio. Es el efecto que Turnau explota con su columna del medio.

> **Pero ojo, hay un bloqueante técnico:** hoy pagar solo promueve de
> `gratuito` a `BASICO` (`cobranza.py:324`), y Mercado Pago cobra un único
> `empresa.precio_mensual` (`mp_suscripcion.py::precio_de`). **Nadie puede
> contratar Pro ni Multi por sí mismo.** Poner tres planes en la landing sin
> resolver esto primero es prometer algo que el sistema no puede entregar.

### 1.6 Multisucursal no aparece en ninguna parte de la landing `IMPACTO ALTO`

Acabás de terminar ocho pasos de multisucursal — el trabajo más grande del
mes — y la página no lo menciona ni una vez. Turnau lo cobra $69.990. Ágora
directamente no lo tiene.

Merece sección propia, con lo que ya está hecho y se puede mostrar en pantalla:
caja por local, agenda por local, estadísticas comparadas entre locales,
profesionales asignados a su sucursal. Es, además, el gancho natural del
plan Multi.

### 1.7 Sin FAQ estructurado para Google `IMPACTO MEDIO · 1 HORA`

Tenés seis preguntas muy bien escritas, pero sin JSON-LD `FAQPage`. Con el
schema, Google las muestra desplegadas debajo del resultado y te comés el
doble de alto en la página de búsqueda. Lo mismo con `SoftwareApplication` +
`Offer` para que aparezca el precio.

Es agregar un `<script type="application/ld+json">` en `layout.tsx` leyendo
el mismo array `faqs` que ya existe. Una hora de trabajo, y es de las pocas
cosas de SEO que dan resultado visible rápido.

### 1.8 Cosas más chicas que los dos tienen y vos no

- **CTA fijo en el celular.** Una barra abajo con "Empezar gratis" que aparece
  después del hero. En móvil el botón del hero se pierde a los dos scrolls.
- **Teléfono y soporte en el footer.** Turnau pone mail *y* teléfono. Vos solo
  mail e Instagram. El WhatsApp que ya usás como CTA no está en el footer.
- **Contradicción de rubros.** El badge del hero dice *"Hecho para barberías,
  peluquerías y salones"*, pero la sección Rubros incluye nutrición y
  kinesiología. O el badge se amplía, o esos dos rubros salen.
- **Sección "para tus clientes".** Ágora dedica una sección a lo que gana el
  cliente final (reservar a cualquier hora, pagar online, recordatorios).
  Tu landing le habla solo al dueño. El dueño compra pensando en si a su
  clienta le va a resultar fácil.

---

## 2. Lo que vos tenés y ellos no — y no lo estás vendiendo

Esto es lo que más me llamó la atención leyendo las tres páginas: **tenés
mejor producto que el que muestra tu landing.**

| Tu funcionalidad | Ágora | Turnau | Cómo está contada hoy |
|---|---|---|---|
| **Caja real** (apertura, cierre, arqueo, pago dividido, comisión por método, gastos) | ✗ | parcial ("caja diaria") | Una viñeta de 3 renglones |
| **Comisiones por profesional** | ✗ | solo desde Pro $24.990 | Una viñeta |
| **Carriles paralelos** en la agenda | ✗ | ✗ | Una viñeta — *y vos mismo escribiste que "los competidores esto lo resuelven mal", pero la página no lo demuestra* |
| **Membresías, gift cards con QR y cupones** | packs/planes | ✗ | Una viñeta |
| **Multisucursal** | ✗ | Elite $69.990 | **No aparece** |
| **Alta asistida gratis** | ✗ | ✗ | Contradicho por el nav |

Seis viñetas de una grilla de "Funcionalidades" tienen el mismo peso visual
que cualquier otra cosa. Turnau agarra tres ideas y les da una sección entera
cada una, numerada 01 / 02 / 03, con su propio CTA. Ese formato es más
efectivo justamente porque obliga a elegir.

**Si tuviera que elegir tres para tratarlas así, serían: la caja (nadie más
la tiene de verdad), los carriles paralelos (es tu mejor detalle técnico y es
invisible) y multisucursal (es nuevo y es el plan caro).**

---

## 3. Plan sugerido, en tres olas

### Ola 1 — esta semana, todo en `page.tsx`

1. **Resolver la contradicción autoservicio/WhatsApp.** Es una decisión, no
   código: elegí A o B y que las cinco menciones digan lo mismo.
2. **CTA final antes del footer**, a página completa.
3. **Reemplazar la galería de 3 fotos** por prueba social (aunque arranque con
   un solo testimonio real) o por el CTA final.
4. **JSON-LD de FAQ y de producto** en `layout.tsx`.
5. **Arreglar la contradicción de rubros** del badge del hero.
6. **Sección de multisucursal**, aprovechando que las capturas del panel ya
   existen en `/public/img/`.
7. **Barra fija de CTA en el celular.**

### Ola 2 — el mes que viene

8. **Prueba social de verdad:** el endpoint `/publico/metricas` con números
   reales, y los primeros dos o tres testimonios con nombre y foto, pedidos
   a clientes reales.
9. **Desbloquear la venta de planes** (`cobranza.py` + `mp_suscripcion.py`)
   y recién entonces publicar la escalera de tres planes.
10. **Dar sección propia a la caja y a los carriles paralelos**, con captura
    y CTA, formato 01 / 02 / 03.

### Ola 3 — el diferencial de fondo

11. **Directorio público por rubro y ciudad** (`/barberias/mendoza`), armado
    sobre las vidrieras que ya existen y ya están en el sitemap. Es el
    argumento que convierte la cuota mensual en inversión, y el único canal
    de adquisición que crece solo.

---

## 4. Lo que yo NO tocaría

- **El hero.** *"Los que reservan y no vienen te están costando plata"* es
  mejor copy que *"Una solución integral para tu emprendimiento"* (Ágora) y
  que *"La agenda inteligente que impulsa tu negocio"* (Turnau). Los dos son
  genéricos; el tuyo nombra un dolor concreto y con plata. No lo suavices
  para parecerte a ellos.
- **La sección Problema** (los cuatro dolores 01–04). Ninguno de los dos
  tiene algo así y es lo mejor escrito de la página.
- **El tono.** Está en argentino real, sin corporativismo. Ágora escribe en
  neutro ("Diseña tu página", "Ofrece tus servicios"), lo que en Argentina
  suena a traducción. Es una ventaja tuya, chiquita pero real.
