"use client";
// Landing Turnos360 — reemplaza app/page.tsx
// Copiá las imágenes a /public/img/ con estos nombres (ver README-integracion.md)
import { useEffect, useState } from "react";
import Link from "next/link";

import { WA_LINK_DEMO as WA_LINK, INSTAGRAM, EMAIL_CONTACTO } from "@/lib/contacto";
import { useLogoMarca } from "@/lib/marca";
import {
  PRECIO_MENSUAL,
  PRECIO_MENSUAL_TEXTO,
  PRECIO_NORMAL_TEXTO,
  PROMO_ACTIVA,
  PROMO_ETIQUETA,
  DIAS_PRUEBA,
} from "@/lib/precios";

// Apuntan a las variables de globals.css. `marca` es la única que sigue
// siendo una fuente de display, y se usa solo en el logotipo.
const font = {
  titulo: "var(--fuente-titulos)",
  texto: "var(--fuente)",
  marca: "var(--fuente-marca)",
};

const pains = [
  { num: "01", title: "Los ausentes", body: "El que reserva y no viene te quema una hora que podías facturar. Es el dolor número uno del rubro." },
  { num: "02", title: "El WhatsApp desbordado", body: "Contestás mensajes todo el día para agendar turnos, incluso fuera de horario y los domingos." },
  { num: "03", title: "No sabés tus números", body: "Cuánto facturaste el mes, cuánto le toca a cada barbero, qué servicio deja más plata: ni idea real." },
  { num: "04", title: "Clientes que se van", body: "No sabés quién hace tres meses que no viene. Y recuperarlo cuesta menos que conseguir uno nuevo." },
];

const features = [
  { glyph: "$", title: "Seña online con Mercado Pago", body: "El cliente paga la seña al reservar. El que puso plata, viene. Tu arma directa contra los ausentes." },
  { glyph: "≡", title: "Agenda con carriles paralelos", body: "Un corte, una tintura y una barba conviven en el mismo horario sin pisarse. Los competidores esto lo resuelven mal." },
  { glyph: "◉", title: "Caja de verdad", body: "Apertura, cierre y arqueo. Pago dividido entre métodos, comisión por método y gastos del día." },
  { glyph: "%", title: "Comisiones por profesional", body: "Cada barbero con su porcentaje. La liquidación sale sola, sin cuentas en papelitos." },
  { glyph: "∞", title: "Membresías y gift cards", body: "\u201CPagás $50.000 y tenés los cortes del mes.\u201D Abonos, gift cards con QR y cupones para llenar horas flojas." },
  { glyph: "✓", title: "Ficha de cada cliente", body: "Historial, gasto total, servicio favorito y etiquetas: VIP, frecuente o en riesgo de no volver." },
  { glyph: "+", title: "Historia clínica, si tu rubro la necesita", body: "Nutrición, kinesiología, psicología y consultorios: antecedentes, evolución de cada sesión, mediciones y adjuntos. Se registra quién la abrió y cuándo." },
  { glyph: "▤", title: "Productos en el mismo ticket", body: "La bebida, la cera, el shampoo que se lleva. Se suman al turno y entran a la caja del día como cualquier otro cobro." },
];

const shots = [
  { label: "Inicio", src: "/img/panel-inicio.webp", caption: "Resumen del mes: turnos, ingresos previstos y tasa de ausencias de un vistazo." },
  { label: "Estadísticas", src: "/img/panel-estadisticas.webp", caption: "Facturación real, comisiones y ticket promedio, filtrado por profesional." },
  { label: "Campañas", src: "/img/panel-campanas.webp", caption: "Recordatorios y campañas automáticas: se prenden una vez y andan solas." },
  { label: "Caja", src: "/img/panel-caja.webp", caption: "Apertura, cobros por método con su comisión, gastos y cierre con arqueo." },
];

const steps = [
  { num: "01", title: "Creás tu cuenta", body: "Elegís tu rubro, el nombre del negocio y la dirección de tu página. Dos minutos y ya estás adentro, con 14 días gratis." },
  { num: "02", title: "Corregís precios y sumás a tu equipo", body: "Los servicios típicos de tu rubro ya vienen cargados con su duración y su carril de agenda: solo ponés tus precios y tus horarios." },
  { num: "03", title: "Tus clientes reservan solos", body: "Compartís tu link, el sistema cobra la seña, manda recordatorios y vos ves los números cada noche." },
];

/**
 * Rubros de la sección "Hecho para tu rubro".
 *
 * `img` es OPCIONAL a propósito: mientras no exista el archivo, la tarjeta
 * cae al emoji sobre un fondo suave y la sección se ve completa igual. Así se
 * pueden ir subiendo las fotos de a una sin que la landing quede rota en el
 * medio.
 *
 * Formato de las fotos: 800 × 1000 px (4:5 vertical), JPG, bajo 150 KB.
 * Van en /public/img/ con exactamente estos nombres.
 */
const rubros: { emoji: string; label: string; img?: string }[] = [
  { emoji: "💈", label: "Barberías", img: "/img/rubro-barberia.jpg" },
  { emoji: "✂️", label: "Peluquerías", img: "/img/rubro-peluqueria.jpg" },
  { emoji: "💅", label: "Salones de uñas", img: "/img/rubro-unas.jpg" },
  { emoji: "✨", label: "Centros de estética", img: "/img/rubro-estetica.jpg" },
  { emoji: "🧖", label: "Spa y masajes", img: "/img/rubro-spa.jpg" },
  { emoji: "🎨", label: "Tatuajes", img: "/img/rubro-tatuajes.jpg" },
  { emoji: "🥗", label: "Nutrición", img: "/img/rubro-nutricion.jpg" },
  { emoji: "🤸", label: "Kinesiología", img: "/img/rubro-kinesiologia.jpg" },
  { emoji: "🧠", label: "Psicología", img: "/img/rubro-psicologia.jpg" },
  { emoji: "🩺", label: "Consultorios", img: "/img/rubro-consultorios.jpg" },
];

/**
 * Multisucursal, lo que se terminó de construir en la fase 3.
 *
 * Va en la landing porque es el diferencial más caro del rubro: el
 * competidor que lo tiene lo cobra en su plan más alto, y el otro
 * directamente no lo tiene. Cada punto es algo que YA anda, no una promesa.
 */
const locales = [
  { title: "Una caja por local", body: "Cada sucursal abre y cierra la suya. Los turnos, las gift cards, los abonos y los gastos caen en la caja del local donde pasaron." },
  { title: "Cada uno con su equipo", body: "El profesional queda atado a su sucursal y solo ve su agenda. El dueño ve todas, y puede filtrar por local cuando quiere." },
  { title: "Comparás locales de verdad", body: "Facturación, turnos y ausencias de un local contra el otro, en el mismo gráfico. Ahí se ve cuál rinde y cuál no." },
  { title: "Tu cliente elige dónde", body: "La página de reservas muestra los locales abiertos con su dirección, y cada uno puede tener su propio precio." },
];

/**
 * Los cuatro planes, espejo de backend/app/core/planes.py.
 *
 * `incluye` es lo que ESE plan suma sobre el anterior, no la lista completa:
 * repetir las nueve líneas en las tres columnas hace que las tres se lean
 * iguales y el que compara no encuentra la diferencia, que es lo único que
 * está buscando. Arriba de cada lista se dice "todo lo de X, más:".
 */
const BASE_INCLUIDA = [
  "Agenda con carriles paralelos",
  "Página de reservas propia (tu link y tu QR)",
  "Seña online con Mercado Pago",
  "Recordatorios automáticos anti-ausencias",
  "Caja con apertura, cierre y arqueo",
  "Ficha y historial de cada cliente",
  "Soporte por WhatsApp",
];

const planes = [
  {
    codigo: "inicial",
    nombre: "Inicial",
    precio: 13900,
    paraQuien: "El que atiende solo o con un equipo chico.",
    // Los cupos, dichos como los cuenta el dueño. «3 cuentas con clave» era
    // el mismo equipo contado por segunda vez y obligaba a cruzar dos
    // números para entender un solo límite: quien mira la grilla quiere
    // saber cuánta gente entra, no cuántos asientos de software compra.
    cupos: ["1 dueño + 3 que atienden", "1 local"],
    tituloLista: "Todo lo que hace falta para atender:",
    incluye: BASE_INCLUIDA,
    destacado: false,
  },
  {
    codigo: "pro",
    nombre: "Pro",
    precio: 19990,
    paraQuien: "El local con equipo, que ya quiere vender más a los que tiene.",
    cupos: ["1 dueño + 10 que atienden", "1 local"],
    tituloLista: "Todo lo de Inicial, más:",
    incluye: [
      "Membresías y abonos mensuales",
      "Gift cards con QR",
      "Cupones de descuento",
      "Comisiones por profesional",
      "WhatsApp con recordatorios",
    ],
    destacado: true,
  },
  {
    codigo: "multi",
    nombre: "Multi",
    precio: 34990,
    paraQuien: "El que abrió el segundo local y necesita compararlos.",
    cupos: ["Equipo ilimitado", "Hasta 3 locales"],
    tituloLista: "Todo lo de Pro, más:",
    incluye: [
      "Una caja por local, con su arqueo",
      "Cada local con su equipo y su agenda",
      "Precio propio por local",
      "Comparación de locales en un mismo gráfico",
      "Tu cliente elige a qué local va",
    ],
    destacado: false,
  },
];

