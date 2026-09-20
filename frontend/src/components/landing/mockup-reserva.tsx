"use client";

/**
 * El mockup del hero: la reserva de un cliente, de punta a punta, sola.
 *
 * Antes era la misma tarjeta pero QUIETA, con el servicio y el horario ya
 * elegidos y las dos chapitas siempre visibles. Mostraba el resultado sin
 * mostrar el mecanismo: quien la miraba veía una captura, no un producto.
 *
 * El ciclo dice en seis pasos lo que la landing explica en tres párrafos:
 * elige · elige horario · paga la seña · le llega el recordatorio.
 */

import { AnimatePresence, motion } from "framer-motion";

import { EASE, usePasos } from "./movimiento";

const TIEMPOS = [1400, 1250, 1150, 1000, 1200, 2800] as const;

const SERVICIOS = [
  { nombre: "Corte + Barba", precio: "$15.000" },
  { nombre: "Corte clásico", precio: "$11.000" },
];
const HORARIOS = ["10:00", "11:30", "15:00"];

const TEAL = "#12b886";
const BORDE = "#e9ecf1";

export function MockupReserva() {
  const paso = usePasos(TIEMPOS);

  const servicioElegido = paso >= 1;
  const horarioElegido = paso >= 2;
  const cobrando = paso === 3;
  const cobrado = paso >= 4;

  return (
    <div style={{ position: "relative", width: "100%", maxWidth: 430 }}>
      <motion.div
        initial={{ opacity: 0, y: 26 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: EASE, delay: 0.15 }}
        style={{
          background: "#fff",
          // El hero pinta `color: #fff` y esta tarjeta vive adentro: sin volver
          // a fijar la tinta, el nombre del negocio salía blanco sobre blanco.
          color: "#12161f",
          borderRadius: 26,
          padding: 24,
          boxShadow:
            "0 40px 90px -20px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)",
        }}
      >
        {/* Cabecera del negocio */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <img
            src="/img/elfaro-logo.webp"
            alt="Barbería El Faro"
            width={46}
            height={46}
            style={{
              width: 46,
              height: 46,
              borderRadius: "50%",
              objectFit: "cover",
              background: "#fff",
              border: `1px solid ${BORDE}`,
              flexShrink: 0,
            }}
          />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 15.5 }}>Barbería El Faro</div>
            <div style={{ fontSize: 12.5, color: "#8b93a7" }}>turnos360.com.ar/elfaro</div>
          </div>
        </div>

        <Rotulo>Elegí tu servicio</Rotulo>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
          {SERVICIOS.map((s, i) => {
            const activo = servicioElegido && i === 0;
            return (
              <motion.div
                key={s.nombre}
                animate={{
                  borderColor: activo ? TEAL : BORDE,
                  backgroundColor: activo ? "#f2fbf7" : "#ffffff",
                  scale: activo && paso === 1 ? [1, 0.975, 1] : 1,
                }}
                transition={{ duration: 0.36, ease: EASE }}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  border: `1.5px solid ${BORDE}`,
                  borderRadius: 13,
                  padding: "12px 14px",
                }}
              >
                <motion.span
                  animate={{ color: activo ? "#1c222c" : "#5d6578" }}
                  style={{ fontSize: 14.5, fontWeight: activo ? 700 : 500 }}
                >
                  {s.nombre}
                </motion.span>
                <motion.span
                  animate={{ color: activo ? "#0e8371" : "#8b93a7" }}
                  style={{ fontSize: 14.5, fontWeight: activo ? 700 : 500 }}
                >
                  {s.precio}
                </motion.span>
              </motion.div>
            );
          })}
        </div>

        <Rotulo>Mañana, jueves</Rotulo>
        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          {HORARIOS.map((h, i) => {
            const activo = horarioElegido && i === 1;
            return (
              <motion.div
                key={h}
                animate={{
                  backgroundColor: activo ? TEAL : "#ffffff",
                  borderColor: activo ? TEAL : BORDE,
                  color: activo ? "#ffffff" : "#8b93a7",
                  scale: activo && paso === 2 ? [1, 0.94, 1] : 1,
                }}
                transition={{ duration: 0.34, ease: EASE }}
                style={{
                  flex: 1,
                  textAlign: "center",
                  border: `1.5px solid ${BORDE}`,
                  borderRadius: 11,
                  padding: "10px 0",
                  fontSize: 14,
                  fontWeight: 700,
                }}
              >
                {h}
              </motion.div>
            );
          })}
        </div>

        {/* El botón: se apaga hasta que hay algo que reservar, se aprieta solo
            en el paso 3 y confirma en verde. */}
        <motion.div
          animate={{
            backgroundColor: cobrado ? "#0e8371" : "#1c222c",
            opacity: horarioElegido ? 1 : 0.45,
            scale: cobrando ? 0.975 : 1,
          }}
          transition={{ duration: 0.34, ease: EASE }}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            borderRadius: 15,
            padding: "15px 16px",
            minHeight: 58,
          }}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={cobrado ? "ok" : cobrando ? "cobrando" : "listo"}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22, ease: EASE }}
              style={{ color: "#fff", fontWeight: 700, fontSize: 14.5 }}
            >
              {cobrado
                ? "Turno confirmado"
                : cobrando
                  ? "Cobrando la seña…"
                  : "Reservar con seña"}
            </motion.span>
          </AnimatePresence>
          <img
            src="/img/mercado-pago.png"
            alt="Mercado Pago"
            style={{ height: 26, background: "#fff", borderRadius: 6, padding: "3px 8px", flexShrink: 0 }}
          />
        </motion.div>
      </motion.div>

      {/* Las dos chapitas ya no están siempre: llegan cuando pasa lo que dicen. */}
      <AnimatePresence>
        {paso >= 5 && (
          <Chapita key="wa" style={{ top: -18, right: -10 }}>
            <img src="/img/whatsapp.png" alt="" style={{ height: 18 }} />
            <span>Recordatorio enviado</span>
          </Chapita>
        )}
        {cobrado && (
          <Chapita key="sena" style={{ bottom: -16, left: -12 }}>
            <span
              style={{ width: 8, height: 8, borderRadius: "50%", background: TEAL, flexShrink: 0 }}
            />
            <span>Seña cobrada · $5.000</span>
          </Chapita>
        )}
      </AnimatePresence>
    </div>
  );
}

function Rotulo({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 12.5, fontWeight: 700, color: "#8b93a7", marginBottom: 10, letterSpacing: "0.01em" }}>
      {children}
    </div>
  );
}

function Chapita({
  children,
  style,
}: {
  children: React.ReactNode;
  style: React.CSSProperties;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9, y: -4 }}
      transition={{ type: "spring", stiffness: 420, damping: 26 }}
      style={{
        position: "absolute",
        background: "#fff",
        borderRadius: 999,
        padding: "9px 15px",
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 12.5,
        fontWeight: 700,
        whiteSpace: "nowrap",
        boxShadow: "0 16px 38px rgba(0,0,0,0.30)",
        ...style,
      }}
    >
      {children}
    </motion.div>
  );
}
