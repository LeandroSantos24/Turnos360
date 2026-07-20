"use client";
// Landing Turnos360 — reemplaza app/page.tsx
// Copiá las imágenes a /public/img/ con estos nombres (ver README-integracion.md)
import { useState } from "react";
import Link from "next/link";

const WA_NUMBER = "5492610000000"; // ← tu número real
const WA_LINK = `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent("Hola! Quiero una demo de Turnos360 para mi negocio.")}`;

const font = { sora: "'Sora', sans-serif", dm: "'DM Sans', sans-serif" };

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
];

const shots = [
  { label: "Inicio", src: "/img/panel-inicio.png", caption: "Resumen del mes: turnos, ingresos previstos y tasa de ausencias de un vistazo." },
  { label: "Estadísticas", src: "/img/panel-estadisticas.png", caption: "Facturación real, comisiones y ticket promedio, filtrado por profesional." },
  { label: "Campañas", src: "/img/panel-campanas.png", caption: "Recordatorios y campañas automáticas: se prenden una vez y andan solas." },
];

const steps = [
  { num: "01", title: "Nos contás de tu negocio", body: "Por WhatsApp: tus servicios, precios, horarios y quiénes trabajan con vos. Nada técnico." },
  { num: "02", title: "Te lo dejamos andando", body: "Cargamos todo, conectamos Mercado Pago y te entregamos tu página de reservas lista, con tu logo y tus colores." },
  { num: "03", title: "Tus clientes reservan solos", body: "Compartís tu link, el sistema cobra la seña, manda recordatorios y vos ves los números cada noche." },
];

const rubros = [
  { emoji: "💈", label: "Barberías" },
  { emoji: "✂️", label: "Peluquerías" },
  { emoji: "💅", label: "Salones de uñas" },
  { emoji: "✨", label: "Centros de estética" },
  { emoji: "🧖", label: "Spa" },
  { emoji: "🥗", label: "Consultorios de nutrición" },
];

const planItems = [
  "Agenda con carriles paralelos",
  "Página de reservas propia (tu link y tu QR)",
  "Seña online con Mercado Pago",
  "Recordatorios automáticos anti-ausencias",
  "Caja con apertura, cierre y arqueo",
  "Comisiones por profesional",
  "Membresías, gift cards y cupones",
  "Estadísticas y ficha de cada cliente",
  "Soporte por WhatsApp",
];

const fotos = [
  { src: "/img/foto-barberia.jpg", alt: "Barbería" },
  { src: "/img/foto-salon.jpg", alt: "Salón de uñas" },
  { src: "/img/foto-estetica.jpg", alt: "Spa / estética" },
];

const faqs = [
  { q: "¿Tengo que saber de computación?", a: "No. Nosotros damos de alta tu negocio, cargamos tus servicios, tu equipo y tu página. Vos entrás y ya está andando. Si algo no se entiende, nos escribís por WhatsApp y lo resolvemos." },
  { q: "¿Mis clientes tienen que descargar una app?", a: "No. Reservan desde el link de tu página, en el navegador del celular. Compartís ese link en tu Instagram o tu estado de WhatsApp y listo." },
  { q: "¿Me cobran comisión por cada turno?", a: "Cero. Pagás la cuota mensual y nada más. Si cobrás la seña con Mercado Pago, la plata va directo a tu cuenta y la única comisión es la de Mercado Pago, que no tocamos." },
  { q: "¿Sirve si tengo varios barberos trabajando a la vez?", a: "Es para lo que está hecho. La agenda muestra carriles paralelos: mientras uno corta, otro puede estar haciendo color y otro barba, sin que los turnos se pisen. Y cada uno tiene su comisión calculada." },
  { q: "¿Qué pasa con los que reservan y no vienen?", a: "Dos frenos: el cobro anticipado con Mercado Pago —elegís si pedís una seña o el total— y los recordatorios automáticos por email 24 horas y 2 horas antes." },
  { q: "¿Puedo probarlo antes de pagar?", a: "Sí. Te hacemos una demo con tu negocio cargado de verdad — tus servicios, tu equipo, tu página — para que veas cómo te quedaría. Sin compromiso." },
];

function Monogram({ size = 30, invert = false }: { size?: number; invert?: boolean }) {
  return (
    <div style={{ width: size, height: size, borderRadius: "50%", background: invert ? "#f5e9c9" : "#1c222c", color: invert ? "#1c222c" : "#f5e9c9", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: font.sora, fontWeight: 700, fontSize: size * 0.37, flexShrink: 0 }}>EF</div>
  );
}

