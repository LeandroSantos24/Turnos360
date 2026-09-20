"use client";

/**
 * La página de reservas de un negocio, en un teléfono, cambiando sola.
 *
 * El punto de esta sección no es "tenés una página": es que la página es DEL
 * NEGOCIO —su portada, su logo, su color, su gente, sus servicios—. Eso con una
 * sola captura no se ve; con tres que se turnan, se entiende en cinco segundos.
 *
 * Los tres son de ejemplo y están rotulados como tales.
 */

import { AnimatePresence, motion } from "framer-motion";

import { EASE, usePasos } from "./movimiento";

type Persona = { nombre: string; foto?: string };

type Negocio = {
  id: string;
  nombre: string;
  zona: string;
  rubro: string;
  portada: string;
  logo?: string;
  iniciales: string;
  acento: string;
  equipo: Persona[];
  servicios: { nombre: string; detalle: string; precio: string }[];
  horarios: string[];
};

const NEGOCIOS: Negocio[] = [
  {
    id: "elfaro",
    nombre: "Barbería El Faro",
    zona: "Godoy Cruz, Mendoza",
    rubro: "Barbería",
    portada: "/img/elfaro-portada.webp",
    logo: "/img/elfaro-logo.webp",
    iniciales: "EF",
    acento: "#1c3f6e",
    equipo: [
      { nombre: "Nico", foto: "/img/elfaro-barbero-1.webp" },
      { nombre: "Tomás", foto: "/img/elfaro-barbero-2.webp" },
    ],
    servicios: [
      { nombre: "Corte + Barba", detalle: "45 min", precio: "$15.000" },
      { nombre: "Corte clásico", detalle: "30 min", precio: "$11.000" },
    ],
    horarios: ["10:00", "11:30", "15:00"],
  },
  {
    id: "studiolu",
    nombre: "Studio Lu",
    zona: "Ciudad, Mendoza",
    rubro: "Salón de uñas",
    portada: "/img/studiolu-portada.webp",
    logo: "/img/studiolu-logo.webp",
    iniciales: "LU",
    // El rosa del logo es muy claro para un botón con texto blanco (no llega a
    // 3:1). Este es el mismo rosa bajado hasta 4.6:1, que sí se lee.
    acento: "#c9486f",
    equipo: [
      { nombre: "Lucía", foto: "/img/studiolu-pro-1.webp" },
      { nombre: "Jazmín" },
    ],
    servicios: [
      { nombre: "Kapping + diseño", detalle: "90 min", precio: "$18.000" },
      { nombre: "Semipermanente", detalle: "60 min", precio: "$12.500" },
    ],
    horarios: ["09:30", "14:00", "17:30"],
  },
  {
    id: "alma",
    nombre: "Alma Estética",
    zona: "Chacras de Coria",
    rubro: "Centro de estética",
    portada: "/img/alma-portada.webp",
    logo: "/img/alma-logo.webp",
    iniciales: "AL",
    // El bronce del logo, bajado hasta que el blanco encima se lea.
    acento: "#9a6a52",
    equipo: [
      { nombre: "Carla", foto: "/img/alma-pro-1.webp" },
      { nombre: "Rocío", foto: "/img/alma-pro-2.webp" },
    ],
    servicios: [
      { nombre: "Limpieza profunda", detalle: "60 min", precio: "$22.000" },
      { nombre: "Masaje descontracturante", detalle: "50 min", precio: "$19.000" },
    ],
    horarios: ["11:00", "16:00", "18:30"],
  },
];

const TIEMPOS = NEGOCIOS.map(() => 5600);

