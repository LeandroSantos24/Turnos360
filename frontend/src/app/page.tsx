"use client";

/**
 * Landing de Turnos360.
 *
 * ESTRUCTURA: hero oscuro a sangre, el resto claro, «Cómo funciona» vuelve al
 * oscuro para partir la página al medio. El movimiento sale de
 * components/landing (framer-motion), no de clases CSS sueltas.
 *
 * OJO CON LAS COMILLAS DOBLES DENTRO DEL BLOQUE <style>, incluso en un
 * comentario: React las serializa como &quot; en el servidor y las deja como "
 * al hidratar, y salta «Text content does not match server-rendered HTML». Si
 * hacen falta comillas ahí adentro, van « ».
 */

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "framer-motion";

import { WA_LINK_DEMO as WA_LINK, INSTAGRAM, EMAIL_CONTACTO } from "@/lib/contacto";
import { useLogoMarca } from "@/lib/marca";
import {
  PRECIO_MENSUAL,
  PRECIO_NORMAL_TEXTO,
  PROMO_ACTIVA,
  PROMO_ETIQUETA,
  DIAS_PRUEBA,
} from "@/lib/precios";
import { EASE, Revelar } from "@/components/landing/movimiento";
import { MockupReserva } from "@/components/landing/mockup-reserva";
import { TelefonoLocal } from "@/components/landing/telefono-local";

const font = {
  titulo: "var(--fuente-titulos)",
  texto: "var(--fuente)",
  marca: "var(--fuente-marca)",
};

/** El ancho útil de toda la página. Antes 1120: en un monitor de 1920 el
 *  contenido quedaba en una columna angosta con dos franjas vacías enormes. */
const ANCHO = 1240;
const LADOS = "clamp(20px,5vw,72px)";
const caja = { maxWidth: ANCHO, margin: "0 auto" } as const;

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
  { glyph: "∞", title: "Membresías y gift cards", body: "“Pagás $50.000 y tenés los cortes del mes.” Abonos, gift cards con QR y cupones para llenar horas flojas." },
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
 * Rubros de «Hecho para tu rubro».
 *
 * `img` es OPCIONAL a propósito: mientras no exista el archivo, la tarjeta cae
 * al emoji y la sección se ve completa igual.
 * Formato: 800 × 1000 px (4:5), JPG, bajo 150 KB, en /public/img/.
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

const locales = [
  { title: "Una caja por local", body: "Cada sucursal abre y cierra la suya. Los turnos, las gift cards, los abonos y los gastos caen en la caja del local donde pasaron." },
  { title: "Cada uno con su equipo", body: "El profesional queda atado a su sucursal y solo ve su agenda. El dueño ve todas, y puede filtrar por local cuando quiere." },
  { title: "Comparás locales de verdad", body: "Facturación, turnos y ausencias de un local contra el otro, en el mismo gráfico. Ahí se ve cuál rinde y cuál no." },
  { title: "Tu cliente elige dónde", body: "La página de reservas muestra los locales abiertos con su dirección, y cada uno puede tener su propio precio." },
];

/** Dónde se comparte el link de la página de reservas. */
const canales = [
  { icono: "/img/instagram-icon.png", label: "En la bio de Instagram" },
  { icono: "/img/whatsapp-icon.png", label: "En tu estado de WhatsApp" },
  { icono: "/img/tiktok-icon.png", label: "En el perfil de TikTok" },
  { icono: "/img/google-maps.png", label: "En tu ficha de Google" },
];

/**
 * Los cuatro planes, espejo de backend/app/core/planes.py.
 *
 * `incluye` es lo que ESE plan suma sobre el anterior, no la lista completa:
 * repetir las nueve líneas en las tres columnas hace que se lean iguales y el
 * que compara no encuentra la diferencia, que es lo único que busca.
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
 * Enterprise, aparte de los tres: no tiene precio de lista, no se contrata
 * online y su botón lleva a WhatsApp. Puesto en la fila obliga a comparar lo
 * que no se compara, y la columna sin número rompe la lectura justo donde el
 * ojo busca el precio.
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
  { src: "/img/elfaro-portada.webp", alt: "Barbería" },
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
 * Datos estructurados para Google, armados del mismo array `faqs` que se
 * muestra en pantalla: duplicados a mano, el día que cambie una respuesta uno
 * de los dos queda viejo y Google marca el schema como no coincidente.
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

/** Título de sección: rótulo chico + h2 grande + bajada. */
function Titulo({
  rotulo,
  color = "#0e8371",
  fondo = "#eef9f4",
  h2,
  bajada,
  centrado,
  oscuro,
  ancho = 720,
}: {
  rotulo?: string;
  color?: string;
  fondo?: string;
  h2: React.ReactNode;
  bajada?: React.ReactNode;
  centrado?: boolean;
  oscuro?: boolean;
  ancho?: number;
}) {
  return (
    <Revelar style={{ textAlign: centrado ? "center" : "left", marginBottom: 44 }}>
      {rotulo && (
        <div style={{ display: "inline-flex", background: fondo, color, fontSize: 13, fontWeight: 700, padding: "7px 15px", borderRadius: 999, marginBottom: 18 }}>
          {rotulo}
        </div>
      )}
      <h2
        style={{
          fontFamily: font.titulo,
          fontWeight: 700,
          fontSize: "clamp(28px,3.9vw,46px)",
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          margin: 0,
          color: oscuro ? "#fff" : "#12161f",
          maxWidth: ancho,
          marginInline: centrado ? "auto" : undefined,
          textWrap: "balance" as React.CSSProperties["textWrap"],
        }}
      >
        {h2}
      </h2>
      {bajada && (
        <p
          style={{
            color: oscuro ? "#9aa5b8" : "#5d6578",
            fontSize: "clamp(16px,1.35vw,18.5px)",
            lineHeight: 1.6,
            margin: "14px 0 0",
            maxWidth: 620,
            marginInline: centrado ? "auto" : undefined,
            textWrap: "pretty" as React.CSSProperties["textWrap"],
          }}
        >
          {bajada}
        </p>
      )}
    </Revelar>
  );
}

