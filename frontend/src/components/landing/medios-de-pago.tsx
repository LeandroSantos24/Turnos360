"use client";

/**
 * «Cómo se cobra»: separa lo que el negocio le cobra a SUS clientes de lo que
 * el negocio le paga a Turnos360. Mezclarlo hacía creer que Turnos360 cobra
 * los turnos o que la cuota se debita sola.
 *
 * Cada fila dice quién mueve la plata y si se acredita sola o hay que
 * revisarla, que es lo que pregunta el dueño antes de contratar.
 *
 * El débito automático de la cuota existe en el código (mp_debito.py) pero
 * depende de la cuenta de Mercado Pago de Turnos360. Hasta que esté
 * configurada y probada en producción no se ofrece acá: se prende con
 * NEXT_PUBLIC_SUSCRIPCION_CON_MP=1.
 */

import { Revelar } from "@/components/landing/movimiento";

const SUSCRIPCION_CON_MP = process.env.NEXT_PUBLIC_SUSCRIPCION_CON_MP === "1";

type Fila = { titulo: string; detalle: string; tipo?: "auto" | "vos" | "nosotros"; logo?: string };

const DE_TUS_CLIENTES: Fila[] = [
  {
    titulo: "Seña o pago total online",
    detalle: "Con tu propia cuenta de Mercado Pago, al reservar. La plata va directo a tu cuenta y el turno queda pagado solo.",
    tipo: "auto",
    logo: "/img/mercado-pago.png",
  },
  {
    titulo: "Efectivo, débito, crédito, transferencia y QR",
    detalle: "Lo que cobrás en el local lo registrás en la caja. Cada método con su comisión, editable.",
    tipo: "vos",
  },
  {
    titulo: "Transferencias",
    detalle: "Turnos360 no se conecta con tu banco: confirmás que llegó y la registrás vos.",
    tipo: "vos",
  },
];

const A_TURNOS360: Fila[] = [
  {
    titulo: "Transferencia bancaria",
    detalle: "Informás el pago desde «Mi suscripción» con el comprobante. Lo revisamos y se acredita en tu cuenta.",
    tipo: "nosotros",
  },
  ...(SUSCRIPCION_CON_MP
    ? [
        {
          titulo: "Débito automático",
          detalle: "Lo activás desde «Mi suscripción» y la cuota se cobra sola cada mes.",
          tipo: "auto" as const,
          logo: "/img/mercado-pago.png",
        },
      ]
    : []),
  {
    titulo: "Sin comisión por turno",
    detalle: "Pagás la cuota del plan y nada más. Lo que cobrás a tus clientes es tuyo.",
  },
];

const ETIQUETA = {
  auto: { texto: "Se acredita solo", color: "#0a6b5c", fondo: "#e6f7f1" },
  vos: { texto: "Lo registrás vos", color: "#8a5a0b", fondo: "#fff4e0" },
  nosotros: { texto: "Revisión manual", color: "#8a5a0b", fondo: "#fff4e0" },
};

function Columna({ titulo, bajada, filas }: { titulo: string; bajada: string; filas: Fila[] }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e9ecf1", borderRadius: 22, padding: "clamp(20px,3vw,30px)", height: "100%" }}>
      <h3 style={{ fontFamily: "var(--fuente-titulos)", fontWeight: 700, fontSize: 21, margin: 0, color: "#12161f" }}>{titulo}</h3>
      <p style={{ color: "#5d6578", fontSize: 14.5, margin: "6px 0 18px", lineHeight: 1.55 }}>{bajada}</p>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 14 }}>
        {filas.map((f) => {
          const e = f.tipo ? ETIQUETA[f.tipo] : null;
          return (
            <li key={f.titulo} style={{ borderTop: "1px solid #f0f2f5", paddingTop: 14 }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 15.5, color: "#12161f" }}>{f.titulo}</span>
                {e && (
                  <span style={{ fontSize: 12, fontWeight: 700, color: e.color, background: e.fondo, borderRadius: 999, padding: "3px 10px" }}>
                    {e.texto}
                  </span>
                )}
                {f.logo && (
                  <img src={f.logo} alt="Mercado Pago" loading="lazy" style={{ height: 30, marginLeft: "auto" }} />
                )}
              </div>
              <p style={{ color: "#5d6578", fontSize: 14, lineHeight: 1.55, margin: "6px 0 0" }}>{f.detalle}</p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function MediosDePago() {
  return (
    <section
      id="cobros"
      aria-labelledby="titulo-cobros"
      style={{ padding: "clamp(64px,8vw,104px) clamp(20px,5vw,72px)", maxWidth: 1440, margin: "0 auto" }}
    >
      <Revelar style={{ textAlign: "center", marginBottom: 40 }}>
        <h2
          id="titulo-cobros"
          style={{
            fontFamily: "var(--fuente-titulos)",
            fontWeight: 700,
            fontSize: "clamp(28px,3.9vw,46px)",
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
            margin: 0,
            color: "#12161f",
          }}
        >
          Cómo se cobra, sin letra chica
        </h2>
        <p style={{ color: "#5d6578", fontSize: "clamp(16px,1.4vw,18px)", lineHeight: 1.6, maxWidth: 640, margin: "14px auto 0" }}>
          Lo que te pagan tus clientes es una cosa; lo que pagás vos por Turnos360, otra. Acá está cada una.
        </p>
      </Revelar>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))", gap: 18 }}>
        <Revelar>
          <Columna
            titulo="Lo que te pagan tus clientes"
            bajada="Turnos360 no toca esa plata: va a tu cuenta o a tu caja."
            filas={DE_TUS_CLIENTES}
          />
        </Revelar>
        <Revelar demora={0.08}>
          <Columna
            titulo="Lo que pagás vos por Turnos360"
            bajada={SUSCRIPCION_CON_MP ? "La cuota mensual del plan que elegiste." : "La cuota mensual del plan que elegiste, por transferencia."}
            filas={A_TURNOS360}
          />
        </Revelar>
      </div>
    </section>
  );
}
