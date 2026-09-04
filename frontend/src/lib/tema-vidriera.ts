/**
 * El LOOK de la página pública de un negocio.
 *
 * UN SOLO ARCHIVO PARA LOS DOS LADOS
 * ──────────────────────────────────
 * Lo usan el editor de «Mi página» (para la vista previa) y la vidriera de
 * verdad. Que la previsualización y la página real salgan del MISMO código no
 * es una comodidad: es lo único que garantiza que lo que el dueño ve mientras
 * elige sea lo que después van a ver sus clientes. Con dos implementaciones,
 * la previa miente el día que alguien toca una y no la otra — y se descubre
 * cuando un cliente ya vio la página fea.
 *
 * POR QUÉ LAS OPCIONES SON LISTAS CERRADAS
 * ────────────────────────────────────────
 * Nada de esto es CSS libre. Cada valor es uno de un puñado, elegidos para que
 * TODAS las combinaciones se vean bien. Un dueño de barbería no tiene por qué
 * saber que gris sobre gris no se lee ni que una tipografía de display a 14 px
 * es ilegible; la libertad total acá no produce páginas lindas, produce
 * páginas rotas — y las rotas también nos representan a nosotros.
 *
 * El color de marca sí es libre: es su marca. El contraste del texto se
 * calcula desde el fondo (ver `textoSobre`), así que no puede quedar ilegible
 * elija lo que elija.
 */

export type Plantilla =
  | "claro"
  | "oscuro"
  | "arena"
  | "bosque"
  | "vino"
  | "noche"
  | "propio";

export type FondoTipo = "solido" | "gradiente" | "patron";
export type BotonForma = "recto" | "suave" | "medio" | "pildora";
export type BotonEstilo = "solido" | "contorno" | "sombra";
export type Titulos = "sans" | "serif" | "display";
export type LogoForma = "circulo" | "cuadrado";
export type LogoTamano = "chico" | "grande";

export interface TemaVidriera {
  plantilla: Plantilla;
  fondo_tipo: FondoTipo;
  fondo_color: string | null;
  fondo_color_2: string | null;
  boton_forma: BotonForma;
  boton_estilo: BotonEstilo;
  titulos: Titulos;
  logo_forma: LogoForma;
  logo_tamano: LogoTamano;
}

export const TEMA_POR_DEFECTO: TemaVidriera = {
  plantilla: "claro",
  fondo_tipo: "solido",
  fondo_color: null,
  fondo_color_2: null,
  boton_forma: "medio",
  boton_estilo: "solido",
  titulos: "sans",
  logo_forma: "circulo",
  logo_tamano: "grande",
};

/**
 * Completa lo que falte con los defaults.
 *
 * La vidriera recibe `tema` del backend como dict libre y puede venir vacío
 * (una empresa que nunca lo tocó) o incompleto (una guardada antes de que
 * existiera una opción). Sin esto, cada lectura tendría que preguntar por
 * null y la página se rompería en el campo que falte.
 */
export function normalizarTema(crudo: Partial<TemaVidriera> | null | undefined): TemaVidriera {
  return { ...TEMA_POR_DEFECTO, ...(crudo ?? {}) };
}

/** Los colores base de cada plantilla. `propio` hereda de claro. */
export const PLANTILLAS: Record<
  Exclude<Plantilla, "propio">,
  { nombre: string; fondo: string; fondo2: string; acento: string; titulos: Titulos }
> = {
  claro: { nombre: "Claro", fondo: "#ffffff", fondo2: "#f4f6f9", acento: "#00d4aa", titulos: "sans" },
  arena: { nombre: "Arena", fondo: "#f5efe6", fondo2: "#e8dcc9", acento: "#8a6a4b", titulos: "serif" },
  bosque: { nombre: "Bosque", fondo: "#f0f4f0", fondo2: "#dbe7dc", acento: "#2f6b4f", titulos: "serif" },
  vino: { nombre: "Vino", fondo: "#f7f0f1", fondo2: "#ecd9dc", acento: "#8c2f3e", titulos: "serif" },
  oscuro: { nombre: "Oscuro", fondo: "#14161a", fondo2: "#1e2228", acento: "#00d4aa", titulos: "sans" },
  noche: { nombre: "Noche", fondo: "#0f1226", fondo2: "#1b2044", acento: "#8b7cff", titulos: "display" },
};

const RADIO: Record<BotonForma, string> = {
  recto: "2px",
  suave: "8px",
  medio: "14px",
  pildora: "999px",
};

export const FAMILIAS: Record<Titulos, string> = {
  sans: "var(--fuente-titulos), system-ui, sans-serif",
  serif: "Georgia, 'Times New Roman', serif",
  display: "var(--fuente-marca), system-ui, sans-serif",
};

/** "#rrggbb" → {r,g,b}. Devuelve null si no es un hex válido. */
function aRgb(hex: string): { r: number; g: number; b: number } | null {
  const v = (hex || "").trim().replace("#", "");
  if (!/^[0-9a-f]{6}$/i.test(v)) return null;
  return {
    r: parseInt(v.slice(0, 2), 16),
    g: parseInt(v.slice(2, 4), 16),
    b: parseInt(v.slice(4, 6), 16),
  };
}