export default function Page() {
  const [tab, setTab] = useState(0);
  const [faq, setFaq] = useState(-1);

  return (
    <div style={{ fontFamily: font.dm, color: "#1c222c", background: "#fff", minWidth: 320, overflowX: "hidden" }}>
      {/* NAV */}
      <nav style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "14px clamp(16px,5vw,64px)", borderBottom: "1px solid #eef1f5", position: "sticky", top: 0, background: "rgba(255,255,255,0.94)", backdropFilter: "blur(8px)", zIndex: 50 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src="/img/logo.png" alt="Turnos360" style={{ width: 38, height: 38, objectFit: "contain" }} />
          <span style={{ fontFamily: font.sora, fontWeight: 700, fontSize: 20 }}>Turnos<span style={{ color: "#12b886" }}>360</span></span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <a href="#funciones" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Funciones</a>
          <a href="#como-funciona" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Cómo funciona</a>
          <a href="#rubros" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Rubros</a>
          <a href="#precios" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Precios</a>
          <a href="#faq" style={{ color: "#5d6578", fontSize: 15, fontWeight: 500, textDecoration: "none" }}>Preguntas</a>
        </div>
        <a href={WA_LINK} target="_blank" style={{ background: "#12b886", color: "#fff", fontWeight: 700, fontSize: 15, padding: "10px 20px", borderRadius: 999, whiteSpace: "nowrap", textDecoration: "none" }}>Pedí una demo</a>
      </nav>

      {/* HERO */}
      <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(32px,5vw,64px)", padding: "clamp(48px,8vw,96px) clamp(16px,5vw,64px) clamp(40px,6vw,72px)", maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ flex: "1 1 420px", minWidth: 300 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "#eef9f4", color: "#0e8371", fontSize: 13, fontWeight: 700, padding: "6px 14px", borderRadius: 999, marginBottom: 20 }}>Hecho para barberías, peluquerías y salones de Argentina</div>
          <h1 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(34px,5vw,54px)", lineHeight: 1.08, margin: "0 0 20px" }}>Los que reservan y no vienen te están costando plata.</h1>
          <p style={{ fontSize: "clamp(16px,2vw,19px)", lineHeight: 1.6, color: "#5d6578", margin: "0 0 28px", maxWidth: 520, textWrap: "pretty" as any }}>Con Turnos360 tus clientes reservan solos, pagan la seña con Mercado Pago y reciben recordatorios por WhatsApp. Vos atendés; el sistema agenda, cobra y te muestra los números.</p>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 14 }}>
            <a href={WA_LINK} target="_blank" style={{ display: "flex", alignItems: "center", gap: 10, background: "#12b886", color: "#fff", fontWeight: 700, fontSize: 17, padding: "15px 28px", borderRadius: 999, boxShadow: "0 8px 24px rgba(18,184,134,0.28)", textDecoration: "none" }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#8bc540" }} />
              Hablemos por WhatsApp
            </a>
            <a href="#como-funciona" style={{ color: "#1c222c", fontWeight: 700, fontSize: 16, padding: "15px 8px", textDecoration: "none" }}>Ver cómo funciona ↓</a>
          </div>
          <p style={{ fontSize: 13, color: "#8b93a7", margin: "18px 0 0" }}>Sin autoservicio: te lo configuramos nosotros y te lo entregamos andando.</p>
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
      </header>

      {/* INTEGRACIONES */}
      <section style={{ padding: "8px clamp(16px,5vw,64px) 56px", maxWidth: 1200, margin: "0 auto" }}>
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
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(24px,4vw,56px)", marginBottom: 40 }}>
            <div style={{ flex: "1 1 380px", minWidth: 280 }}>
              <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px", maxWidth: 640 }}>Si manejás el negocio con libreta y WhatsApp, esto te suena.</h2>
              <p style={{ color: "#5d6578", fontSize: 17, margin: 0, maxWidth: 560 }}>Cuatro cosas que le pasan a casi todos los dueños del rubro.</p>
            </div>
            <img src="/img/duena-notebook.jpg" alt="Dueña revisando sus números en Turnos360" style={{ flex: "1 1 320px", minWidth: 280, maxWidth: 440, width: "100%", borderRadius: 20, objectFit: "cover", aspectRatio: "3 / 2", boxShadow: "0 20px 48px rgba(28,34,44,0.14)" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {pains.map((p) => (
              <div key={p.num} style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 18, padding: 24 }}>
                <div style={{ fontFamily: font.sora, fontWeight: 700, fontSize: 26, color: "#12b886", marginBottom: 12 }}>{p.num}</div>
                <div style={{ fontWeight: 700, fontSize: 16.5, marginBottom: 8 }}>{p.title}</div>
                <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.55 }}>{p.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FUNCIONALIDADES */}
      <section id="funciones" style={{ padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ display: "inline-flex", background: "#fff7ec", color: "#b45309", fontSize: 13, fontWeight: 700, padding: "6px 14px", borderRadius: 999, marginBottom: 16 }}>Lo que la agenda común no hace</div>
        <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px", maxWidth: 620 }}>Anotar turnos lo hace cualquiera. Esto es lo que te diferencia.</h2>
        <p style={{ color: "#5d6578", fontSize: 17, margin: "0 0 40px", maxWidth: 600 }}>Turnos360 te dice cuánto ganaste, quién te lo generó y qué clientes dejaron de venir.</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          {features.map((f) => (
            <div key={f.title} style={{ border: "1px solid #e9ecf1", borderRadius: 18, padding: 26, background: "#fff" }}>
              <div style={{ width: 42, height: 42, borderRadius: 12, background: "#eef9f4", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 19, marginBottom: 16, color: "#0e8371", fontWeight: 700, fontFamily: font.sora }}>{f.glyph}</div>
              <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>{f.title}</div>
              <div style={{ color: "#5d6578", fontSize: 14.5, lineHeight: 1.55 }}>{f.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PANEL / TABS */}
      <section style={{ background: "#f8f9fb", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>Todo el negocio en un solo lugar</h2>
          <p style={{ color: "#5d6578", fontSize: 17, margin: "0 auto 8px", maxWidth: 560 }}>Agenda, clientes, caja y estadísticas desde el celular o la compu. Estas son pantallas reales del sistema.</p>
          <img src="/img/notebook-mockup.png" alt="Turnos360 en una notebook" style={{ width: "100%", maxWidth: 720, mixBlendMode: "multiply", display: "block", margin: "0 auto 8px" }} />
          <div style={{ display: "inline-flex", background: "#fff", border: "1px solid #e9ecf1", borderRadius: 999, padding: 5, gap: 4, marginBottom: 28, flexWrap: "wrap", justifyContent: "center" }}>
            {shots.map((s, i) => (
              <button key={s.label} onClick={() => setTab(i)} style={{ border: "none", cursor: "pointer", fontFamily: font.dm, fontSize: 14.5, fontWeight: 700, padding: "9px 22px", borderRadius: 999, background: i === tab ? "#12b886" : "transparent", color: i === tab ? "#fff" : "#5d6578" }}>{s.label}</button>
            ))}
          </div>
          <div style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 20, padding: "clamp(8px,1.5vw,16px)", boxShadow: "0 24px 60px rgba(28,34,44,0.10)", overflow: "hidden" }}>
            <img src={shots[tab].src} alt="Panel de Turnos360" style={{ width: "100%", display: "block", borderRadius: 12 }} />
          </div>
          <p style={{ color: "#8b93a7", fontSize: 14, margin: "20px 0 0" }}>{shots[tab].caption}</p>
        </div>
      </section>

      {/* COMPARTIR / REDES */}
      <section style={{ padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "clamp(32px,5vw,72px)" }}>
          <div style={{ flex: "1 1 360px", minWidth: 280 }}>
            <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 16px" }}>Tu página de reservas, donde quieras</h2>
            <p style={{ color: "#5d6578", fontSize: 17, lineHeight: 1.6, margin: "0 0 24px", maxWidth: 480, textWrap: "pretty" as any }}>Cada negocio tiene su propia página con su logo, sus servicios y sus horarios. Ponela en la bio de Instagram, en el estado de WhatsApp o imprimí el QR y pegalo en el espejo del local. El cliente reserva solo, incluso a las 2 de la mañana.</p>
            <a href={WA_LINK} target="_blank" style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "#1c222c", color: "#fff", fontWeight: 700, fontSize: 16, padding: "14px 26px", borderRadius: 999, textDecoration: "none" }}>Quiero mi página</a>
          </div>
          <div style={{ flex: "1 1 380px", minWidth: 300, display: "flex", justifyContent: "center" }}>
            <div style={{ position: "relative", width: "100%", maxWidth: 480, aspectRatio: "1.02" }}>
              <div style={{ position: "absolute", inset: "4% 0 4% 6%", background: "radial-gradient(ellipse at center, #e3f6ee 0%, #eef9f4 70%)", borderRadius: "50%" }} />
              {/* WhatsApp */}
              <div style={{ position: "absolute", top: "8%", right: "6%", width: "52%", background: "#25d366", borderRadius: 20, padding: 16, transform: "rotate(3deg)", boxShadow: "0 16px 40px rgba(28,34,44,0.16)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}><Monogram /><span style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>WhatsApp</span></div>
                  <img src="/img/whatsapp-icon.png" alt="WhatsApp" style={{ width: 28, height: 28, objectFit: "contain" }} />
                </div>
                <div style={{ height: 8, background: "rgba(255,255,255,0.45)", borderRadius: 99, margin: "14px 0 8px", width: "82%" }} />
                <div style={{ height: 8, background: "rgba(255,255,255,0.45)", borderRadius: 99, width: "58%" }} />
              </div>
              {/* QR */}
              <div style={{ position: "absolute", top: "22%", right: "16%", width: "52%", background: "#5d6578", borderRadius: 20, padding: 16, transform: "rotate(-2deg)", boxShadow: "0 16px 40px rgba(28,34,44,0.18)" }}>
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
              <div style={{ position: "absolute", top: "37%", right: "24%", width: "52%", background: "#16181f", borderRadius: 20, padding: 16, transform: "rotate(2deg)", boxShadow: "0 16px 40px rgba(28,34,44,0.22)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}><Monogram invert /><span style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>TikTok</span></div>
                  <img src="/img/tiktok-icon.png" alt="TikTok" style={{ width: 28, height: 28, borderRadius: "50%", objectFit: "cover" }} />
                </div>
                <div style={{ height: 8, background: "rgba(255,255,255,0.3)", borderRadius: 99, margin: "14px 0 8px", width: "80%" }} />
                <div style={{ height: 8, background: "rgba(255,255,255,0.3)", borderRadius: 99, width: "55%" }} />
              </div>
              {/* Instagram */}
              <div style={{ position: "absolute", top: "52%", right: "32%", width: "54%", background: "linear-gradient(135deg, #6228d7 0%, #ee2a7b 55%, #f9ce34 120%)", borderRadius: 20, padding: 18, transform: "rotate(-3deg)", boxShadow: "0 24px 56px rgba(238,42,123,0.35)" }}>
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

      {/* COMO FUNCIONA */}
      <section id="como-funciona" style={{ background: "#1c222c", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px", color: "#fff" }}>Nosotros te lo dejamos andando</h2>
          <p style={{ color: "#8b93a7", fontSize: 17, margin: "0 0 44px", maxWidth: 560 }}>No hay que crear cuentas ni configurar nada solo. El alta la hacemos con vos, paso a paso.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20 }}>
            {steps.map((s) => (
              <div key={s.num} style={{ border: "1px solid rgba(255,255,255,0.12)", borderRadius: 20, padding: 28, background: "rgba(255,255,255,0.04)" }}>
                <div style={{ fontFamily: font.sora, fontWeight: 700, fontSize: 14, color: "#8bc540", letterSpacing: "0.12em", marginBottom: 14 }}>PASO {s.num}</div>
                <div style={{ fontFamily: font.sora, fontWeight: 700, fontSize: 21, color: "#fff", marginBottom: 10 }}>{s.title}</div>
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
      <section id="rubros" style={{ padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)", maxWidth: 1100, margin: "0 auto", textAlign: "center" }}>
        <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>Hecho para tu rubro</h2>
        <p style={{ color: "#5d6578", fontSize: 17, margin: "0 auto 36px", maxWidth: 520 }}>Servicios con duración, profesional y precio. Si trabajás con turnos, Turnos360 es para vos.</p>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 12, maxWidth: 760, margin: "0 auto" }}>
          {rubros.map((r) => (
            <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 10, border: "1px solid #e9ecf1", borderRadius: 999, padding: "12px 24px", fontWeight: 700, fontSize: 15.5, background: "#fff" }}>
              <span style={{ fontSize: 22 }}>{r.emoji}</span>{r.label}
            </div>
          ))}
        </div>
      </section>

      {/* PRECIOS */}
      <section id="precios" style={{ background: "#f8f9fb", padding: "clamp(56px,8vw,96px) clamp(16px,5vw,64px)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", textAlign: "center" }}>
          <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 12px" }}>Un solo plan, todo incluido</h2>
          <p style={{ color: "#5d6578", fontSize: 17, margin: "0 auto 40px", maxWidth: 520 }}>Sin niveles, sin funciones bloqueadas, sin sorpresas. Todo lo que viste en esta página está adentro.</p>
          <div style={{ maxWidth: 460, margin: "0 auto", background: "#fff", border: "2px solid #12b886", borderRadius: 24, padding: "clamp(28px,4vw,40px)", boxShadow: "0 24px 60px rgba(18,184,134,0.14)", textAlign: "left" }}>
            <div style={{ display: "inline-flex", background: "#8bc540", color: "#1c222c", fontWeight: 700, fontSize: 13, padding: "6px 14px", borderRadius: 999, marginBottom: 20 }}>7 días de prueba gratis</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
              <span style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(40px,5vw,52px)" }}>$16.990</span>
              <span style={{ color: "#5d6578", fontSize: 17, fontWeight: 500 }}>/ mes</span>
            </div>
            <div style={{ color: "#8b93a7", fontSize: 14, marginBottom: 24 }}>Precio en pesos argentinos. Cancelás cuando quieras.</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 11, marginBottom: 28 }}>
              {planItems.map((it) => (
                <div key={it} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 15, color: "#1c222c" }}>
                  <span style={{ color: "#12b886", fontWeight: 700, flexShrink: 0 }}>✓</span>{it}
                </div>
              ))}
            </div>
            <a href={WA_LINK} target="_blank" style={{ display: "flex", justifyContent: "center", background: "#12b886", color: "#fff", fontWeight: 700, fontSize: 17, padding: "15px 28px", borderRadius: 999, boxShadow: "0 8px 24px rgba(18,184,134,0.28)", textDecoration: "none" }}>Probalo gratis 7 días</a>
            <p style={{ color: "#8b93a7", fontSize: 13, textAlign: "center", margin: "14px 0 0" }}>Arrancamos por WhatsApp: te lo dejamos configurado y andando.</p>
          </div>
        </div>
      </section>

      {/* GALERIA */}
      <section style={{ padding: "0 clamp(16px,5vw,64px) clamp(48px,7vw,80px)", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          {fotos.map((f) => (
            <img key={f.src} src={f.src} alt={f.alt} style={{ width: "100%", height: 260, objectFit: "cover", borderRadius: 20 }} />
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" style={{ padding: "0 clamp(16px,5vw,64px) clamp(56px,8vw,96px)", maxWidth: 820, margin: "0 auto" }}>
        <h2 style={{ fontFamily: font.sora, fontWeight: 700, fontSize: "clamp(26px,3.6vw,38px)", margin: "0 0 8px", textAlign: "center" }}>Preguntas frecuentes</h2>
        <p style={{ color: "#5d6578", fontSize: 17, margin: "0 0 32px", textAlign: "center" }}>Lo que todos preguntan antes de arrancar.</p>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {faqs.map((q, i) => (
            <div key={q.q} style={{ borderBottom: "1px solid #e9ecf1" }}>
              <button onClick={() => setFaq(faq === i ? -1 : i)} style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: "18px 4px", fontFamily: font.dm, fontSize: 16.5, fontWeight: 700, color: "#1c222c" }}>
                {q.q}
                <span style={{ color: "#12b886", fontSize: 20, fontWeight: 700, flexShrink: 0 }}>{faq === i ? "−" : "+"}</span>
              </button>
              {faq === i && <div style={{ color: "#5d6578", fontSize: 15, lineHeight: 1.6, padding: "0 4px 18px", maxWidth: 680 }}>{q.a}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ borderTop: "1px solid #eef1f5", padding: "28px clamp(16px,5vw,64px)", display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src="/img/logo.png" alt="Turnos360" style={{ width: 28, height: 28, objectFit: "contain" }} />
          <span style={{ fontFamily: font.sora, fontWeight: 700, fontSize: 16 }}>Turnos<span style={{ color: "#12b886" }}>360</span></span>
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
          </div>
          <span style={{ color: "#8b93a7", fontSize: 13.5, textAlign: "right" }}>
            © {new Date().getFullYear()} Turnos360 · Hecho en Mendoza, Argentina ·{" "}
            <a href="mailto:turnos360.contacto@gmail.com" style={{ color: "#5d6578" }}>
              turnos360.contacto@gmail.com
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}