export function TelefonoLocal() {
  const indice = usePasos(TIEMPOS);
  const n = NEGOCIOS[indice];

  return (
    <div style={{ position: "relative", width: "100%", maxWidth: 330, margin: "0 auto" }}>
      {/* Halo del color del negocio de turno: el fondo también cambia. */}
      <motion.div
        aria-hidden
        animate={{ background: `radial-gradient(60% 55% at 50% 40%, ${n.acento}38, transparent 70%)` }}
        transition={{ duration: 0.9, ease: EASE }}
        style={{ position: "absolute", inset: "-14% -22%", borderRadius: "50%", filter: "blur(10px)" }}
      />

      {/* Carcasa */}
      <div
        style={{
          position: "relative",
          borderRadius: 42,
          padding: 9,
          background: "linear-gradient(160deg, #2b3340, #12161d)",
          boxShadow: "0 40px 90px -24px rgba(16,22,32,0.55), 0 0 0 1px rgba(255,255,255,0.06)",
        }}
      >
        <div
          style={{
            position: "relative",
            borderRadius: 34,
            overflow: "hidden",
            background: "#fff",
            aspectRatio: "9 / 18.4",
          }}
        >
          {/* Muesca */}
          <div
            aria-hidden
            style={{
              position: "absolute",
              top: 9,
              left: "50%",
              transform: "translateX(-50%)",
              width: 92,
              height: 22,
              borderRadius: 999,
              background: "#12161d",
              zIndex: 3,
            }}
          />

          <AnimatePresence mode="wait">
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: 26 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -26 }}
              transition={{ duration: 0.5, ease: EASE }}
              style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column" }}
            >
              {/* Portada */}
              <div style={{ position: "relative", height: "26%", flexShrink: 0 }}>
                <img
                  src={n.portada}
                  alt=""
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                />
                <div
                  aria-hidden
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: "linear-gradient(180deg, rgba(10,15,30,0.42) 0%, transparent 45%)",
                  }}
                />
              </div>

              {/* zIndex: la portada es `position: relative` por el degradé, así
                  que sin esto pinta por encima y se come el nombre del negocio,
                  que sube 22px para montarse sobre ella. */}
              <div style={{ position: "relative", zIndex: 1, padding: "0 16px 16px", flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
                {/* Logo + nombre.
                    APILADOS, no en fila: con el nombre al costado del logo, la
                    mitad de arriba de las letras caía sobre la portada oscura y
                    el texto —que es tinta negra— desaparecía ahí. El logo sí
                    puede montarse sobre la foto porque lleva su propio borde
                    blanco. */}
                <div style={{ marginTop: -24 }}>
                  {n.logo ? (
                    <img
                      src={n.logo}
                      alt=""
                      style={{
                        width: 52,
                        height: 52,
                        borderRadius: 16,
                        objectFit: "cover",
                        background: "#fff",
                        border: "3px solid #fff",
                        boxShadow: "0 6px 18px rgba(16,22,32,0.18)",
                        flexShrink: 0,
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        width: 52,
                        height: 52,
                        borderRadius: 16,
                        border: "3px solid #fff",
                        background: n.acento,
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 700,
                        fontSize: 17,
                        letterSpacing: "0.02em",
                        boxShadow: "0 6px 18px rgba(16,22,32,0.18)",
                        flexShrink: 0,
                      }}
                    >
                      {n.iniciales}
                    </div>
                  )}
                  <div style={{ marginTop: 9, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.2 }}>{n.nombre}</div>
                    <div style={{ fontSize: 11.5, color: "#8b93a7", marginTop: 2 }}>{n.zona}</div>
                  </div>
                </div>

                <Seccion titulo="Con quién te atendés" arriba={16}>
                  <div style={{ display: "flex", gap: 8 }}>
                    {n.equipo.map((p, i) => (
                      <div
                        key={p.nombre}
                        style={{
                          flex: 1,
                          display: "flex",
                          alignItems: "center",
                          gap: 7,
                          border: `1.5px solid ${i === 0 ? n.acento : "#e9ecf1"}`,
                          background: i === 0 ? `${n.acento}0f` : "#fff",
                          borderRadius: 11,
                          padding: "6px 8px",
                          minWidth: 0,
                        }}
                      >
                        {p.foto ? (
                          <img
                            src={p.foto}
                            alt=""
                            style={{ width: 26, height: 26, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
                          />
                        ) : (
                          <span
                            style={{
                              width: 26,
                              height: 26,
                              borderRadius: "50%",
                              background: `${n.acento}22`,
                              color: n.acento,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 11,
                              fontWeight: 700,
                              flexShrink: 0,
                            }}
                          >
                            {p.nombre.slice(0, 1)}
                          </span>
                        )}
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: i === 0 ? 700 : 500,
                            color: i === 0 ? "#1c222c" : "#5d6578",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {p.nombre}
                        </span>
                      </div>
                    ))}
                  </div>
                </Seccion>

                <Seccion titulo="Servicios" arriba={14}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                    {n.servicios.map((s, i) => (
                      <div
                        key={s.nombre}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 8,
                          border: `1.5px solid ${i === 0 ? n.acento : "#e9ecf1"}`,
                          background: i === 0 ? `${n.acento}0f` : "#fff",
                          borderRadius: 11,
                          padding: "9px 11px",
                          minWidth: 0,
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: 12.5,
                              fontWeight: i === 0 ? 700 : 500,
                              color: i === 0 ? "#1c222c" : "#5d6578",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {s.nombre}
                          </div>
                          <div style={{ fontSize: 10.5, color: "#8b93a7", marginTop: 1 }}>{s.detalle}</div>
                        </div>
                        <span
                          style={{
                            fontSize: 12.5,
                            fontWeight: 700,
                            color: i === 0 ? n.acento : "#8b93a7",
                            flexShrink: 0,
                          }}
                        >
                          {s.precio}
                        </span>
                      </div>
                    ))}
                  </div>
                </Seccion>

                <Seccion titulo="Mañana, jueves" arriba={14}>
                  <div style={{ display: "flex", gap: 6 }}>
                    {n.horarios.map((h, i) => (
                      <span
                        key={h}
                        style={{
                          flex: 1,
                          textAlign: "center",
                          borderRadius: 9,
                          padding: "7px 0",
                          fontSize: 11.5,
                          fontWeight: 700,
                          ...(i === 1
                            ? { background: n.acento, color: "#fff" }
                            : { border: "1.5px solid #e9ecf1", color: "#8b93a7" }),
                        }}
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                </Seccion>

                <div
                  style={{
                    marginTop: "auto",
                    paddingTop: 14,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    background: n.acento,
                    color: "#fff",
                    borderRadius: 13,
                    padding: "12px 14px",
                    fontSize: 13,
                    fontWeight: 700,
                  }}
                >
                  Reservar con seña
                  <img
                    src="/img/mercado-pago.png"
                    alt=""
                    style={{ height: 19, background: "#fff", borderRadius: 4, padding: "2px 6px" }}
                  />
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Qué negocio se está viendo, y los puntitos del ciclo. */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          marginTop: 18,
        }}
      >
        {NEGOCIOS.map((x, i) => (
          <motion.span
            key={x.id}
            animate={{
              width: i === indice ? 22 : 7,
              backgroundColor: i === indice ? x.acento : "#cfd5de",
            }}
            transition={{ duration: 0.4, ease: EASE }}
            style={{ height: 7, borderRadius: 999, display: "block" }}
          />
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.p
          key={n.id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.32, ease: EASE }}
          style={{ textAlign: "center", fontSize: 13, color: "#8b93a7", margin: "10px 0 0" }}
        >
          {n.rubro} · ejemplo
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

function Seccion({
  titulo,
  arriba,
  children,
}: {
  titulo: string;
  arriba: number;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginTop: arriba }}>
      <div style={{ fontSize: 10.5, fontWeight: 700, color: "#8b93a7", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 7 }}>
        {titulo}
      </div>
      {children}
    </div>
  );
}