/**
 * Enterprise, aparte de los tres.
 *
 * NO es un cuarto escalón: no tiene precio de lista, no se contrata online y
 * su botón lleva a WhatsApp. Puesto en la fila obligaba a comparar lo que no
 * se compara, y la columna sin número rompía la lectura justo donde el ojo
 * busca el precio.
 *
 * De paso se le sacó «Los locales que necesites», que estaba DOS veces: como
 * cupo arriba y como beneficio en la lista. Repetir la misma frase en la
 * misma tarjeta hace que la segunda se lea como si dijera algo distinto, y
 * el que la lee vuelve a leerla para ver qué se le escapó.
 */
const ENTERPRISE = {
  nombre: "Enterprise",
  paraQuien: "Cadenas y franquicias. Lo armamos con vos.",
  cupos: ["Equipo ilimitado", "Los locales que necesites", "Precio pactado"],
  incluye: [
    "Acompañamiento en la puesta en marcha",
    "Migración de tus datos actuales",
    "Soporte prioritario",
  ],
};

const enPesos = (n: number) => `$${n.toLocaleString("es-AR")}`;

const fotos = [
  { src: "/img/foto-barberia.jpg", alt: "Barbería" },
  { src: "/img/foto-salon.jpg", alt: "Salón de uñas" },
  { src: "/img/foto-estetica.jpg", alt: "Spa / estética" },
];

const faqs = [
  { q: "¿Tengo que saber de computación?", a: "No. Te das de alta en dos minutos eligiendo tu rubro, y ya entrás con tus servicios típicos cargados, tus métodos de cobro y tu página lista: solo corregís los precios con los tuyos. Si preferís que lo dejemos configurado nosotros, escribinos por WhatsApp y lo hacemos con vos, sin cargo." },
  { q: "¿Mis clientes tienen que descargar una app?", a: "No. Reservan desde el link de tu página, en el navegador del celular. Compartís ese link en tu Instagram o tu estado de WhatsApp y listo." },
  { q: "¿Me cobran comisión por cada turno?", a: "Cero. Pagás la cuota mensual y nada más. Si cobrás la seña con Mercado Pago, la plata va directo a tu cuenta y la única comisión es la de Mercado Pago, que no tocamos." },
  { q: "¿Sirve si tengo varios barberos trabajando a la vez?", a: "Es para lo que está hecho. La agenda muestra carriles paralelos: mientras uno corta, otro puede estar haciendo color y otro barba, sin que los turnos se pisen. Y cada uno tiene su comisión calculada." },
  { q: "¿Qué pasa con los que reservan y no vienen?", a: "Dos frenos: el cobro anticipado con Mercado Pago —elegís si pedís una seña o el total— y los recordatorios automáticos por email 24 horas y 2 horas antes." },
  { q: "¿Qué pasa si me queda chico el plan?", a: "Cambiás de plan cuando quieras desde «Mi suscripción» y se aplica al toque: no hay que migrar nada ni volver a cargar tus datos. Y si un mes bajás de plan, no perdés nada de lo que ya tenías cargado — simplemente no podés sumar más hasta volver a subir." },
  { q: "¿Cuál plan me conviene?", a: "Contá cuántas personas atienden, vos incluido. Hasta tres, Inicial. Si son más, o querés vender membresías, gift cards y cupones, Pro. Si tenés más de un local, Multi. Durante la prueba tenés todas las funciones desbloqueadas, así que las probás todas y después elegís sabiendo." },
  { q: "¿Puedo probarlo antes de pagar?", a: `Sí, ${DIAS_PRUEBA} días gratis con todas las funciones desbloqueadas —membresías, gift cards, cupones y campañas incluidas— para que lo pruebes con clientes reales antes de elegir. Durante la prueba trabajás con los cupos de Inicial: hasta tres personas atendiendo y un local, así el día que elegís plan no perdés nada de lo que cargaste. No pedimos tarjeta: te das de alta solo y al día ${DIAS_PRUEBA} decidís si seguís.` },
];

/**
 * Datos estructurados para Google (schema.org).
 *
 * Se arman del mismo array `faqs` que se muestra en pantalla, a propósito: si
 * quedaran duplicados a mano, el día que cambie una respuesta uno de los dos
 * queda viejo — y a Google eso le importa, marca el schema como no coincidente.
 *
 * El FAQPage hace que las preguntas aparezcan desplegables debajo del
 * resultado de búsqueda; el SoftwareApplication con su Offer, que se vea el
 * precio. Es de lo poco de SEO que da resultado visible rápido.
 */
const SITIO = process.env.NEXT_PUBLIC_SITE_URL || "https://turnos360.com.ar";

function datosEstructurados(preguntas: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        name: "Turnos360",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        url: SITIO,
        description:
          "Agenda online, seña con Mercado Pago, recordatorios automáticos, caja y comisiones para barberías, peluquerías, salones y centros de estética de Argentina.",
        offers: {
          "@type": "Offer",
          price: String(PRECIO_MENSUAL),
          priceCurrency: "ARS",
          url: `${SITIO}/#precios`,
        },
      },
      {
        "@type": "FAQPage",
        mainEntity: preguntas.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
      },
    ],
  };
}

function FotoRubro({ src, emoji, label }: { src?: string; emoji: string; label: string }) {
  const [falló, setFalló] = useState(false);
  const mostrarFoto = Boolean(src) && !falló;
  return (
    <div style={{ position: "relative", aspectRatio: "4 / 5", background: "#f3f5f8", display: "flex", alignItems: "center", justifyContent: "center" }}>
      {mostrarFoto ? (
        <img
          src={src}
          alt={label}
          loading="lazy"
          onError={() => setFalló(true)}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <span style={{ fontSize: 44 }}>{emoji}</span>
      )}
    </div>
  );
}

/**
 * Avatar del negocio de ejemplo en los mockups.
 *
 * Antes eran las letras "EF" sobre un círculo. Con el logo real de la barbería
 * el mockup deja de parecer un placeholder: el que lo mira ve un negocio, no
 * una maqueta. `invert` ahora solo cambia el aro, no el contenido.
 */
function Monogram({ size = 30, invert = false }: { size?: number; invert?: boolean }) {
  return (
    <img
      src="/img/elfaro-logo.jpg"
      alt="Barbería El Faro"
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        objectFit: "cover",
        flexShrink: 0,
        background: "#fff",
        border: `1.5px solid ${invert ? "rgba(28,34,44,0.15)" : "rgba(255,255,255,0.5)"}`,
      }}
    />
  );
}