export default function Page() {
  const logo = useLogoMarca();
  const [tab, setTab] = useState(0);
  const [faq, setFaq] = useState(-1);

  // La barra arranca transparente sobre el hero oscuro y se vuelve blanca al
  // primer scroll. 48px y no 0: con el umbral en cero, el rebote del scroll en
  // iOS la hacía parpadear al llegar arriba.
  const { scrollY } = useScroll();
  const [compacta, setCompacta] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setCompacta(v > 48));

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(datosEstructurados(faqs)) }}
      />

      <style>{`
        /* ── Barra superior ──────────────────────────────────────────────
           Grilla de tres columnas (1fr · auto · 1fr) y no space-between: con
           space-between el grupo del medio se centra entre el logo y los
           botones, que miden distinto, y los links quedaban corridos. */
        .nav-fija {
          position: sticky; top: 0; z-index: 50;
          border-bottom: 1px solid transparent;
          transition: background-color .3s ease, border-color .3s ease,
                      backdrop-filter .3s ease, box-shadow .3s ease;
        }
        .nav-clara {
          background: rgba(255,255,255,0.86);
          backdrop-filter: blur(14px);
          border-bottom-color: #e9ecf1;
          box-shadow: 0 1px 24px rgba(16,22,32,.05);
        }
        .nav-barra {
          display: grid;
          grid-template-columns: 1fr auto 1fr;
          align-items: center;
        }
        .nav-links { display: flex; align-items: center; gap: 28px; justify-self: center; }
        .nav-accesos { justify-self: end; }

        .nav-link {
          font-size: 15px; font-weight: 500; text-decoration: none;
          color: rgba(255,255,255,.72);
          transition: color .25s ease;
        }
        .nav-link:hover { color: #fff; }
        .nav-clara .nav-link { color: #5d6578; }
        .nav-clara .nav-link:hover { color: #12161f; }

        .nav-marca { color: #fff; transition: color .3s ease; }
        .nav-clara .nav-marca { color: #12161f; }

        .nav-boton {
          display: inline-flex; align-items: center; justify-content: center;
          gap: 8px; height: 42px; padding: 0 20px;
          border-radius: 999px;
          font-size: 15px; font-weight: 600;
          white-space: nowrap; text-decoration: none;
          transition: background-color .22s ease, border-color .22s ease,
                      box-shadow .22s ease, transform .22s ease, color .22s ease;
        }
        .nav-boton:focus-visible { outline: 2px solid #12b886; outline-offset: 3px; }

        .nav-boton-suave {
          color: rgba(255,255,255,.88);
          background: rgba(255,255,255,.07);
          border: 1px solid rgba(255,255,255,.18);
        }
        .nav-boton-suave:hover { background: rgba(255,255,255,.14); color: #fff; }
        .nav-clara .nav-boton-suave {
          color: #39414f; background: #fff; border-color: #e4e8ee;
        }
        .nav-clara .nav-boton-suave:hover { background: #f7f9fb; border-color: #cfd6e0; color: #12161f; }

        .nav-boton-fuerte {
          color: #06251c; background: #12b886; border: 1px solid #12b886;
          padding: 0 22px;
          box-shadow: 0 6px 20px rgba(18,184,134,.28);
        }
        .nav-boton-fuerte:hover {
          background: #0fd39a; border-color: #0fd39a;
          box-shadow: 0 10px 26px rgba(18,184,134,.38);
          transform: translateY(-1px);
        }
        .nav-boton-fuerte:active { transform: translateY(0); }
        .nav-flecha { transition: transform .22s ease; }
        .nav-corto { display: none; }
        .nav-boton-fuerte:hover .nav-flecha { transform: translateX(3px); }

        /* Por debajo de ~1240 las dos columnas de los costados dejan de medir
           igual y el menú del medio se corre. Los accesos acortan la etiqueta
           y el eje vuelve a su lugar. */
        @media (max-width: 1240px) {
          .nav-largo { display: none; }
          .nav-corto { display: inline; }
          .nav-flecha { display: none; }
        }
        @media (max-width: 900px) {
          .nav-barra { grid-template-columns: auto 1fr; }
          .nav-links { display: none; }
        }
        @media (max-width: 560px) {
          .nav-boton { height: 40px; padding: 0 14px; font-size: 14px; }
          .nav-boton-fuerte { padding: 0 16px; gap: 6px; }
        }
        @media (max-width: 360px) {
          .nav-boton { padding: 0 12px; }
        }

        /* ── Llamados a la acción ──────────────────────────────────────── */
        .cta {
          display: inline-flex; align-items: center; justify-content: center;
          gap: 10px;
          padding: 16px 30px;
          border-radius: 999px;
          font-size: 17px; font-weight: 700;
          white-space: nowrap; text-decoration: none;
          transition: background-color .2s ease, border-color .2s ease,
                      box-shadow .2s ease, transform .2s ease, color .2s ease;
        }
        .cta:focus-visible { outline: 2px solid #12b886; outline-offset: 3px; }
        .cta-flecha { transition: transform .2s ease; }
        .cta:hover .cta-flecha { transform: translateX(3px); }

        .cta-fuerte {
          background: #12b886; color: #06251c;
          border: 1px solid #12b886;
          box-shadow: 0 10px 30px rgba(18,184,134,0.32);
        }
        .cta-fuerte:hover {
          background: #0fd39a; border-color: #0fd39a;
          box-shadow: 0 14px 38px rgba(18,184,134,0.42);
          transform: translateY(-1px);
        }
        .cta-fuerte:active { transform: translateY(0); }

        .cta-suave { background: #fff; color: #12161f; border: 1px solid #e4e8ee; }
        .cta-suave:hover { background: #f7f9fb; border-color: #cfd6e0; }

        /* Variante del hero: sobre el oscuro, el blanco sólido gritaba más que
           el botón principal. */
        .cta-fantasma {
          background: rgba(255,255,255,.06);
          color: #fff;
          border: 1px solid rgba(255,255,255,.22);
        }
        .cta-fantasma:hover { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.34); }

        .tarjeta-hover {
          transition: transform .26s cubic-bezier(.32,.72,0,1),
                      box-shadow .26s cubic-bezier(.32,.72,0,1),
                      border-color .26s cubic-bezier(.32,.72,0,1);
        }
        .tarjeta-hover:hover {
          transform: translateY(-4px);
          border-color: #bfe6d8 !important;
          box-shadow: 0 22px 46px -16px rgba(18,184,134,.26);
        }

        /* ── Grilla de planes ────────────────────────────────────────────
           TRES columnas: Enterprise sale de la fila y va debajo, a lo ancho. */
        .grilla-planes {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 20px;
          align-items: stretch;
        }
        @media (max-width: 980px) {
          .grilla-planes { grid-template-columns: 1fr; max-width: 460px; margin: 0 auto; gap: 22px; }
          .plan-destacado { transform: none; }
          .plan-destacado:hover { transform: translateY(-4px); }
        }
        .plan-enterprise {
          max-width: 820px;
          margin: 24px auto 0;
          display: grid;
          grid-template-columns: 1.1fr 1fr;
          gap: 28px;
          align-items: center;
          background: #fff;
          border: 1px solid #e4e8ee;
          border-radius: 24px;
          padding: 28px 32px;
        }
        @media (max-width: 720px) {
          .plan-enterprise { grid-template-columns: 1fr; gap: 18px; padding: 24px; }
        }
        .plan {
          display: flex;
          flex-direction: column;
          background: #fff;
          border: 1px solid #e6eaf0;
          border-radius: 24px;
          padding: 30px 28px;
          position: relative;
          box-shadow: 0 1px 2px rgba(16,22,32,.05), 0 10px 28px -10px rgba(16,22,32,.09);
          transition: transform .28s cubic-bezier(.32,.72,0,1),
                      box-shadow .28s cubic-bezier(.32,.72,0,1),
                      border-color .28s cubic-bezier(.32,.72,0,1);
        }
        .plan:hover {
          transform: translateY(-4px);
          border-color: #bfe6d8;
          box-shadow: 0 2px 4px rgba(16,22,32,.06), 0 26px 54px -14px rgba(18,184,134,.22);
        }
        .plan-destacado {
          border: 2px solid #12b886;
          transform: translateY(-12px);
          box-shadow: 0 28px 66px -16px rgba(18,184,134,.30);
        }
        .plan-destacado:hover { transform: translateY(-16px); }
        .plan-cinta {
          position: absolute;
          top: -13px; left: 50%; transform: translateX(-50%);
          background: #12b886; color: #06251c;
          font-size: 12.5px; font-weight: 700;
          padding: 5px 16px; border-radius: 999px;
          white-space: nowrap;
          box-shadow: 0 6px 16px rgba(18,184,134,.34);
        }
        .plan-cupos {
          display: flex; flex-wrap: wrap; gap: 7px;
          margin: 20px 0 22px;
          padding: 15px 0;
          border-top: 1px solid #eef1f5;
          border-bottom: 1px solid #eef1f5;
        }
        .plan-cupo {
          font-size: 13px; font-weight: 600; color: #0e8371;
          background: #eef9f4; border: 1px solid #d3efe4;
          padding: 4px 11px; border-radius: 999px;
        }
        @media (max-width: 720px) {
          .plan-destacado, .plan-destacado:hover, .plan:hover { transform: none; }
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
          footer { padding-bottom: 88px; }
        }

        /* La cinta va DUPLICADA y se desplaza exactamente el 50%: al terminar,
           el primer clon está donde estaba el original y el salto no se ve. */
        @keyframes correr-cinta {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .cinta-rubros { animation: correr-cinta 48s linear infinite; }
        .cinta-rubros:hover { animation-play-state: paused; }

        /* El hero no es mitad y mitad: el texto pide más aire que el mockup, y
           con 50/50 el título de 68px partía «Los que» solo en el primer
           renglón. Debajo de 980 se apilan. */
        .hero-grilla {
          display: grid;
          grid-template-columns: 1.08fr 0.92fr;
          align-items: center;
          gap: clamp(40px,5vw,72px);
        }
        @media (max-width: 980px) {
          .hero-grilla { grid-template-columns: 1fr; }
        }

        /* Trama de puntos del hero: da textura sin pesar un byte de imagen. */
        .trama {
          background-image: radial-gradient(rgba(255,255,255,.075) 1px, transparent 1px);
          background-size: 26px 26px;
          mask-image: radial-gradient(120% 90% at 50% 0%, #000 25%, transparent 78%);
          -webkit-mask-image: radial-gradient(120% 90% at 50% 0%, #000 25%, transparent 78%);
        }

        .visor-panel { transition: transform .35s ease, box-shadow .35s ease; }
        .visor-panel:hover {
          transform: scale(1.01);
          box-shadow: 0 40px 90px -24px rgba(16,22,32,0.30);
        }
        .visor-img { transition: opacity .45s ease; }
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
          background: rgba(255,255,255,0.94);
          box-shadow: 0 4px 16px rgba(16,22,32,0.2);
          color: #12161f; font-size: 24px; line-height: 1; font-weight: 700;
          opacity: 0;
          transition: opacity .25s ease;
        }
        .visor-panel:hover .visor-flecha { opacity: 1; }
        @media (hover: none) { .visor-flecha { opacity: .85; } }
        .visor-lado:focus-visible .visor-flecha { opacity: 1; outline: 2px solid #12b886; }

        @media (prefers-reduced-motion: reduce) {
          .cinta-rubros { animation: none !important; }
          .plan, .plan:hover, .plan-destacado, .plan-destacado:hover { transform: none !important; transition: none !important; }
          .visor-panel, .visor-img, .visor-flecha { transition: none !important; }
          .visor-panel:hover { transform: none !important; }
        }
      `}</style>

      <div style={{ fontFamily: font.texto, color: "#12161f", background: "#fff", minWidth: 320, overflowX: "hidden" }}>
        {/* ══ NAV ══ */}
        <header className={compacta ? "nav-fija nav-clara" : "nav-fija"}>
          <nav className="nav-barra" style={{ gap: 16, padding: `14px ${LADOS}`, ...caja }}>
            <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
              {/* El archivo del logo trae fondo blanco horneado. Redondeado
                  lee como el ícono de una app; en cuadrado, sobre el hero
                  oscuro, parecía una imagen mal recortada. */}
              <img src={logo.src} onError={logo.alFallar} alt="Turnos360" style={{ width: 42, height: 42, objectFit: "contain", borderRadius: 11 }} />
              <span className="nav-marca" style={{ fontFamily: font.marca, fontWeight: 700, fontSize: 20 }}>
                Turnos<span style={{ color: "#12b886" }}>360</span>
              </span>
            </Link>
            <div className="nav-links">
              <a href="#funciones" className="nav-link">Funciones</a>
              <a href="#como-funciona" className="nav-link">Cómo funciona</a>
              <a href="#rubros" className="nav-link">Rubros</a>
              <a href="#precios" className="nav-link">Precios</a>
              <a href="#faq" className="nav-link">Preguntas</a>
            </div>
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

        {/* ══ HERO ══
            Arranca en negativo para meterse DEBAJO de la barra: la barra es
            sticky y transparente, así que el degradé tiene que empezar arriba
            de todo o se ve una franja blanca sobre el oscuro. */}
        <section
          style={{
            position: "relative",
            marginTop: -71,
            paddingTop: 71,
            background:
              "radial-gradient(1000px 560px at 76% 12%, rgba(18,184,134,0.20), transparent 62%)," +
              "radial-gradient(760px 520px at 8% 4%, rgba(56,102,175,0.22), transparent 58%)," +
              "linear-gradient(180deg, #080d18 0%, #0a1020 68%, #0c1426 100%)",
            color: "#fff",
            overflow: "hidden",
          }}
        >
          <div aria-hidden className="trama" style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />

          <div
            className="hero-grilla"
            style={{
              position: "relative",
              padding: `clamp(44px,6vw,84px) ${LADOS} clamp(40px,5vw,64px)`,
              ...caja,
            }}
          >
            <div>
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: EASE }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 9,
                  background: "rgba(18,184,134,0.12)",
                  border: "1px solid rgba(18,184,134,0.30)",
                  color: "#5ee7bd",
                  fontSize: 13,
                  fontWeight: 700,
                  padding: "7px 15px",
                  borderRadius: 999,
                  marginBottom: 24,
                }}
              >
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#12b886" }} />
                Hecho en Argentina para negocios que trabajan con turnos
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.65, ease: EASE, delay: 0.06 }}
                style={{
                  fontFamily: font.titulo,
                  fontWeight: 700,
                  fontSize: "clamp(38px,5.4vw,68px)",
                  lineHeight: 1.03,
                  letterSpacing: "-0.028em",
                  margin: "0 0 22px",
                  textWrap: "balance" as React.CSSProperties["textWrap"],
                }}
              >
                Los que reservan y no vienen{" "}
                <span
                  style={{
                    background: "linear-gradient(100deg, #12b886 0%, #6ee7c4 55%, #a7f3d0 100%)",
                    WebkitBackgroundClip: "text",
                    backgroundClip: "text",
                    color: "transparent",
                  }}
                >
                  te están costando plata.
                </span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.65, ease: EASE, delay: 0.14 }}
                style={{
                  fontSize: "clamp(16.5px,1.5vw,20px)",
                  lineHeight: 1.62,
                  color: "#9fadc2",
                  margin: "0 0 32px",
                  maxWidth: 540,
                  textWrap: "pretty" as React.CSSProperties["textWrap"],
                }}
              >
                Tus clientes reservan solos, pagan la seña con Mercado Pago y reciben
                recordatorios automáticos. Vos atendés; el sistema agenda, cobra y te
                muestra los números.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.65, ease: EASE, delay: 0.2 }}
                style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}
              >
                <Link href="/registro" className="cta cta-fuerte">
                  Crear mi cuenta gratis
                  <span aria-hidden className="cta-flecha">→</span>
                </Link>
                <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="cta cta-fantasma">
                  <span aria-hidden style={{ width: 9, height: 9, borderRadius: "50%", background: "#8bc540", flexShrink: 0 }} />
                  Que me lo configuren
                </a>
              </motion.div>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, ease: EASE, delay: 0.32 }}
                style={{ fontSize: 13.5, color: "#6b7a91", margin: "20px 0 0", lineHeight: 1.6 }}
              >
                {DIAS_PRUEBA} días gratis · No pedimos tarjeta · Cancelás cuando quieras.
                <br />
                <span style={{ color: "#8b9ab0" }}>
                  ¿Preferís no cargar nada vos? Te damos de alta el negocio por WhatsApp, gratis.
                </span>
              </motion.p>
            </div>

            <div style={{ display: "flex", justifyContent: "center" }}>
              <MockupReserva />
            </div>
          </div>

          {/* Integraciones, todavía sobre el oscuro: cierran la primera pantalla
              en vez de abrir la segunda. */}
          <div style={{ position: "relative", padding: `0 ${LADOS} clamp(40px,5vw,64px)`, ...caja }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "center",
                gap: "clamp(22px,4vw,54px)",
                borderTop: "1px solid rgba(255,255,255,0.09)",
                paddingTop: 34,
              }}
            >
              <span style={{ fontSize: 12.5, fontWeight: 700, color: "#6b7a91", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Se integra con
              </span>
              {/* Cada logo en su pastilla clara: son marcas con su propio color
                  y sobre el navy el de Mercado Pago —azul sobre azul— casi no
                  se veía. Monocromarlos en blanco lo arreglaba, pero acá el
                  logo de Mercado Pago es parte del argumento de venta y tiene
                  que leerse como Mercado Pago. */}
              {[
                { src: "/img/mercado-pago.png", alt: "Mercado Pago", h: 26 },
                { src: "/img/whatsapp.png", alt: "WhatsApp", h: 20 },
                { src: "/img/google-calendar.png", alt: "Google Calendar", h: 22 },
                { src: "/img/google-maps.png", alt: "Google Maps", h: 20 },
              ].map((i) => (
                <span
                  key={i.alt}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    background: "rgba(255,255,255,0.94)",
                    border: "1px solid rgba(255,255,255,0.14)",
                    borderRadius: 12,
                    padding: "10px 16px",
                  }}
                >
                  <img src={i.src} alt={i.alt} style={{ height: i.h, display: "block" }} />
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ══ PROBLEMA ══ */}
        <section style={{ background: "#f7f9fb", padding: `clamp(64px,8vw,104px) ${LADOS}` }}>
          <div style={caja}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", alignItems: "center", gap: "clamp(28px,4vw,56px)", marginBottom: 48 }}>
              <Titulo
                h2="Si manejás el negocio con libreta y WhatsApp, esto te suena."
                bajada="Cuatro cosas que le pasan a casi todos los dueños del rubro."
              />
              <Revelar demora={0.08}>
                <img
                  src="/img/duena-notebook.jpg"
                  alt="Dueña revisando sus números en Turnos360"
                  style={{ width: "100%", maxWidth: 480, borderRadius: 24, objectFit: "cover", aspectRatio: "3 / 2", boxShadow: "0 28px 60px -18px rgba(16,22,32,0.28)", marginLeft: "auto", display: "block" }}
                />
              </Revelar>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(248px, 1fr))", gap: 18 }}>
              {pains.map((p, i) => (
                <Revelar key={p.num} demora={i * 0.07}>
                  <div style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 20, padding: 26, height: "100%" }}>
                    <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 28, color: "#12b886", marginBottom: 14, letterSpacing: "-0.02em" }}>{p.num}</div>
                    <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>{p.title}</div>
                    <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.6 }}>{p.body}</div>
                  </div>
                </Revelar>
              ))}
            </div>
          </div>
        </section>

        {/* ══ FUNCIONALIDADES ══ */}
        <section id="funciones" style={{ padding: `clamp(64px,8vw,112px) ${LADOS}`, ...caja }}>
          <Titulo
            rotulo="Lo que la agenda común no hace"
            color="#b45309"
            fondo="#fff7ec"
            h2="Anotar turnos lo hace cualquiera. Esto es lo que te diferencia."
            bajada="Turnos360 te dice cuánto ganaste, quién te lo generó y qué clientes dejaron de venir."
          />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))", gap: 18 }}>
            {features.map((f, i) => (
              <Revelar key={f.title} demora={(i % 4) * 0.07}>
                <div className="tarjeta-hover" style={{ border: "1px solid #e9ecf1", borderRadius: 20, padding: 28, background: "#fff", height: "100%" }}>
                  <div style={{ width: 44, height: 44, borderRadius: 13, background: "#eef9f4", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, marginBottom: 18, color: "#0e8371", fontWeight: 700, fontFamily: font.titulo }}>
                    {f.glyph}
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 17.5, marginBottom: 9 }}>{f.title}</div>
                  <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.6 }}>{f.body}</div>
                </div>
              </Revelar>
            ))}
          </div>
        </section>

        {/* ══ PANEL ══ */}
        <section style={{ background: "#f7f9fb", padding: `clamp(64px,8vw,112px) ${LADOS}` }}>
          <div style={{ ...caja, textAlign: "center" }}>
            <Titulo
              centrado
              h2="Todo el negocio en un solo lugar"
              bajada="Agenda, clientes, caja y estadísticas desde el celular o la compu. Estas son pantallas reales del sistema."
            />
            <Revelar>
              <div style={{ display: "inline-flex", background: "#fff", border: "1px solid #e9ecf1", borderRadius: 999, padding: 5, gap: 4, marginBottom: 30, flexWrap: "wrap", justifyContent: "center" }}>
                {shots.map((s, i) => (
                  <button
                    key={s.label}
                    onClick={() => setTab(i)}
                    style={{
                      position: "relative",
                      border: "none",
                      cursor: "pointer",
                      fontFamily: font.texto,
                      fontSize: 14.5,
                      fontWeight: 700,
                      padding: "10px 24px",
                      borderRadius: 999,
                      background: "transparent",
                      color: i === tab ? "#06251c" : "#5d6578",
                    }}
                  >
                    {i === tab && (
                      <motion.span
                        layoutId="pestana-panel"
                        transition={{ type: "spring", stiffness: 420, damping: 34 }}
                        style={{ position: "absolute", inset: 0, borderRadius: 999, background: "#12b886", zIndex: 0 }}
                      />
                    )}
                    <span style={{ position: "relative", zIndex: 1 }}>{s.label}</span>
                  </button>
                ))}
              </div>
            </Revelar>

            <Revelar demora={0.06}>
              <div
                className="visor-panel"
                style={{ position: "relative", background: "#fff", border: "1px solid #e9ecf1", borderRadius: 22, padding: "clamp(8px,1.5vw,16px)", boxShadow: "0 32px 76px -22px rgba(16,22,32,0.22)", overflow: "hidden", maxWidth: 1040, margin: "0 auto" }}
              >
                {/* Las cuatro capturas APILADAS y cruzadas por opacidad: cambiando
                    el src, el navegador descarta la vieja antes de tener la nueva
                    y la primera vez que se toca cada pestaña hay un parpadeo. */}
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
                        borderRadius: 14,
                        opacity: i === tab ? 1 : 0,
                        ...(i === 0 ? { position: "relative" } : { position: "absolute", inset: 0, height: "100%" }),
                      }}
                    />
                  ))}
                </div>

                <button type="button" aria-label="Pantalla anterior" onClick={() => setTab((t) => (t - 1 + shots.length) % shots.length)} className="visor-lado visor-lado-izq">
                  <span className="visor-flecha" aria-hidden>‹</span>
                </button>
                <button type="button" aria-label="Pantalla siguiente" onClick={() => setTab((t) => (t + 1) % shots.length)} className="visor-lado visor-lado-der">
                  <span className="visor-flecha" aria-hidden>›</span>
                </button>
              </div>
            </Revelar>

            <AnimatePresence mode="wait">
              <motion.p
                key={shots[tab].label}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.28, ease: EASE }}
                style={{ color: "#8b93a7", fontSize: 14.5, margin: "22px auto 0", maxWidth: 620 }}
              >
                {shots[tab].caption}
              </motion.p>
            </AnimatePresence>
          </div>
        </section>

        {/* ══ PÁGINA DE RESERVAS ══ */}
        <section style={{ padding: `clamp(64px,8vw,112px) ${LADOS}`, ...caja }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(310px, 1fr))", alignItems: "center", gap: "clamp(40px,6vw,88px)" }}>
            <div>
              <Titulo
                rotulo="Tu página, no la nuestra"
                h2="Cada negocio con su propia página de reservas"
                bajada="Tu portada, tu logo, tu color, tu gente y tus precios. El cliente entra, elige y paga la seña —incluso a las dos de la mañana— sin bajarse ninguna app."
              />
              <div style={{ display: "grid", gap: 12, marginBottom: 32 }}>
                {canales.map((c, i) => (
                  <Revelar key={c.label} demora={i * 0.06}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span style={{ width: 38, height: 38, borderRadius: 11, background: "#f3f5f8", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <img src={c.icono} alt="" style={{ width: 20, height: 20, objectFit: "contain" }} />
                      </span>
                      <span style={{ fontSize: 15.5, color: "#3a4356", fontWeight: 500 }}>{c.label}</span>
                    </div>
                  </Revelar>
                ))}
              </div>
              <Revelar demora={0.28}>
                <div style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "#f7f9fb", border: "1px solid #e9ecf1", borderRadius: 999, padding: "10px 18px", fontWeight: 700, fontSize: 15 }}>
                  turnos360.com.ar/<span style={{ color: "#0e8371" }}>elfaro</span>
                </div>
              </Revelar>
            </div>

            <Revelar demora={0.1} y={30}>
              <TelefonoLocal />
            </Revelar>
          </div>
        </section>

        {/* ══ MULTISUCURSAL ══ */}
        <section id="sucursales" style={{ background: "#f7f9fb", padding: `clamp(64px,8vw,112px) ${LADOS}` }}>
          <div style={{ ...caja, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", alignItems: "center", gap: "clamp(36px,5vw,72px)" }}>
            <div>
              <Titulo
                rotulo="Para los que tienen más de un local"
                color="#4338ca"
                fondo="#eef2ff"
                h2="Dos locales, dos cajas, un solo panel."
                bajada="Cuando abrís el segundo local, la mayoría de los sistemas te obliga a pagar dos cuentas y a sumar los números a mano. Acá cada sucursal tiene su caja, su equipo y su agenda, y vos las ves todas juntas."
              />
              <div style={{ display: "grid", gap: 20 }}>
                {locales.map((l, i) => (
                  <Revelar key={l.title} demora={i * 0.07}>
                    <div style={{ display: "flex", gap: 13 }}>
                      <span style={{ color: "#12b886", fontWeight: 700, fontSize: 17, lineHeight: 1.45, flexShrink: 0 }}>✓</span>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 16.5, marginBottom: 5 }}>{l.title}</div>
                        <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.6 }}>{l.body}</div>
                      </div>
                    </div>
                  </Revelar>
                ))}
              </div>
            </div>

            {/* Números de ejemplo, y la etiqueta lo dice: la landing no puede
                insinuar que son reales. */}
            <Revelar demora={0.12} y={28}>
              <div style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 26, boxShadow: "0 32px 70px -22px rgba(16,22,32,0.20)", padding: "clamp(22px,3vw,30px)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
                  <span style={{ fontWeight: 700, fontSize: 15.5 }}>Comparativa del mes</span>
                  <span style={{ fontSize: 12, color: "#8b93a7", background: "#f3f5f8", borderRadius: 999, padding: "4px 10px" }}>Ejemplo</span>
                </div>
                {[
                  { nombre: "El Faro · Centro", monto: "$1.840.000", turnos: "212 turnos", barra: 100, color: "#12b886" },
                  { nombre: "El Faro · Godoy Cruz", monto: "$1.115.000", turnos: "141 turnos", barra: 61, color: "#8bc540" },
                ].map((l, i) => (
                  <div key={l.nombre} style={{ marginBottom: 22 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 9, gap: 12 }}>
                      <span style={{ fontWeight: 700, fontSize: 14.5 }}>{l.nombre}</span>
                      <span style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 18 }}>{l.monto}</span>
                    </div>
                    <div style={{ height: 10, borderRadius: 999, background: "#f0f2f6", overflow: "hidden" }}>
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: `${l.barra}%` }}
                        viewport={{ once: true, amount: 0.6 }}
                        transition={{ duration: 0.9, ease: EASE, delay: 0.2 + i * 0.12 }}
                        style={{ height: "100%", borderRadius: 999, background: l.color }}
                      />
                    </div>
                    <div style={{ fontSize: 12.5, color: "#8b93a7", marginTop: 7 }}>{l.turnos}</div>
                  </div>
                ))}
                <div style={{ borderTop: "1px solid #eef1f5", paddingTop: 17, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 13.5, color: "#5d6578" }}>Caja abierta hoy</span>
                  <span style={{ fontSize: 13.5, fontWeight: 700 }}>2 de 3 locales</span>
                </div>
              </div>
              <p style={{ fontSize: 13, color: "#8b93a7", margin: "14px 4px 0", textAlign: "center" }}>
                Incluido en el plan, sin costo por local extra.
              </p>
            </Revelar>
          </div>
        </section>

        {/* ══ CÓMO FUNCIONA ══ */}
        <section
          id="como-funciona"
          style={{
            background:
              "radial-gradient(800px 420px at 85% 100%, rgba(139,197,64,0.14), transparent 60%)," +
              "radial-gradient(760px 420px at 10% 0%, rgba(18,184,134,0.14), transparent 60%)," +
              "#0a1020",
            padding: `clamp(64px,8vw,112px) ${LADOS}`,
          }}
        >
          <div style={caja}>
            <Titulo
              oscuro
              h2="Andando en la misma tarde"
              bajada="Te das de alta solo, en dos minutos y sin tarjeta. Y si preferís que lo carguemos nosotros, también: escribinos y lo dejamos listo con vos."
            />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(268px, 1fr))", gap: 20 }}>
              {steps.map((s, i) => (
                <Revelar key={s.num} demora={i * 0.09}>
                  <div style={{ border: "1px solid rgba(255,255,255,0.11)", borderRadius: 22, padding: 30, background: "rgba(255,255,255,0.035)", height: "100%" }}>
                    <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 13, color: "#8bc540", letterSpacing: "0.14em", marginBottom: 16 }}>
                      PASO {s.num}
                    </div>
                    <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 22, color: "#fff", marginBottom: 11, letterSpacing: "-0.01em" }}>
                      {s.title}
                    </div>
                    <div style={{ color: "#a6b2c4", fontSize: 15, lineHeight: 1.62 }}>{s.body}</div>
                  </div>
                </Revelar>
              ))}
            </div>
            <Revelar demora={0.3}>
              <div style={{ marginTop: 36, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16, border: "1px solid rgba(139,197,64,0.32)", background: "rgba(139,197,64,0.08)", borderRadius: 18, padding: "20px 24px" }}>
                <span style={{ background: "#8bc540", color: "#0a1020", fontWeight: 700, fontSize: 12, padding: "5px 12px", borderRadius: 999, letterSpacing: "0.06em" }}>PILOTO</span>
                <span style={{ color: "#dfe6d4", fontSize: 15 }}>
                  La configuración inicial se bonifica para los primeros negocios, a cambio de tu testimonio real.
                </span>
              </div>
            </Revelar>
          </div>
        </section>

        {/* ══ RUBROS ══ */}
        <section id="rubros" style={{ padding: `clamp(64px,8vw,112px) ${LADOS} clamp(48px,6vw,80px)`, ...caja }}>
          <Titulo
            centrado
            h2="Hecho para tu rubro"
            bajada="Servicios con duración, profesional y precio. Si trabajás con turnos, Turnos360 es para vos."
          />
          <Revelar>
            <div
              style={{
                overflow: "hidden",
                WebkitMaskImage: "linear-gradient(90deg, transparent 0%, #000 6%, #000 94%, transparent 100%)",
                maskImage: "linear-gradient(90deg, transparent 0%, #000 6%, #000 94%, transparent 100%)",
              }}
            >
              <div className="cinta-rubros" style={{ display: "flex", gap: 18, width: "max-content" }}>
                {[...rubros, ...rubros].map((r, i) => (
                  <div
                    key={`${r.label}-${i}`}
                    aria-hidden={i >= rubros.length}
                    style={{ width: 200, flexShrink: 0, border: "1px solid #e9ecf1", borderRadius: 20, overflow: "hidden", background: "#fff", textAlign: "left" }}
                  >
                    <FotoRubro src={r.img} emoji={r.emoji} label={r.label} />
                    <div style={{ padding: "15px 17px", fontWeight: 700, fontSize: 15.5 }}>{r.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </Revelar>
        </section>

        {/* ══ PRECIOS ══ */}
        <section id="precios" style={{ background: "#f7f9fb", padding: `clamp(64px,8vw,112px) ${LADOS}`, position: "relative", overflow: "hidden" }}>
          {/* Dos halos diluidos detrás de las tarjetas: sin esto la sección es
              un rectángulo gris y las tres flotan sin apoyarse en nada. */}
          <div
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              background:
                "radial-gradient(680px 340px at 20% 0%, rgba(18,184,134,0.11), transparent 62%)," +
                "radial-gradient(600px 320px at 82% 12%, rgba(139,197,64,0.11), transparent 60%)",
              pointerEvents: "none",
            }}
          />
          <div style={{ ...caja, position: "relative" }}>
            <Titulo
              centrado
              h2="Elegí por el tamaño de tu equipo"
              bajada="Los tres traen la agenda completa, tu página de reservas y las señas. Lo que cambia es cuánta gente entra y qué más podés vender."
            />

            <div className="grilla-planes">
              {planes.map((p, i) => (
                <Revelar key={p.codigo} demora={i * 0.09} style={{ display: "flex" }}>
                  <div className={`plan ${p.destacado ? "plan-destacado" : ""}`} style={{ width: "100%" }}>
                    {p.destacado && <div className="plan-cinta">El que más eligen</div>}

                    <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 22, marginBottom: 5 }}>{p.nombre}</div>
                    <p style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.5, margin: "0 0 20px", minHeight: 44 }}>{p.paraQuien}</p>

                    <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
                      {PROMO_ACTIVA && p.codigo === "inicial" && (
                        <span style={{ color: "#9aa3b2", fontSize: 19, fontWeight: 600, textDecoration: "line-through" }}>
                          {PRECIO_NORMAL_TEXTO}
                        </span>
                      )}
                      <span style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: "clamp(34px,3.8vw,46px)", letterSpacing: "-0.03em" }}>
                        {enPesos(p.precio)}
                      </span>
                      <span style={{ color: "#5d6578", fontSize: 16, fontWeight: 500 }}>/ mes</span>
                    </div>
                    {PROMO_ACTIVA && p.codigo === "inicial" && (
                      <div style={{ display: "inline-flex", background: "#fff4e0", color: "#9a6212", fontWeight: 700, fontSize: 12, padding: "4px 11px", borderRadius: 999, marginTop: 8 }}>
                        {PROMO_ETIQUETA}
                      </div>
                    )}

                    <div className="plan-cupos">
                      {p.cupos.map((c) => (
                        <div key={c} className="plan-cupo">{c}</div>
                      ))}
                    </div>

                    <p style={{ color: "#8b93a7", fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 13px" }}>
                      {p.tituloLista}
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: 11, marginBottom: 28, flex: 1 }}>
                      {p.incluye.map((it) => (
                        <div key={it} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 14.5, lineHeight: 1.45, color: "#2a3140" }}>
                          <span aria-hidden style={{ color: "#12b886", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>✓</span>
                          {it}
                        </div>
                      ))}
                    </div>

                    <Link href="/registro" className={`cta ${p.destacado ? "cta-fuerte" : "cta-suave"}`} style={{ width: "100%" }}>
                      Probalo {DIAS_PRUEBA} días gratis
                      <span aria-hidden className="cta-flecha">→</span>
                    </Link>
                  </div>
                </Revelar>
              ))}
            </div>

            {/* Enterprise fuera de la fila: sin precio que mostrar, la tarjeta
                vertical quedaba con un hueco enorme donde va el número. */}
            <Revelar demora={0.1}>
              <div className="plan-enterprise">
                <div>
                  <div style={{ fontFamily: font.titulo, fontWeight: 700, fontSize: 22, marginBottom: 5 }}>{ENTERPRISE.nombre}</div>
                  <p style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.5, margin: "0 0 14px" }}>{ENTERPRISE.paraQuien}</p>
                  <div className="plan-cupos" style={{ marginBottom: 18 }}>
                    {ENTERPRISE.cupos.map((c) => (
                      <div key={c} className="plan-cupo">{c}</div>
                    ))}
                  </div>
                  <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="cta cta-suave">
                    Hablemos
                    <span aria-hidden className="cta-flecha">→</span>
                  </a>
                </div>
                <div>
                  <p style={{ color: "#8b93a7", fontSize: 12.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 13px" }}>
                    Todo lo de Multi, más:
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
                    {ENTERPRISE.incluye.map((it) => (
                      <div key={it} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 14.5, lineHeight: 1.45, color: "#2a3140" }}>
                        <span aria-hidden style={{ color: "#12b886", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>✓</span>
                        {it}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Revelar>

            <p style={{ color: "#8b93a7", fontSize: 14, textAlign: "center", margin: "30px auto 0", maxWidth: 640, lineHeight: 1.6 }}>
              {DIAS_PRUEBA} días gratis con <b style={{ color: "#5d6578" }}>todo desbloqueado</b>, sin tarjeta.
              Precios en pesos, cancelás cuando quieras. Cambiás de plan cuando te queda chico.{" "}
              <a href={WA_LINK} target="_blank" rel="noopener noreferrer" style={{ color: "#0e8371", fontWeight: 600 }}>
                O que te lo configuremos gratis
              </a>
              .
            </p>
          </div>
        </section>

        {/* ══ GALERÍA ══ */}
        <section style={{ padding: `clamp(56px,7vw,88px) ${LADOS} clamp(48px,6vw,72px)`, ...caja }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 18 }}>
            {fotos.map((f, i) => (
              <Revelar key={f.src} demora={i * 0.08}>
                <div style={{ position: "relative", borderRadius: 24, overflow: "hidden", height: 290 }}>
                  <img src={f.src} alt={f.alt} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                  <div aria-hidden style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, transparent 45%, rgba(8,13,24,0.62) 100%)" }} />
                  <span style={{ position: "absolute", left: 20, bottom: 18, color: "#fff", fontWeight: 700, fontSize: 16 }}>{f.alt}</span>
                </div>
              </Revelar>
            ))}
          </div>
        </section>

        {/* ══ FAQ ══ */}
        <section id="faq" style={{ padding: `0 ${LADOS} clamp(64px,8vw,104px)`, maxWidth: 860, margin: "0 auto" }}>
          <Titulo centrado h2="Preguntas frecuentes" bajada="Lo que todos preguntan antes de arrancar." />
          <div style={{ display: "flex", flexDirection: "column" }}>
            {faqs.map((q, i) => {
              const abierta = faq === i;
              return (
                <Revelar key={q.q} demora={Math.min(i, 4) * 0.05} y={14}>
                  <div style={{ borderBottom: "1px solid #e9ecf1" }}>
                    <button
                      onClick={() => setFaq(abierta ? -1 : i)}
                      aria-expanded={abierta}
                      style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: "20px 4px", fontFamily: font.texto, fontSize: 17, fontWeight: 700, color: "#12161f" }}
                    >
                      {q.q}
                      <motion.span
                        animate={{ rotate: abierta ? 135 : 0 }}
                        transition={{ duration: 0.28, ease: EASE }}
                        style={{ color: "#12b886", fontSize: 24, fontWeight: 300, lineHeight: 1, flexShrink: 0 }}
                      >
                        +
                      </motion.span>
                    </button>
                    <AnimatePresence initial={false}>
                      {abierta && (
                        <motion.div
                          key="cuerpo"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.32, ease: EASE }}
                          style={{ overflow: "hidden" }}
                        >
                          <div style={{ color: "#5d6578", fontSize: 15.5, lineHeight: 1.65, padding: "0 4px 20px", maxWidth: 720 }}>
                            {q.a}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </Revelar>
              );
            })}
          </div>
        </section>

        {/* El CIERRE se sacó a pedido de Leandro: era una segunda tanda de los
            mismos dos botones que ya están arriba y en cada tarjeta de precio.
            Al que llegó hasta acá ya se le ofreció cuatro veces. */}

        {/* ══ FOOTER ══ */}
        <footer style={{ borderTop: "1px solid #eef1f5", padding: `32px ${LADOS}` }}>
          <div style={{ ...caja, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <img src={logo.src} onError={logo.alFallar} alt="Turnos360" style={{ width: 30, height: 30, objectFit: "contain" }} />
              <span style={{ fontFamily: font.marca, fontWeight: 700, fontSize: 16 }}>
                Turnos<span style={{ color: "#12b886" }}>360</span>
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                <Link href="/terminos" style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}>Términos y condiciones</Link>
                <span style={{ color: "#cfd5de", fontSize: 13.5 }}>·</span>
                <Link href="/privacidad" style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}>Política de privacidad</Link>
                <span style={{ color: "#cfd5de", fontSize: 13.5 }}>·</span>
                <a href={WA_LINK} target="_blank" rel="noopener noreferrer" style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}>WhatsApp</a>
                <span style={{ color: "#cfd5de", fontSize: 13.5 }}>·</span>
                <a href={INSTAGRAM} target="_blank" rel="noopener noreferrer" style={{ color: "#5d6578", fontSize: 13.5, textDecoration: "none" }}>Instagram</a>
              </div>
              <span style={{ color: "#8b93a7", fontSize: 13.5, textAlign: "right" }}>
                © {new Date().getFullYear()} Turnos360 · Hecho en Mendoza, Argentina ·{" "}
                <a href={`mailto:${EMAIL_CONTACTO}`} style={{ color: "#5d6578" }}>{EMAIL_CONTACTO}</a>
              </span>
            </div>
          </div>
        </footer>

        {/* En el celular el botón del hero se pierde al segundo scroll y el
            siguiente recién aparece en Precios. */}
        <div className="barra-movil">
          <Link href="/registro" className="cta cta-fuerte" style={{ flex: 1, justifyContent: "center" }}>
            Crear mi cuenta gratis
          </Link>
          <a href={WA_LINK} target="_blank" rel="noopener noreferrer" aria-label="Escribinos por WhatsApp" className="barra-movil-wa">
            <svg viewBox="0 0 24 24" width="23" height="23" fill="#25D366" aria-hidden focusable="false">
              <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.25-.46-2.39-1.47-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.14-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.48s1.06 2.87 1.21 3.07c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.71 2-1.4.25-.69.25-1.28.17-1.4-.07-.13-.27-.2-.57-.35z" />
              <path d="M12.04 2C6.6 2 2.17 6.43 2.17 11.87c0 1.74.46 3.44 1.32 4.94L2.09 22l5.33-1.38a9.83 9.83 0 0 0 4.62 1.17h.01c5.44 0 9.87-4.43 9.87-9.87 0-2.64-1.03-5.12-2.9-6.98A9.8 9.8 0 0 0 12.04 2zm0 1.79c2.16 0 4.19.84 5.72 2.37a8.03 8.03 0 0 1 2.37 5.71c0 4.46-3.63 8.09-8.09 8.09a8.1 8.1 0 0 1-4.12-1.13l-.3-.18-3.06.8.82-3-.19-.31a8.04 8.04 0 0 1-1.24-4.31c0-4.46 3.63-8.08 8.09-8.08z" />
            </svg>
          </a>
        </div>
      </div>
    </>
  );
}