/**
 * Qué color de texto se lee sobre este fondo: el oscuro o el claro.
 *
 * Es lo que permite dejar el color de fondo LIBRE sin que la página pueda
 * quedar ilegible. Usa luminancia relativa (la fórmula de WCAG) y no el
 * promedio de los canales: el ojo ve el verde mucho más brillante que el
 * azul, así que un promedio simple da texto blanco sobre amarillo.
 */
export function textoSobre(fondo: string): string {
  const rgb = aRgb(fondo);
  if (!rgb) return "#14161a";
  const canal = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  const L = 0.2126 * canal(rgb.r) + 0.7152 * canal(rgb.g) + 0.0722 * canal(rgb.b);
  return L > 0.45 ? "#14161a" : "#ffffff";
}

/** El mismo color con transparencia, para bordes y fondos suaves. */
export function conAlfa(hex: string, alfa: number): string {
  const rgb = aRgb(hex);
  if (!rgb) return `rgba(0,0,0,${alfa})`;
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alfa})`;
}

export interface EstilosVidriera {
  /** Para el contenedor de la página. */
  fondo: React.CSSProperties;
  /** Color de texto que contrasta con ese fondo. */
  texto: string;
  /** Texto secundario: el mismo, atenuado. */
  textoSuave: string;
  /** Para los botones principales. */
  boton: React.CSSProperties;
  /** Para los botones secundarios (mismo radio, sin relleno). */
  botonSecundario: React.CSSProperties;
  /** Para las tarjetas de servicio. */
  tarjeta: React.CSSProperties;
  /** Familia tipográfica de los títulos. */
  familiaTitulos: string;
  /** El acento efectivo (el del negocio, o el de la plantilla). */
  acento: string;
  radio: string;
}

/**
 * Traduce el tema + el color de marca a estilos concretos.
 *
 * `acentoNegocio` es `empresa.color_marca`: si el dueño eligió uno, MANDA
 * sobre el de la plantilla. La plantilla define el clima (fondo, tipografía);
 * el acento es la marca, y la marca gana.
 */
export function estilosDe(tema: TemaVidriera, acentoNegocio?: string | null): EstilosVidriera {
  const base =
    PLANTILLAS[(tema.plantilla === "propio" ? "claro" : tema.plantilla)] ?? PLANTILLAS.claro;

  const fondo1 = tema.fondo_color || base.fondo;
  const fondo2 = tema.fondo_color_2 || base.fondo2;
  const acentoValido = /^#[0-9a-f]{6}$/i.test((acentoNegocio || "").trim());
  const acento = acentoValido ? (acentoNegocio as string).trim() : base.acento;

  const texto = textoSobre(fondo1);
  const claroSobreOscuro = texto === "#ffffff";

  let fondo: React.CSSProperties;
  if (tema.fondo_tipo === "gradiente") {
    fondo = { backgroundImage: `linear-gradient(160deg, ${fondo1} 0%, ${fondo2} 100%)` };
  } else if (tema.fondo_tipo === "patron") {
    // Puntos muy suaves del color del texto: se nota que hay textura sin que
    // compita con el contenido. En SVG inline para no pedir ninguna imagen.
    const punto = encodeURIComponent(conAlfa(texto, 0.07));
    fondo = {
      backgroundColor: fondo1,
      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18'%3E%3Ccircle cx='2' cy='2' r='1.4' fill='${punto}'/%3E%3C/svg%3E")`,
    };
  } else {
    fondo = { backgroundColor: fondo1 };
  }

  const radio = RADIO[tema.boton_forma];
  const textoBoton = textoSobre(acento);

  const boton: React.CSSProperties =
    tema.boton_estilo === "contorno"
      ? {
          borderRadius: radio,
          background: "transparent",
          color: acento,
          border: `1.5px solid ${acento}`,
        }
      : {
          borderRadius: radio,
          background: acento,
          color: textoBoton,
          border: `1.5px solid ${acento}`,
          ...(tema.boton_estilo === "sombra"
            ? { boxShadow: `0 10px 26px -8px ${conAlfa(acento, 0.55)}` }
            : {}),
        };

  return {
    fondo,
    texto,
    textoSuave: conAlfa(texto, 0.62),
    boton,
    botonSecundario: {
      borderRadius: radio,
      background: "transparent",
      color: texto,
      border: `1.5px solid ${conAlfa(texto, 0.22)}`,
    },
    tarjeta: {
      borderRadius: `calc(${radio === "999px" ? "18px" : radio} + 4px)`,
      background: claroSobreOscuro ? conAlfa("#ffffff", 0.06) : "#ffffff",
      border: `1px solid ${conAlfa(texto, 0.1)}`,
    },
    familiaTitulos: FAMILIAS[tema.titulos],
    acento,
    radio,
  };
}