export default function Page() {
  // El logo de la marca. Sale del archivo del repo y se cambia solo si el
  // super-admin cargó una URL. Ver lib/marca.ts.
  const logo = useLogoMarca();
  const [tab, setTab] = useState(0);
  const [faq, setFaq] = useState(-1);

  /**
   * Enciende los bloques `.revela` cuando entran en pantalla.
   *
   * Con IntersectionObserver y no con un listener de scroll: el listener
   * corre en el hilo principal en cada píxel y en un celular de gama media
   * se nota en el scroll de una página tan larga como esta.
   *
   * `unobserve` después de encender: una vez que apareció, no hay nada más
   * que observar, y dejar 30 entradas vivas hasta que se cierre la pestaña es
   * trabajo que no sirve.
   *
   * rootMargin negativo abajo: el bloque se enciende cuando ya entró de
   * verdad (12 % adentro), no cuando asoma un píxel — así el movimiento se ve
   * y no pasa desapercibido arriba del pliegue.
   */
  useEffect(() => {
    const bloques = document.querySelectorAll<HTMLElement>(".revela");

    // Sin soporte (o con reduced-motion), se muestran y listo: la página
    // nunca puede quedar invisible por un efecto decorativo.
    if (typeof IntersectionObserver === "undefined") {
      bloques.forEach((b) => b.classList.add("visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entradas) => {
        for (const e of entradas) {
          if (!e.isIntersecting) continue;
          e.target.classList.add("visible");
          observer.unobserve(e.target);
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );

    bloques.forEach((b) => observer.observe(b));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(datosEstructurados(faqs)) }}
      />

      {/* Todo el movimiento de la landing en un solo lugar.

          Las rotaciones se repiten dentro de cada keyframe porque `transform`
          es una sola propiedad: si la animación solo declarara translateY,
          pisaría el rotate del estilo inline y las tarjetas se enderezarían al
          empezar a moverse.

          prefers-reduced-motion apaga todo. No es un detalle de accesibilidad
          de manual: hay gente a la que el movimiento continuo le da mareo, y
          esta es una página de venta que se abre desde el celular. */}
      {/* OJO CON LAS COMILLAS DOBLES ACÁ ADENTRO, incluso en un comentario.
          React las serializa como &quot; en el HTML del servidor y las deja
          como " al hidratar en el cliente: los dos strings dejan de ser
          idénticos y salta "Text content does not match server-rendered
          HTML". Eran cuatro comillas en dos comentarios de CSS —20 caracteres
          de diferencia sobre 16.537— y tiraban un error de hidratación en
          toda la landing. Si necesitás comillas en este bloque, usá « ». */}
      <style>{`
        /* ── Barra superior ──────────────────────────────────────────────
           Grilla de tres columnas (1fr · auto · 1fr) y no space-between: con
           space-between el grupo del medio se centra entre el logo y los
           botones, que miden distinto, así que los links quedaban corridos a
           la izquierda del centro real de la página. Con las dos columnas de
           los costados iguales, el menú cae exactamente en el eje. */
        .nav-barra {
          display: grid;
          grid-template-columns: 1fr auto 1fr;
          align-items: center;
        }
        .nav-links {
          display: flex; align-items: center; gap: 26px;
          justify-self: center;
        }
        .nav-accesos { justify-self: end; }

        /* Los dos accesos comparten alto, radio y tipografía: leen como un
           par, no como un texto suelto al lado de un botón. */
        .nav-boton {
          display: inline-flex; align-items: center; justify-content: center;
          gap: 8px;
          height: 42px; padding: 0 20px;
          border-radius: 999px;
          font-size: 15px; font-weight: 600;
          white-space: nowrap; text-decoration: none;
          transition: background-color .18s ease, border-color .18s ease,
                      box-shadow .18s ease, transform .18s ease, color .18s ease;
        }
        .nav-boton:focus-visible {
          outline: 2px solid #12b886;
          outline-offset: 3px;
        }

        /* Secundario: contorno en vez de texto pelado. Sin forma propia, al
           lado de una píldora sólida parecía un link olvidado. */
        .nav-boton-suave {
          color: #39414f;
          background: #fff;
          border: 1px solid #e4e8ee;
        }
        .nav-boton-suave:hover {
          background: #f7f9fb;
          border-color: #cfd6e0;
          color: #1c222c;
        }

        /* Principal: el peso visual va acá. La sombra es apenas un apoyo, no
           un resplandor — el brillo fuerte queda para el botón del hero. */
        .nav-boton-fuerte {
          color: #fff;
          background: #1c222c;
          border: 1px solid #1c222c;
          padding: 0 22px;
          box-shadow: 0 1px 2px rgba(28,34,44,.16);
        }
        .nav-boton-fuerte:hover {
          background: #0f141c;
          box-shadow: 0 6px 18px rgba(28,34,44,.22);
          transform: translateY(-1px);
        }
        .nav-boton-fuerte:active { transform: translateY(0); }
        .nav-flecha { transition: transform .18s ease; }
        .nav-corto { display: none; }
        .nav-boton-fuerte:hover .nav-flecha { transform: translateX(3px); }

        /* El menú cae en el eje mientras las dos columnas de los costados
           tengan lugar de sobra; la que manda es la derecha, porque los
           accesos con la etiqueta larga miden 320px. Por debajo de ~1240 ya
           no entran los dos lados iguales y el menú se empieza a correr a la
           izquierda, que es justo lo que queríamos arreglar. Así que a partir
           de ahí los accesos acortan la etiqueta: pasan a medir ~170 y el
           menú vuelve a quedar centrado hasta que lo escondemos. */
        @media (max-width: 1240px) {
          .nav-largo { display: none; }
          .nav-corto { display: inline; }
          .nav-flecha { display: none; }
        }

        /* Angosto: el menú del medio no entra y empujaría los accesos fuera
           de la pantalla. Las secciones siguen a un scroll de distancia.
           Ojo: el display del menú va acá y no en un style inline, porque un
           inline le gana a la media query y el menú no se escondía — el
           header terminaba en dos renglones en el celular. */
        @media (max-width: 900px) {
          .nav-barra { grid-template-columns: auto 1fr; }
          .nav-links { display: none; }
        }

        /* Celular: los dos accesos completos no entraban al lado de la marca
           (medían ~460px de los ~350px útiles). En vez de sacar uno —el que
           ya es cliente también tiene que poder entrar— achicamos la píldora. */
        @media (max-width: 560px) {
          .nav-boton { height: 40px; padding: 0 14px; font-size: 14px; }
          .nav-boton-fuerte { padding: 0 16px; gap: 6px; }
        }
        @media (max-width: 360px) {
          .nav-boton { padding: 0 12px; }
        }

        /* ── Llamados a la acción ────────────────────────────────────────
           Una sola forma para los botones grandes de toda la página: antes
           cada sección repetía su propio bloque de estilos inline y ninguno
           tenía hover ni foco visible. */
        .cta {
          display: inline-flex; align-items: center; justify-content: center;
          gap: 10px;
          padding: 15px 28px;
          border-radius: 999px;
          font-size: 17px; font-weight: 700;
          white-space: nowrap; text-decoration: none;
          transition: background-color .18s ease, border-color .18s ease,
                      box-shadow .18s ease, transform .18s ease, color .18s ease;
        }
        .cta:focus-visible { outline: 2px solid #12b886; outline-offset: 3px; }
        .cta-flecha { transition: transform .18s ease; }
        .cta:hover .cta-flecha { transform: translateX(3px); }

        .cta-fuerte {
          background: #12b886; color: #fff;
          border: 1px solid #12b886;
          box-shadow: 0 8px 24px rgba(18,184,134,0.28);
        }
        .cta-fuerte:hover {
          background: #0fa377; border-color: #0fa377;
          box-shadow: 0 12px 30px rgba(18,184,134,0.34);
          transform: translateY(-1px);
        }
        .cta-fuerte:active { transform: translateY(0); }

        .cta-suave {
          background: #fff; color: #1c222c;
          border: 1px solid #e4e8ee;
        }
        .cta-suave:hover { background: #f7f9fb; border-color: #cfd6e0; }

        /* Las tarjetas de funciones estaban absolutamente quietas: un borde
           de 1px y nada más. Un elemento que no reacciona al mouse se lee
           como una imagen, no como parte de una página. */
        .tarjeta-hover {
          transition: transform .26s cubic-bezier(.32,.72,0,1),
                      box-shadow .26s cubic-bezier(.32,.72,0,1),
                      border-color .26s cubic-bezier(.32,.72,0,1);
        }
        .tarjeta-hover:hover {
          transform: translateY(-3px);
          border-color: #bfe6d8 !important;
          box-shadow: 0 18px 40px -14px rgba(18,184,134,.24);
        }

        /* ── Grilla de planes ────────────────────────────────────────────
           TRES columnas, no cuatro. Enterprise sale de la fila y va debajo,
           en una tarjeta ancha (.plan-enterprise).

           Eran cuatro y se veía mal, y el motivo no es solo que apretaba: es
           que Enterprise no es un cuarto escalón, es OTRA cosa. No tiene
           precio, no se contrata online y su botón lleva a WhatsApp. Puesto
           al lado de los tres, obliga a comparar lo que no se compara —y la
           columna sin número rompe la lectura de izquierda a derecha justo
           donde el ojo busca el precio—.

           Los tres que SÍ se comparan quedan más anchos, que es lo que
           necesitan: son los que se venden solos.

           El destacado se levanta 12px sobre los otros dos: es la forma más
           barata de decir «este» sin escribirlo. */
        .grilla-planes {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 18px;
          align-items: stretch;
        }
        @media (max-width: 980px) {
          .grilla-planes { grid-template-columns: 1fr; max-width: 460px; margin: 0 auto; gap: 22px; }
          .plan-destacado { transform: none; }
          .plan-destacado:hover { transform: translateY(-4px); }
        }

        /* ── Enterprise, abajo y a lo ancho ──────────────────────────────
           Centrada y más angosta que la grilla: si ocupara los 1120px
           enteros competiría en peso visual con los tres de arriba, que es
           exactamente lo que se quiere evitar. */
        .plan-enterprise {
          max-width: 760px;
          margin: 22px auto 0;
          display: grid;
          grid-template-columns: 1.1fr 1fr;
          gap: 28px;
          align-items: center;
          background: #fff;
          border: 1px solid #e4e8ee;
          border-radius: 22px;
          padding: 26px 30px;
        }
        @media (max-width: 720px) {
          .plan-enterprise { grid-template-columns: 1fr; gap: 18px; padding: 24px; }
        }
        .plan {
          display: flex;
          flex-direction: column;
          background: #fff;
          border: 1px solid #e6eaf0;
          border-radius: 22px;
          padding: 28px 26px;
          position: relative;
          box-shadow: 0 1px 2px rgba(28,34,44,.05), 0 8px 24px -8px rgba(28,34,44,.08);
          transition: transform .28s cubic-bezier(.32,.72,0,1),
                      box-shadow .28s cubic-bezier(.32,.72,0,1),
                      border-color .28s cubic-bezier(.32,.72,0,1);
        }
        .plan:hover {
          transform: translateY(-4px);
          border-color: #bfe6d8;
          box-shadow: 0 2px 4px rgba(28,34,44,.06), 0 22px 48px -12px rgba(18,184,134,.20);
        }
        .plan-destacado {
          border: 2px solid #12b886;
          transform: translateY(-12px);
          box-shadow: 0 24px 60px -14px rgba(18,184,134,.28);
        }
        .plan-destacado:hover { transform: translateY(-16px); }
        .plan-cinta {
          position: absolute;
          top: -13px; left: 50%; transform: translateX(-50%);
          background: #12b886; color: #fff;
          font-size: 12.5px; font-weight: 700; letter-spacing: .01em;
          padding: 5px 16px; border-radius: 999px;
          white-space: nowrap;
          box-shadow: 0 6px 16px rgba(18,184,134,.34);
        }

        /* Los cupos: el dato por el que se elige un plan. Van arriba, con
           fondo propio, para que no se pierdan entre las funciones. */
        .plan-cupos {
          display: flex; flex-wrap: wrap; gap: 7px;
          margin: 20px 0 22px;
          padding: 14px 0;
          border-top: 1px solid #eef1f5;
          border-bottom: 1px solid #eef1f5;
        }
        .plan-cupo {
          font-size: 13px; font-weight: 600; color: #0e8371;
          background: #eef9f4; border: 1px solid #d3efe4;
          padding: 4px 11px; border-radius: 999px;
        }

        @media (max-width: 720px) {
          /* Apilados, levantar el del medio deja un hueco raro arriba y otro
             abajo. La cinta sola alcanza para distinguirlo. */
          .plan-destacado, .plan-destacado:hover { transform: none; }
          .plan:hover { transform: none; }
        }

        /* ── Revelado al hacer scroll ────────────────────────────────────
           La página entera aparecía de golpe, entera, quieta. Eso es lo que
           se lee como «plana»: no le falta color, le falta que las cosas
           lleguen. Cada bloque sube 18px y se enciende cuando entra en
           pantalla, escalonado con --demora.

           Se hace con IntersectionObserver y no con scroll listeners: el
           observer no corre en el hilo principal en cada píxel de scroll. */
        .revela {
          opacity: 0;
          transform: translateY(18px);
          transition: opacity .6s cubic-bezier(.32,.72,0,1),
                      transform .6s cubic-bezier(.32,.72,0,1);
          transition-delay: var(--demora, 0ms);
        }
        .revela.visible {
          opacity: 1;
          transform: none;
        }

        /* ── Barra fija del celular ──────────────────────────────────────── */
        .barra-movil { display: none; }
        @media (max-width: 720px) {
          .barra-movil {
            position: fixed; left: 0; right: 0; bottom: 0; z-index: 60;
            display: flex; align-items: center; gap: 10px;
            padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
            background: rgba(255,255,255,0.94);
            backdrop-filter: blur(10px);
            border-top: 1px solid #eef1f5;
          }
          .barra-movil .cta { padding: 13px 20px; font-size: 16px; box-shadow: none; }
          .barra-movil-wa {
            display: flex; align-items: center; justify-content: center;
            width: 48px; height: 48px; flex-shrink: 0;
            border: 1px solid #e4e8ee; border-radius: 999px; background: #fff;
          }
          /* Para que la barra no tape la última línea del footer. */
          footer { padding-bottom: 88px; }
        }

        @keyframes correr-cinta {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .cinta-rubros { animation: correr-cinta 45s linear infinite; }
        .cinta-rubros:hover { animation-play-state: paused; }

        .flota { will-change: transform; }
        @keyframes flota-a {
          0%,100% { transform: rotate(3deg)  translateY(0); }
          50%     { transform: rotate(3deg)  translateY(-10px); }
        }
        @keyframes flota-b {
          0%,100% { transform: rotate(-2deg) translateY(0); }
          50%     { transform: rotate(-2deg) translateY(-13px); }
        }
        @keyframes flota-c {
          0%,100% { transform: rotate(2deg)  translateY(0); }
          50%     { transform: rotate(2deg)  translateY(-9px); }
        }
        @keyframes flota-d {
          0%,100% { transform: rotate(-3deg) translateY(0); }
          50%     { transform: rotate(-3deg) translateY(-14px); }
        }
        .flota-1 { animation: flota-a 5.5s ease-in-out infinite; }
        .flota-2 { animation: flota-b 6.4s ease-in-out infinite 0.4s; }
        .flota-3 { animation: flota-c 5.9s ease-in-out infinite 0.9s; }
        .flota-4 { animation: flota-d 6.8s ease-in-out infinite 0.2s; }

        /* Visor de capturas del panel */
        .visor-panel { transition: transform .35s ease, box-shadow .35s ease; }
        .visor-panel:hover {
          transform: scale(1.02);
          box-shadow: 0 32px 72px rgba(28,34,44,0.16);
        }
        /* .45s es el punto en que el cruce se percibe como intencional sin
           hacer esperar: por debajo de .3s parece un parpadeo, por encima de
           .6s el que va clickeando pestañas siente que el sitio va lento. */
        .visor-img { transition: opacity .45s ease; }

        /* Mitad izquierda / derecha clickeable. Sin fondo ni borde: lo único
           visible es la flecha, y recién al pasar el mouse. */
        .visor-lado {
          position: absolute; top: 0; bottom: 0; width: 26%;
          border: none; background: transparent; cursor: pointer;
          display: flex; align-items: center; padding: 0 14px;
          -webkit-tap-highlight-color: transparent;
        }
        .visor-lado-izq { left: 0; justify-content: flex-start; }
        .visor-lado-der { right: 0; justify-content: flex-end; }
        .visor-flecha {
          display: flex; align-items: center; justify-content: center;
          width: 38px; height: 38px; border-radius: 999px;
          background: rgba(255,255,255,0.92);
          box-shadow: 0 4px 16px rgba(28,34,44,0.18);
          color: #1c222c; font-size: 24px; line-height: 1; font-weight: 700;
          opacity: 0; transform: translateY(-1px);
          transition: opacity .25s ease;
        }
        .visor-panel:hover .visor-flecha { opacity: 1; }
        /* En pantallas táctiles no hay hover: si dependieran de él, en el
           celular no habría forma de saber que los costados se pueden tocar. */
        @media (hover: none) {
          .visor-flecha { opacity: .85; }
        }
        .visor-lado:focus-visible .visor-flecha { opacity: 1; outline: 2px solid #12b886; }

        @media (prefers-reduced-motion: reduce) {
          .cinta-rubros, .flota { animation: none !important; }
          /* Sin el reset, quien pidió menos movimiento se quedaría con la
             página INVISIBLE: .revela arranca en opacity 0 y lo que la
             enciende es justamente la transición. */
          .revela { opacity: 1 !important; transform: none !important; transition: none !important; }
          .plan, .plan:hover, .plan-destacado, .plan-destacado:hover { transform: none !important; transition: none !important; }
          .visor-panel, .visor-img { transition: none !important; }
          .visor-flecha { transition: none !important; }
          .visor-panel:hover { transform: none !important; }
        }
      `}</style>

    <div style={{ fontFamily: font.texto, color: "#1c222c", background: "#fff", minWidth: 320, overflowX: "hidden" }}>
      {/* NAV */}
      {/* La barra pinta el fondo a todo el ancho (si no, el blur cortaría en
          seco a los costados), pero su CONTENIDO va dentro del mismo
          contenedor de 1120 que el resto de la página.

          Antes la barra usaba solo el padding lateral y el contenido llevaba
          además `maxWidth: 1200; margin: 0 auto`. En una pantalla ancha eso
          dejaba el logo 112 px más a la izquierda que el título del hero: los
          dos elementos más grandes de la primera pantalla, sin alinear. Es
          exactamente lo que se ve como "descuadrado" aunque no se sepa
          nombrar. */}
      <header style={{ borderBottom: "1px solid #eef1f5", position: "sticky", top: 0, background: "rgba(255,255,255,0.94)", backdropFilter: "blur(8px)", zIndex: 50 }}>
      <nav className="nav-barra" style={{ gap: 16, padding: "12px clamp(16px,5vw,64px)", maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src={logo.src} onError={logo.alFallar} alt="Turnos360" style={{ width: 44, height: 44, objectFit: "contain" }} />
          <span style={{ fontFamily: font.marca, fontWeight: 700, fontSize: 20 }}>Turnos<span style={{ color: "#12b886" }}>360</span></span>
        </div>
        <div className="nav-links">
          <a href="#funciones" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Funciones</a>
          <a href="#como-funciona" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Cómo funciona</a>
          <a href="#rubros" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Rubros</a>
          <a href="#precios" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Precios</a>
          <a href="#faq" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Preguntas</a>
        </div>
        {/* Los dos accesos que espera cualquiera arriba a la derecha: el que
            YA es cliente entra, y el que recién llega se da de alta. Antes
            había uno solo ("Ingresar") y el alta era por WhatsApp. */}
        <div className="nav-accesos" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/login" className="nav-boton nav-boton-suave">
            <span className="nav-largo">Iniciar sesión</span>
            <span className="nav-corto">Entrar</span>
          </Link>
          <Link href="/registro" className="nav-boton nav-boton-fuerte">
            <span className="nav-largo">Comenzar gratis</span>
            <span className="nav-corto">Empezar</span>
            <span aria-hidden className="nav-flecha" style={{ fontSize: 17, lineHeight: 1 }}>→</span>
          </Link>
        </div>
      </nav>
      </header>

      {/* HERO */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(32px,5vw,64px)", padding: "clamp(48px,8vw,96px) clamp(16px,5vw,64px) clamp(40px,6vw,72px)", maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ flex: "1 1 420px", minWidth: 300 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "#eef9f4", color: "#0e8371", fontSize: 13, fontWeight: 700, padding: "6px 14px", borderRadius: 999, marginBottom: 20 }}>Hecho en Argentina para negocios que trabajan con turnos</div>
          <h1 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(34px,5vw,54px)", lineHeight: 1.08, margin: "0 0 20px" }}>Los que reservan y no vienen te están costando plata.</h1>
          <p style={{ fontSize: "clamp(16px,2vw,19px)", lineHeight: 1.6, color: "#5d6578", margin: "0 0 28px", maxWidth: 520, textWrap: "pretty" as any }}>Con Turnos360 tus clientes reservan solos, pagan la seña con Mercado Pago y reciben recordatorios automáticos. Vos atendés; el sistema agenda, cobra y te muestra los números.</p>
          {/* El botón grande crea la cuenta. Antes mandaba a WhatsApp y el nav,
              dos centímetros más arriba, decía "Comenzar gratis": el que venía
              de la publicidad leía dos cosas distintas en la misma pantalla.
              El alta asistida no se pierde — baja a ser la segunda opción, que
              es lo que en realidad es. */}
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
            <Link href="/registro" className="cta cta-fuerte">
              Crear mi cuenta gratis
              <span aria-hidden className="cta-flecha">→</span>
            </Link>
            <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="cta cta-suave">
              <span aria-hidden style={{ width: 9, height: 9, borderRadius: "50%", background: "#8bc540", flexShrink: 0 }} />
              Que me lo configuren
            </a>
          </div>
          <p style={{ fontSize: 13.5, color: "#8b93a7", margin: "16px 0 0", lineHeight: 1.55 }}>
            {DIAS_PRUEBA} días gratis · No pedimos tarjeta · Cancelás cuando quieras.
            <br />
            <span style={{ color: "#5d6578" }}>¿Preferís no cargar nada vos? Te damos de alta el negocio por WhatsApp, gratis.</span>
          </p>
        </div>
        <div style={{ flex: "1 1 380px", minWidth: 300, display: "flex", justifyContent: "center" }}>
          <div style={{ position: "relative", width: "100%", maxWidth: 420 }}>
            <div style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 24, boxShadow: "0 24px 60px rgba(28,34,44,0.12)", padding: 24 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
                <Monogram size={44} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>Barbería El Faro</div>
                  <div style={{ fontSize: 12.5, color: "#8b93a7" }}>turnos360.com.ar/elfaro</div>
                </div>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#5d6578", marginBottom: 10 }}>Elegí tu servicio</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", border: "2px solid #12b886", background: "#f2fbf7", borderRadius: 12, padding: "12px 14px" }}>
                  <span style={{ fontWeight: 700, fontSize: 14.5 }}>Corte + Barba</span>
                  <span style={{ fontWeight: 700, fontSize: 14.5, color: "#0e8371" }}>$15.000</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", border: "1px solid #e9ecf1", borderRadius: 12, padding: "12px 14px" }}>
                  <span style={{ fontWeight: 500, fontSize: 14.5, color: "#5d6578" }}>Corte clásico</span>
                  <span style={{ fontSize: 14.5, color: "#8b93a7" }}>$11.000</span>
                </div>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#5d6578", marginBottom: 10 }}>Mañana, jueves</div>
              <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
                {["10:00", "11:30", "15:00"].map((h, i) => (
                  <div key={h} style={{ flex: 1, textAlign: "center", borderRadius: 10, padding: "9px 0", fontSize: 14, ...(i === 1 ? { background: "#12b886", color: "#fff", fontWeight: 700 } : { border: "1px solid #e9ecf1", color: "#8b93a7" }) }}>{h}</div>
                ))}
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "#1c222c", borderRadius: 14, padding: "14px 16px" }}>
                <span style={{ color: "#fff", fontWeight: 700, fontSize: 14.5 }}>Reservar con seña</span>
                <img src="/img/mercado-pago.png" alt="Mercado Pago" style={{ height: 26, background: "#fff", borderRadius: 6, padding: "3px 8px" }} />
              </div>
            </div>
            <div style={{ position: "absolute", top: -16, right: -8, background: "#fff", border: "1px solid #e9ecf1", borderRadius: 999, padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 10px 24px rgba(28,34,44,0.10)" }}>
              <img src="/img/whatsapp.png" alt="WhatsApp" style={{ height: 18 }} />
              <span style={{ fontSize: 12.5, fontWeight: 700 }}>Recordatorio enviado</span>
            </div>
            <div style={{ position: "absolute", bottom: -14, left: -10, background: "#fff", border: "1px solid #e9ecf1", borderRadius: 999, padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 10px 24px rgba(28,34,44,0.10)" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#12b886" }} />
              <span style={{ fontSize: 12.5, fontWeight: 700 }}>Seña cobrada · $5.000</span>
            </div>
          </div>
        </div>
      </div>

      {/* INTEGRACIONES */}
      <section style={{ padding: "8px clamp(16px,5vw,64px) 56px", maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "center", gap: "clamp(24px,4vw,56px)", borderTop: "1px solid #eef1f5", paddingTop: 32 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#8b93a7", letterSpacing: "0.06em", textTransform: "uppercase" }}>Se integra con</span>
          <img src="/img/mercado-pago.png" alt="Mercado Pago" style={{ height: 44, opacity: 0.85 }} />
          <img src="/img/whatsapp.png" alt="WhatsApp" style={{ height: 30, opacity: 0.85 }} />
          <img src="/img/google-calendar.png" alt="Google Calendar" style={{ height: 32, opacity: 0.85 }} />
          <img src="/img/google-maps.png" alt="Google Maps" style={{ height: 30, opacity: 0.85 }} />
        </div>
      </section>

      {/* PROBLEMA */}
      <section style={{ background: "#f8f9fb", padding: "clamp(56px,8vw,88px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto" }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(24px,4vw,56px)", marginBottom: 40 }}>
            <div style={{ flex: "1 1 380px", minWidth: 280 }}>
              <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px", maxWidth: 640 }}>Si manejás el negocio con libreta y WhatsApp, esto te suena.</h2>
              <p style={{ color: "#5d6578", fontSize: 17, margin: 0, maxWidth: 560 }}>Cuatro cosas que le pasan a casi todos los dueños del rubro.</p>
            </div>
            <img src="/img/duena-notebook.jpg" alt="Dueña revisando sus números en Turnos360" style={{ flex: "1 1 320px", minWidth: 280, maxWidth: 440, width: "100%", borderRadius: 20, objectFit: "cover", aspectRatio: "3 / 2", boxShadow: "0 20px 48px rgba(28,34,44,0.14)" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {pains.map((p, i) => (
              <div key={p.num} className="revela" style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 18, padding: 24, "--demora": `${i * 70}ms` } as React.CSSProperties}>
                <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 26, color: "#12b886", marginBottom: 12 }}>{p.num}</div>
                <div style={{ fontWeight: 700, fontSize: 16.5, marginBottom: 8 }}>{p.title}</div>
                <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.55 }}>{p.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FUNCIONALIDADES */}
      <section id="funciones" style={{ padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ display: "inline-flex", background: "#fff7ec", color: "#b45309", fontSize: 13, fontWeight: 700, padding: "6px 14px", borderRadius: 999, marginBottom: 16 }}>Lo que la agenda común no hace</div>
        <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px", maxWidth: 620 }}>Anotar turnos lo hace cualquiera. Esto es lo que te diferencia.</h2>
        <p style={{ color: "#5d6578", fontSize: 17, margin: "0 0 40px", maxWidth: 600 }}>Turnos360 te dice cuánto ganaste, quién te lo generó y qué clientes dejaron de venir.</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          {features.map((f, i) => (
            <div key={f.title} className="revela tarjeta-hover" style={{ border: "1px solid #e9ecf1", borderRadius: 18, padding: 26, background: "#fff", "--demora": `${i * 70}ms` } as React.CSSProperties}>
              <div style={{ width: 42, height: 42, borderRadius: 12, background: "#eef9f4", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 19, marginBottom: 16, color: "#0e8371", fontWeight: 700, fontFamily: font.titulo }}>{f.glyph}</div>
              <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>{f.title}</div>
              <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.55 }}>{f.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PANEL / TABS */}
      <section style={{ background: "#f8f9fb", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>Todo el negocio en un solo lugar</h2>
          <p style={{ color: "#5d6578", fontSize: 17, margin: "0 auto 8px", maxWidth: 560 }}>Agenda, clientes, caja y estadísticas desde el celular o la compu. Estas son pantallas reales del sistema.</p>
          <img src="/img/notebook-mockup.webp" alt="Turnos360 en una notebook" style={{ width: "100%", maxWidth: 720, display: "block", margin: "0 auto 8px" }} />
          <div style={{ display: "inline-flex", background: "#fff", border: "1px solid #e9ecf1", borderRadius: 999, padding: 5, gap: 4, marginBottom: 28, flexWrap: "wrap", justifyContent: "center" }}>
            {shots.map((s, i) => (
              <button key={s.label} onClick={() => setTab(i)} style={{ border: "none", cursor: "pointer", fontFamily: font.texto, fontSize: 14.5, fontWeight: 700, padding: "9px 22px", borderRadius: 999, background: i === tab ? "#12b886" : "transparent", color: i === tab ? "#fff" : "#5d6578" }}>{s.label}</button>
            ))}
          </div>
          <div
            style={{ position: "relative", background: "#fff", border: "1px solid #e9ecf1", borderRadius: 20, padding: "clamp(8px,1.5vw,16px)", boxShadow: "0 24px 60px rgba(28,34,44,0.10)", overflow: "hidden", maxWidth: 940, margin: "0 auto" }}
            className="visor-panel"
          >
            {/* Las cuatro capturas van APILADAS y se cruzan por opacidad, en
                vez de cambiar el src de una sola.

                Cambiando el src, el navegador descarta la imagen vieja antes
                de tener la nueva: la primera vez que se toca cada pestaña
                aparece un parpadeo blanco, justo lo contrario de lo que busca
                una transición. Apiladas, las cuatro ya están decodificadas y
                el cruce es instantáneo.

                La primera va en flujo normal y define el alto del contenedor;
                las otras tres, absolutas encima. Solo la primera carga con
                prioridad: las demás quedan en lazy y el navegador las trae
                mientras el visitante lee lo de arriba. */}
            <div style={{ position: "relative" }}>
              {shots.map((s, i) => (
                <img
                  key={s.label}
                  src={s.src}
                  alt={`Turnos360 · ${s.label}`}
                  loading={i === 0 ? "eager" : "lazy"}
                  aria-hidden={i !== tab}
                  className="visor-img"
                  style={{
                    width: "100%",
                    display: "block",
                    borderRadius: 12,
                    opacity: i === tab ? 1 : 0,
                    ...(i === 0
                      ? { position: "relative" }
                      : { position: "absolute", inset: 0, height: "100%" }),
                  }}
                />
              ))}
            </div>

            {/* Mitades invisibles a los costados: click a la izquierda vuelve,
                a la derecha avanza. Se ven solo al pasar el mouse por encima
                (ver .visor-flecha en el bloque de estilos), así no ensucian la
                captura cuando alguien solo la está mirando. */}
            <button
              type="button"
              aria-label="Pantalla anterior"
              onClick={() => setTab((t) => (t - 1 + shots.length) % shots.length)}
              className="visor-lado visor-lado-izq"
            >
              <span className="visor-flecha" aria-hidden>‹</span>
            </button>
            <button
              type="button"
              aria-label="Pantalla siguiente"
              onClick={() => setTab((t) => (t + 1) % shots.length)}
              className="visor-lado visor-lado-der"
            >
              <span className="visor-flecha" aria-hidden>›</span>
            </button>
          </div>
          <p style={{ color: "#8b93a7", fontSize: 14, margin: "20px 0 0" }}>{shots[tab].caption}</p>
        </div>
      </section>

      {/* COMPARTIR / REDES */}
      <section style={{ padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(32px,5vw,72px)" }}>
          <div style={{ flex: "1 1 360px", minWidth: 280 }}>
            <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 16px" }}>Tu página de reservas, donde quieras</h2>
            <p style={{ color: "#5d6578", fontSize: 17, lineHeight: 1.6, margin: "0 0 24px", maxWidth: 480, textWrap: "pretty" as any }}>Cada negocio tiene su propia página con su logo, sus servicios y sus horarios. Ponela en la bio de Instagram, en el estado de WhatsApp o imprimí el QR y pegalo en el espejo del local. El cliente reserva solo, incluso a las 2 de la mañana.</p>
            <a href={WA_LINK} target="_blank" style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "#1c222c", color: "#fff", fontWeight: 700, fontSize: 16, padding: "14px 26px", borderRadius: 999, textDecoration: "none" }}>Quiero mi página</a>
          </div>
          <div style={{ flex: "1 1 380px", minWidth: 300, display: "flex", justifyContent: "center" }}>
            <div style={{ position: "relative", width: "100%", maxWidth: 480, aspectRatio: "1.02" }}>
              <div style={{ position: "absolute", inset: "4% 0 4% 6%", background: "radial-gradient(ellipse at center, #e3f6ee 0%, #eef9f4 70%)", borderRadius: "50%" }} />
              {/* WhatsApp */}
              <div style={{ position: "absolute", top: "8%", right: "6%", width: "52%", background: "#25d366", borderRadius: 20, padding: 16, transform: "rotate(3deg)", boxShadow: "0 16px 40px rgba(28,34,44,0.16)" }} className="flota flota-1">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}><Monogram /><span style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>WhatsApp</span></div>
                  <img src="/img/whatsapp-icon.png" alt="WhatsApp" style={{ width: 28, height: 28, objectFit: "contain" }} />
                </div>
                <div style={{ height: 8, background: "rgba(255,255,255,0.45)", borderRadius: 99, margin: "14px 0 8px", width: "82%" }} />
                <div style={{ height: 8, background: "rgba(255,255,255,0.45)", borderRadius: 99, width: "58%" }} />
              </div>
              {/* QR */}
              <div style={{ position: "absolute", top: "22%", right: "16%", width: "52%", background: "#5d6578", borderRadius: 20, padding: 16, transform: "rotate(-2deg)", boxShadow: "0 16px 40px rgba(28,34,44,0.18)" }} className="flota flota-2">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}><Monogram /><span style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>QR del local</span></div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 5px)", gridTemplateRows: "repeat(4, 5px)", gap: 2 }}>
                    {[1,1,0,1,1,0,1,0,0,1,1,1,1,0,1,1].map((on, i) => <span key={i} style={{ background: on ? "#fff" : "transparent" }} />)}
                  </div>
                </div>
                <div style={{ height: 8, background: "rgba(255,255,255,0.4)", borderRadius: 99, margin: "14px 0 8px", width: "76%" }} />
                <div style={{ height: 8, background: "rgba(255,255,255,0.4)", borderRadius: 99, width: "52%" }} />
              </div>
              {/* TikTok */}
              <div style={{ position: "absolute", top: "37%", right: "24%", width: "52%", background: "#16181f", borderRadius: 20, padding: 16, transform: "rotate(2deg)", boxShadow: "0 16px 40px rgba(28,34,44,0.22)" }} className="flota flota-3">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}><Monogram invert /><span style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>TikTok</span></div>
                  <img src="/img/tiktok-icon.png" alt="TikTok" style={{ width: 28, height: 28, borderRadius: "50%", objectFit: "cover" }} />
                </div>
                <div style={{ height: 8, background: "rgba(255,255,255,0.3)", borderRadius: 99, margin: "14px 0 8px", width: "80%" }} />
                <div style={{ height: 8, background: "rgba(255,255,255,0.3)", borderRadius: 99, width: "55%" }} />
              </div>
              {/* Instagram */}
              <div style={{ position: "absolute", top: "52%", right: "32%", width: "54%", background: "linear-gradient(135deg, #6228d7 0%, #ee2a7b 55%, #f9ce34 120%)", borderRadius: 20, padding: 18, transform: "rotate(-3deg)", boxShadow: "0 24px 56px rgba(238,42,123,0.35)" }} className="flota flota-4">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9 }}><Monogram size={34} /><span style={{ color: "#fff", fontWeight: 700, fontSize: 15 }}>Instagram</span></div>
                  <img src="/img/instagram-icon.png" alt="Instagram" style={{ width: 28, height: 28, borderRadius: 8, objectFit: "contain" }} />
                </div>
                <div style={{ height: 9, background: "rgba(255,255,255,0.5)", borderRadius: 99, margin: "16px 0 9px", width: "84%" }} />
                <div style={{ height: 9, background: "rgba(255,255,255,0.5)", borderRadius: 99, width: "60%" }} />
              </div>
              <div style={{ position: "absolute", bottom: "6%", left: 0, background: "#fff", borderRadius: 999, padding: "13px 22px", fontWeight: 700, fontSize: 15, boxShadow: "0 16px 40px rgba(28,34,44,0.18)", whiteSpace: "nowrap" }}>turnos360.com.ar/<span style={{ color: "#12b886" }}>elfaro</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* MULTISUCURSAL */}
      <section id="sucursales" style={{ background: "#f8f9fb", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(32px,5vw,64px)" }}>
          <div style={{ flex: "1 1 420px", minWidth: 300 }}>
            <div style={{ display: "inline-flex", background: "#eef2ff", color: "#4338ca", fontSize: 13, fontWeight: 700, padding: "6px 14px", borderRadius: 999, marginBottom: 16 }}>Para los que tienen más de un local</div>
            <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>Dos locales, dos cajas, un solo panel.</h2>
            <p style={{ color: "#5d6578", fontSize: 17, lineHeight: 1.6, margin: "0 0 28px", maxWidth: 520 }}>
              Cuando abrís el segundo local, la mayoría de los sistemas te obliga a pagar dos cuentas y a sumar los números a mano. Acá cada sucursal tiene su caja, su equipo y su agenda, y vos las ves todas juntas.
            </p>
            <div style={{ display: "grid", gap: 18 }}>
              {locales.map((l, i) => (
                <div key={l.title} className="revela" style={{ display: "flex", gap: 12, "--demora": `${i * 70}ms` } as React.CSSProperties}>
                  <span style={{ color: "#12b886", fontWeight: 700, fontSize: 17, lineHeight: 1.45, flexShrink: 0 }}>✓</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16.5, marginBottom: 4 }}>{l.title}</div>
                    <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.55 }}>{l.body}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Comparativa de dos locales. Son números de ejemplo y la etiqueta
              lo dice: la landing no puede insinuar que son reales. */}
          <div style={{ flex: "1 1 360px", minWidth: 300 }}>
            <div style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 24, boxShadow: "0 24px 60px rgba(28,34,44,0.10)", padding: "clamp(20px,3vw,28px)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
                <span style={{ fontWeight: 700, fontSize: 15 }}>Comparativa del mes</span>
                <span style={{ fontSize: 12, color: "#8b93a7", background: "#f3f5f8", borderRadius: 999, padding: "4px 10px" }}>Ejemplo</span>
              </div>
              {[
                { nombre: "El Faro · Centro", monto: "$1.840.000", turnos: "212 turnos", barra: 100, color: "#12b886" },
                { nombre: "El Faro · Godoy Cruz", monto: "$1.115.000", turnos: "141 turnos", barra: 61, color: "#8bc540" },
              ].map((l) => (
                <div key={l.nombre} style={{ marginBottom: 20 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8, gap: 12 }}>
                    <span style={{ fontWeight: 700, fontSize: 14.5 }}>{l.nombre}</span>
                    <span style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 17 }}>{l.monto}</span>
                  </div>
                  <div style={{ height: 10, borderRadius: 999, background: "#f0f2f6", overflow: "hidden" }}>
                    <div style={{ width: `${l.barra}%`, height: "100%", borderRadius: 999, background: l.color }} />
                  </div>
                  <div style={{ fontSize: 12.5, color: "#8b93a7", marginTop: 6 }}>{l.turnos}</div>
                </div>
              ))}
              <div style={{ borderTop: "1px solid #eef1f5", paddingTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13.5, color: "#5d6578" }}>Caja abierta hoy</span>
                <span style={{ fontSize: 13.5, fontWeight: 700 }}>2 de 3 locales</span>
              </div>
            </div>
            <p style={{ fontSize: 13, color: "#8b93a7", margin: "14px 4px 0", textAlign: "center" }}>
              Incluido en el plan, sin costo por local extra.
            </p>
          </div>
        </div>
      </section>

      {/* COMO FUNCIONA */}
      <section id="como-funciona" style={{ background: "#1c222c", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1120, margin: "0 auto" }}>
          <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px", color: "#fff" }}>Andando en la misma tarde</h2>
          <p style={{ color: "#8b93a7", fontSize: 17, margin: "0 0 44px", maxWidth: 560 }}>Te das de alta solo, en dos minutos y sin tarjeta. Y si preferís que lo carguemos nosotros, también: escribinos y lo dejamos listo con vos.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20 }}>
            {steps.map((s, i) => (
              <div key={s.num} className="revela" style={{ border: "1px solid rgba(255,255,255,0.12)", borderRadius: 20, padding: 28, background: "rgba(255,255,255,0.04)", "--demora": `${i * 90}ms` } as React.CSSProperties}>
                <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 14, color: "#8bc540", letterSpacing: "0.12em", marginBottom: 14 }}>PASO {s.num}</div>
                <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 21, color: "#fff", marginBottom: 10 }}>{s.title}</div>
                <div style={{ color: "#b8bfcc", fontSize: 15, lineHeight: 1.6 }}>{s.body}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 36, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16, border: "1px solid rgba(139,197,64,0.35)", background: "rgba(139,197,64,0.08)", borderRadius: 16, padding: "18px 22px" }}>
            <span style={{ background: "#8bc540", color: "#1c222c", fontWeight: 700, fontSize: 12, padding: "5px 12px", borderRadius: 999, letterSpacing: "0.06em" }}>PILOTO</span>
            <span style={{ color: "#e6eadf", fontSize: 15 }}>La configuración inicial se bonifica para los primeros negocios, a cambio de tu testimonio real.</span>
          </div>
        </div>
      </section>

      {/* RUBROS */}
      <section id="rubros" style={{ padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", maxWidth: 1120, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>Hecho para tu rubro</h2>
        <p style={{ color: "#5d6578", fontSize: 17, margin: "0 auto 36px", maxWidth: 520 }}>Servicios con duración, profesional y precio. Si trabajás con turnos, Turnos360 es para vos.</p>
        {/* Cinta continua en vez de grilla.

            Con grilla, seis o siete rubros siempre dejan una fila incompleta y
            hay que elegir el número de tarjetas para que cierre. Acá corren en
            una sola línea, así que sumar un rubro no rompe nada.

            La lista va DUPLICADA y la animación desplaza exactamente el 50%:
            cuando termina, el primer clon está en la posición del original y
            el salto es invisible. Es la única forma de que el loop no dé un
            tirón al reiniciar. */}
        <div
          style={{
            overflow: "hidden",
            WebkitMaskImage: "linear-gradient(90deg, transparent 0%, #000 6%, #000 94%, transparent 100%)",
            maskImage: "linear-gradient(90deg, transparent 0%, #000 6%, #000 94%, transparent 100%)",
          }}
        >
          <div className="cinta-rubros" style={{ display: "flex", gap: 16, width: "max-content" }}>
            {[...rubros, ...rubros].map((r, i) => (
              <div
                key={`${r.label}-${i}`}
                aria-hidden={i >= rubros.length}
                style={{ width: 190, flexShrink: 0, border: "1px solid #e9ecf1", borderRadius: 18, overflow: "hidden", background: "#fff", textAlign: "left" }}
              >
                <FotoRubro src={r.img} emoji={r.emoji} label={r.label} />
                <div style={{ padding: "14px 16px", fontWeight: 700, fontSize: 15.5 }}>{r.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRECIOS */}
      <section id="precios" style={{ background: "#f8f9fb", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", position: "relative", overflow: "hidden" }}>
        {/* Dos halos muy diluidos detrás de las tarjetas. Sin esto la sección
            es un rectángulo gris y las tres tarjetas flotan sin apoyarse en
            nada — que es la sensación exacta de "plano". */}
        <div aria-hidden style={{ position: "absolute", inset: 0, background: "radial-gradient(620px 320px at 20% 0%, rgba(18,184,134,0.10), transparent 62%), radial-gradient(560px 300px at 82% 12%, rgba(139,197,64,0.10), transparent 60%)", pointerEvents: "none" }} />
        <div style={{ maxWidth: 1120, margin: "0 auto", position: "relative" }}>
          <div style={{ textAlign: "center", marginBottom: 44 }}>
            <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>
              Elegí por el tamaño de tu equipo
            </h2>
            <p style={{ color: "#5d6578", fontSize: 17, margin: "0 auto", maxWidth: 560 }}>
              Los tres traen la agenda completa, tu página de reservas y las señas.
              Lo que cambia es cuánta gente entra y qué más podés vender.
            </p>
          </div>

          <div className="grilla-planes">
            {planes.map((p, i) => (
              <div
                key={p.codigo}
                className={`plan revela ${p.destacado ? "plan-destacado" : ""}`}
                style={{ "--demora": `${i * 90}ms` } as React.CSSProperties}
              >
                {p.destacado && <div className="plan-cinta">El que más eligen</div>}

                <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 21, marginBottom: 4 }}>
                  {p.nombre}
                </div>
                <p style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.5, margin: "0 0 18px", minHeight: 44 }}>
                  {p.paraQuien}
                </p>

                <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
                  {PROMO_ACTIVA && p.codigo === "inicial" && (
                    <span style={{ color: "#9aa3b2", fontSize: 19, fontWeight: 600, textDecoration: "line-through" }}>
                      {PRECIO_NORMAL_TEXTO}
                    </span>
                  )}
                  <span style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: p.precio === null ? "clamp(24px,2.6vw,30px)" : "clamp(32px,3.6vw,42px)", letterSpacing: "-0.02em" }}>
                    {p.precio === null ? "A convenir" : enPesos(p.precio)}
                  </span>
                  {p.precio !== null && (
                    <span style={{ color: "#5d6578", fontSize: 16, fontWeight: 500 }}>/ mes</span>
                  )}
                </div>
                {PROMO_ACTIVA && p.codigo === "inicial" && (
                  <div style={{ display: "inline-flex", background: "#fff4e0", color: "#9a6212", fontWeight: 700, fontSize: 12, padding: "4px 11px", borderRadius: 999, marginTop: 8 }}>
                    {PROMO_ETIQUETA}
                  </div>
                )}

                {/* Los cupos arriba y separados de las funciones: es el dato
                    por el que se elige un plan, y enterrado en una lista de
                    nueve renglones no se encuentra. */}
                <div className="plan-cupos">
                  {p.cupos.map((c) => (
                    <div key={c} className="plan-cupo">{c}</div>
                  ))}
                </div>

                <p style={{ color: "#8b93a7", fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 12px" }}>
                  {p.tituloLista}
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 26, flex: 1 }}>
                  {p.incluye.map((it) => (
                    <div key={it} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 14.5, lineHeight: 1.45, color: "#2a3140" }}>
                      <span aria-hidden style={{ color: "#12b886", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>✓</span>
                      {it}
                    </div>
                  ))}
                </div>

                {p.precio === null ? (
                  <a
                    href={WA_LINK}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="cta cta-suave"
                    style={{ width: "100%" }}
                  >
                    Hablemos
                    <span aria-hidden className="cta-flecha">→</span>
                  </a>
                ) : (
                  <Link
                    href="/registro"
                    className={`cta ${p.destacado ? "cta-fuerte" : "cta-suave"}`}
                    style={{ width: "100%" }}
                  >
                    Probalo {DIAS_PRUEBA} días gratis
                    <span aria-hidden className="cta-flecha">→</span>
                  </Link>
                )}
              </div>
            ))}
          </div>

          {/* ── Enterprise, abajo y a lo ancho ─────────────────────────
              Fuera de la fila a propósito: ver el comentario de
              .plan-enterprise en los estilos. Acá el layout es horizontal
              —quién es a la izquierda, qué incluye a la derecha— porque sin
              precio que mostrar, la tarjeta vertical quedaba con un hueco
              enorme donde iba el número. */}
          <div className="plan-enterprise revela">
            <div>
              <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 21, marginBottom: 4 }}>
                {ENTERPRISE.nombre}
              </div>
              <p style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.5, margin: "0 0 14px" }}>
                {ENTERPRISE.paraQuien}
              </p>
              <div className="plan-cupos" style={{ marginBottom: 18 }}>
                {ENTERPRISE.cupos.map((c) => (
                  <div key={c} className="plan-cupo">{c}</div>
                ))}
              </div>
              <a
                href={WA_LINK}
                target="_blank"
                rel="noopener noreferrer"
                className="cta cta-suave"
              >
                Hablemos
                <span aria-hidden className="cta-flecha">→</span>
              </a>
            </div>

            <div>
              <p style={{ color: "#8b93a7", fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 12px" }}>
                Todo lo de Multi, más:
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {ENTERPRISE.incluye.map((it) => (
                  <div key={it} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 14.5, lineHeight: 1.45, color: "#2a3140" }}>
                    <span aria-hidden style={{ color: "#12b886", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>✓</span>
                    {it}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p style={{ color: "#8b93a7", fontSize: 14, textAlign: "center", margin: "28px auto 0", maxWidth: 620, lineHeight: 1.6 }}>
            {DIAS_PRUEBA} días gratis con <b style={{ color: "#5d6578" }}>todo desbloqueado</b>, sin
            tarjeta. Precios en pesos, cancelás cuando quieras. Cambiás de plan
            cuando te queda chico.{" "}
            <a href={WA_LINK} target="_blank" rel="noopener noreferrer" style={{ color: "#0e8371", fontWeight: 600 }}>
              O que te lo configuremos gratis
            </a>
            .
          </p>
        </div>
      </section>

      {/* GALERIA */}
      <section style={{ padding: "0 clamp(16px,5vw,64px) clamp(48px,7vw,80px)", maxWidth: 1120, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          {fotos.map((f, i) => (
            <img key={f.src} src={f.src} alt={f.alt} className="revela" style={{ width: "100%", height: 260, objectFit: "cover", borderRadius: 20, "--demora": `${i * 80}ms` } as React.CSSProperties} />
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" style={{ padding: "0 clamp(16px,5vw,64px) clamp(56px,8vw,96px)", maxWidth: 820, margin: "0 auto" }}>
        <h2 style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 8px", textAlign: "center" }}>Preguntas frecuentes</h2>
        <p style={{ color: "#5d6578", fontSize: 17, margin: "0 0 32px", textAlign: "center" }}>Lo que todos preguntan antes de arrancar.</p>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {faqs.map((q, i) => (
            <div key={q.q} style={{ borderBottom: "1px solid #e9ecf1" }}>
              <button onClick={() => setFaq(faq === i ? -1 : i)} style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: "18px 4px", fontFamily: font.texto, fontSize: 16.5, fontWeight: 700, color: "#1c222c" }}>
                {q.q}
                <span style={{ color: "#12b886", fontSize: 20, fontWeight: 700, flexShrink: 0 }}>{faq === i ? "−" : "+"}</span>
              </button>
              {faq === i && <div style={{ color: "#5d6578", fontSize: 15, lineHeight: 1.6, padding: "0 4px 18px", maxWidth: 680 }}>{q.a}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* El CIERRE salió de acá: era una segunda tanda de «Crear mi cuenta
          gratis» + «Hablar por WhatsApp», los mismos dos botones que ya están
          arriba de todo y en cada tarjeta de precio. Lo pidió Leandro y tiene
          razón: al que llegó hasta el final ya se le ofreció cuatro veces, y
          la quinta no convence a nadie — solo estira la página entre las
          preguntas frecuentes y el footer, que es donde el que busca el
          teléfono o los términos tiene que llegar rápido. */}

      {/* FOOTER */}
      <footer style={{ borderTop: "1px solid #eef1f5", padding: "28px clamp(16px,5vw,64px)", display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src={logo.src} onError={logo.alFallar} alt="Turnos360" style={{ width: 28, height: 28, objectFit: "contain" }} />
          <span style={{ fontFamily: font.marca, fontWeight: 700, fontSize: 16 }}>Turnos<span style={{ color: "#12b886" }}>360</span></span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <Link href="/terminos" style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}>
              Términos y condiciones
            </Link>
            <span style={{ color: "#cfd5de", fontSize: 13.5 }}>·</span>
            <Link href="/privacidad" style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}>
              Política de privacidad
            </Link>
            <span style={{ color: "#cfd5de", fontSize: 13.5 }}>·</span>
            <a
              href={WA_LINK}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}
            >
              WhatsApp
            </a>
            <span style={{ color: "#cfd5de", fontSize: 13.5 }}>·</span>
            <a
              href={INSTAGRAM}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}
            >
              Instagram
            </a>
          </div>
          <span style={{ color: "#8b93a7", fontSize: 13.5, textAlign: "right" }}>
            © {new Date().getFullYear()} Turnos360 · Hecho en Mendoza, Argentina ·{" "}
            <a href={`mailto:${EMAIL_CONTACTO}`} style={{ color: "#5d6578" }}>
              {EMAIL_CONTACTO}
            </a>
          </span>
        </div>
      </footer>

      {/* En el celular el botón del hero se pierde al segundo scroll y el
          siguiente recién aparece en Precios. Esta barra queda siempre a mano.
          Solo en pantallas chicas: en escritorio ya está el del nav. */}
      <div className="barra-movil">
        <Link href="/registro" className="cta cta-fuerte" style={{ flex: 1, justifyContent: "center" }}>
          Crear mi cuenta gratis
        </Link>
        <a
          href={WA_LINK}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Escribinos por WhatsApp"
          className="barra-movil-wa"
        >
          <svg viewBox="0 0 24 24" width="23" height="23" fill="#25D366" aria-hidden focusable="false">
            <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.25-.46-2.39-1.47-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.14-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.48s1.06 2.87 1.21 3.07c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.71 2-1.4.25-.69.25-1.28.17-1.4-.07-.13-.27-.2-.57-.35z"/>
            <path d="M12.04 2C6.6 2 2.17 6.43 2.17 11.87c0 1.74.46 3.44 1.32 4.94L2.09 22l5.33-1.38a9.83 9.83 0 0 0 4.62 1.17h.01c5.44 0 9.87-4.43 9.87-9.87 0-2.64-1.03-5.12-2.9-6.98A9.8 9.8 0 0 0 12.04 2zm0 1.79c2.16 0 4.19.84 5.72 2.37a8.03 8.03 0 0 1 2.37 5.71c0 4.46-3.63 8.09-8.09 8.09a8.1 8.1 0 0 1-4.12-1.13l-.3-.18-3.06.8.82-3-.19-.31a8.04 8.04 0 0 1-1.24-4.31c0-4.46 3.63-8.08 8.09-8.08z"/>
          </svg>
        </a>
      </div>
    </div>
    </>
  );
}
