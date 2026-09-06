"use client";

/**
 * «El look»: la sección del editor que decide cómo se ve la página pública.
 *
 * Antes lo único configurable era el color de acento. Dos barberías de la
 * misma cuadra tenían la misma página con distinto logo — y esa página es lo
 * que el negocio comparte en su Instagram, o sea su cara. Que se parezcan
 * todas entre sí es el mejor argumento para no usarla.
 *
 * El orden de los controles es el del impacto: primero la plantilla (un toque
 * y cambia todo), y recién después los ajustes finos para el que quiere
 * seguir. Al revés, el 90 % que solo quiere que quede lindo se pierde entre
 * seis selectores antes de llegar a lo que le resuelve el problema.
 */

import { Check } from "lucide-react";

import {
  FORMAS_DE_LOGO,
  PLANTILLAS,
  estilosDe,
  formaDelLogo,
  normalizarTema,
  type BotonEstilo,
  type BotonForma,
  type FondoTipo,
  type LogoForma,
  type Plantilla,
  type TemaVidriera,
  type Titulos,
} from "@/lib/tema-vidriera";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SubirImagen } from "@/components/subir-imagen";
import { urlDeImagen } from "@/lib/imagenes";

/** Una fila de opciones con forma de píldora. */
function Elegir<T extends string>({
  etiqueta,
  ayuda,
  valor,
  opciones,
  onElegir,
}: {
  etiqueta: string;
  ayuda?: string;
  valor: T;
  opciones: { valor: T; label: string }[];
  onElegir: (v: T) => void;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">{etiqueta}</Label>
      <div className="flex flex-wrap gap-1.5">
        {opciones.map((o) => (
          <button
            key={o.valor}
            type="button"
            onClick={() => onElegir(o.valor)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              o.valor === valor
                ? "border-transparent bg-primary text-primary-foreground"
                : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
      {ayuda && <p className="text-xs text-muted-foreground">{ayuda}</p>}
    </div>
  );
}

/** El cuadradito de color con su input hex al lado. */
function Color({
  etiqueta,
  valor,
  porDefecto,
  onCambio,
}: {
  etiqueta: string;
  valor: string | null;
  porDefecto: string;
  onCambio: (v: string | null) => void;
}) {
  const actual = valor || porDefecto;
  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">{etiqueta}</Label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={actual}
          onChange={(e) => onCambio(e.target.value)}
          className="h-9 w-12 cursor-pointer rounded-lg border bg-card p-1"
          aria-label={etiqueta}
        />
        <Input
          value={actual}
          maxLength={7}
          onChange={(e) => {
            const v = e.target.value.trim();
            // Se acepta lo que se escribe pero solo se guarda un hex completo:
            // así se puede tipear "#8a6" sin que la previa parpadee en cada
            // tecla con colores a medio escribir.
            onCambio(/^#[0-9a-fA-F]{6}$/.test(v) ? v.toLowerCase() : valor);
          }}
          className="max-w-[120px] font-mono text-xs uppercase"
        />
        {valor && (
          <button
            type="button"
            onClick={() => onCambio(null)}
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            volver al de la plantilla
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Las imágenes y el color de la marca.
 *
 * POR QUÉ VIVEN ACÁ Y NO EN «EL NEGOCIO»
 * ──────────────────────────────────────
 * Estaban en la pestaña de al lado, con los datos de contacto, y la FORMA del
 * logo estaba acá. Elegir la forma en una pantalla y subir la imagen en otra
 * es lo que hizo que el recorte no coincidiera nunca con el resultado: se
 * encuadraba a ciegas.
 *
 * Ahora el que sube el logo tiene la forma al lado, el recorte se hace con
 * ESA forma, y la previa del costado le muestra el resultado. Las tres cosas
 * en el mismo lugar, que es donde estaba el error.
 *
 * «El negocio» se queda con lo que es texto: dirección, teléfono, email.
 */
export interface MarcaEditable {
  logo_url: string | null;
  portada_url: string | null;
  color_marca: string | null;
  onLogo: (url: string | null) => void;
  onPortada: (url: string | null) => void;
  onColor: (hex: string | null) => void;
}

export function PanelLook({
  tema,
  acentoNegocio,
  marca,
  onCambio,
}: {
  tema: TemaVidriera;
  acentoNegocio: string | null;
  /** Logo, portada y color. Opcional: sin esto el panel es solo el look. */
  marca?: MarcaEditable;
  onCambio: (t: TemaVidriera) => void;
}) {
  const t = normalizarTema(tema);
  const base = PLANTILLAS[t.plantilla === "propio" ? "claro" : t.plantilla] ?? PLANTILLAS.claro;

  function set<K extends keyof TemaVidriera>(clave: K, valor: TemaVidriera[K]) {
    onCambio({ ...t, [clave]: valor });
  }

  /**
   * Elegir una plantilla LIMPIA los ajustes finos.
   *
   * Sin esto, alguien que probó un fondo bordó y después elige «Bosque» se
   * queda con el bordó encima del verde y concluye que las plantillas no
   * funcionan. Una plantilla tiene que ser un punto de partida limpio; para
   * eso está el aviso de más abajo.
   */
  function elegirPlantilla(p: Exclude<Plantilla, "propio">) {
    onCambio({
      ...t,
      plantilla: p,
      fondo_color: null,
      fondo_color_2: null,
      titulos: PLANTILLAS[p].titulos,
    });
  }

  return (
    <div className="space-y-8">
      {/* ── Plantillas ─────────────────────────────────────────────── */}
      <section>
        <h3 className="font-semibold">Plantillas</h3>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Un look completo en un toque. Después podés ajustar lo que quieras.
        </p>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {(Object.keys(PLANTILLAS) as Exclude<Plantilla, "propio">[]).map((clave) => {
            const p = PLANTILLAS[clave];
            const elegida = t.plantilla === clave;
            const muestra = estilosDe(
              { ...t, plantilla: clave, fondo_color: null, fondo_color_2: null, titulos: p.titulos },
              acentoNegocio,
            );
            return (
              <button
                key={clave}
                type="button"
                onClick={() => elegirPlantilla(clave)}
                className={`tarjeta tarjeta-viva overflow-hidden p-0 text-left ${
                  elegida ? "tarjeta-elegida" : ""
                }`}
              >
                {/* La miniatura se pinta con el MISMO estilosDe() que la
                    página real: si mostrara colores aproximados, elegir por
                    la miniatura sería elegir a ciegas. */}
                <div
                  className="flex h-24 flex-col items-center justify-center gap-2"
                  style={{ ...muestra.fondo, color: muestra.texto }}
                >
                  <span
                    className="text-base font-bold leading-none"
                    style={{ fontFamily: muestra.familiaTitulos }}
                  >
                    Aa
                  </span>
                  <span
                    className="px-4 py-1 text-[9px] font-semibold"
                    style={muestra.boton}
                  >
                    Reservar
                  </span>
                </div>
                <div className="flex items-center justify-between px-3 py-2">
                  <span className="text-xs font-medium">{p.nombre}</span>
                  {elegida && <Check className="h-3.5 w-3.5 text-primary" />}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* ── Ajustes finos ──────────────────────────────────────────── */}
      <section className="space-y-5 border-t pt-6">
        <div>
          <h3 className="font-semibold">Ajustes finos</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Opcional. Si tocás un color, elegir otra plantilla lo vuelve a
            dejar como venía.
          </p>
        </div>

        {marca && <BloqueMarca marca={marca} tema={t} onCambio={onCambio} />}

        <Elegir<FondoTipo>
          etiqueta="Fondo"
          valor={t.fondo_tipo}
          opciones={[
            { valor: "solido", label: "Sólido" },
            { valor: "gradiente", label: "Gradiente" },
            { valor: "patron", label: "Patrón" },
          ]}
          onElegir={(v) => set("fondo_tipo", v)}
        />

        <Color
          etiqueta="Color de fondo"
          valor={t.fondo_color}
          porDefecto={base.fondo}
          onCambio={(v) => set("fondo_color", v)}
        />

        {t.fondo_tipo === "gradiente" && (
          <Color
            etiqueta="Segundo color del gradiente"
            valor={t.fondo_color_2}
            porDefecto={base.fondo2}
            onCambio={(v) => set("fondo_color_2", v)}
          />
        )}

        <Elegir<BotonForma>
          etiqueta="Forma de los botones"
          valor={t.boton_forma}
          opciones={[
            { valor: "recto", label: "Recto" },
            { valor: "suave", label: "Suave" },
            { valor: "medio", label: "Medio" },
            { valor: "pildora", label: "Píldora" },
          ]}
          onElegir={(v) => set("boton_forma", v)}
        />

        <Elegir<BotonEstilo>
          etiqueta="Estilo de los botones"
          valor={t.boton_estilo}
          opciones={[
            { valor: "solido", label: "Sólido" },
            { valor: "contorno", label: "Contorno" },
            { valor: "sombra", label: "Con sombra" },
          ]}
          onElegir={(v) => set("boton_estilo", v)}
        />

        <Elegir<Titulos>
          etiqueta="Tipografía de los títulos"
          ayuda="El texto largo va siempre en la misma tipografía: es lo que tu cliente tiene que poder leer de un celular, en la calle."
          valor={t.titulos}
          opciones={[
            { valor: "sans", label: "Moderna" },
            { valor: "serif", label: "Clásica" },
            { valor: "display", label: "Con carácter" },
          ]}
          onElegir={(v) => set("titulos", v)}
        />

        {/* La forma y el tamaño del logo NO están acá abajo: se subieron al
            bloque de la marca, pegados al botón de subirlo. Separados, el
            dueño elegía la forma en un lado y encuadraba en otro. */}
        {!marca && (
          <div className="grid gap-5 sm:grid-cols-2">
            <Elegir<LogoForma>
              etiqueta="Forma del logo"
              valor={t.logo_forma}
              opciones={FORMAS}
              onElegir={(v) => set("logo_forma", v)}
            />
            <Elegir
              etiqueta="Tamaño del logo"
              valor={t.logo_tamano}
              opciones={[
                { valor: "grande" as const, label: "Grande" },
                { valor: "chico" as const, label: "Chico" },
              ]}
              onElegir={(v) => set("logo_tamano", v)}
            />
          </div>
        )}
      </section>
    </div>
  );
}

/** Las formas del logo, sacadas del mismo lugar que las usa todo el resto. */
const FORMAS = (Object.keys(FORMAS_DE_LOGO) as LogoForma[]).map((f) => ({
  valor: f,
  label: FORMAS_DE_LOGO[f].etiqueta,
}));

/**
 * Logo, portada y color de marca, con la forma del logo al lado.
 *
 * La previa del logo se dibuja con la MISMA geometría que la página real
 * (`formaDelLogo`), así que lo que se ve acá es lo que va a ver el cliente.
 * Antes esta previa era un círculo cableado y la página un cuadrado: dos
 * respuestas distintas a la misma pregunta, en la misma pantalla.
 */
function BloqueMarca({
  marca,
  tema,
  onCambio,
}: {
  marca: MarcaEditable;
  tema: TemaVidriera;
  onCambio: (t: TemaVidriera) => void;
}) {
  const geo = formaDelLogo(tema.logo_forma);
  const ancho = tema.logo_forma === "rectangular" ? 96 : 64;
  const alto = Math.round(ancho / geo.aspecto);

  return (
    <div className="space-y-5 rounded-2xl border bg-muted/30 p-4">
      <div>
        <h4 className="text-sm font-semibold">Tu marca</h4>
        <p className="mt-0.5 text-xs text-muted-foreground">
          El logo, la portada y tu color. Elegí la forma ANTES de subir el
          logo: el recorte se hace con esa forma.
        </p>
      </div>

      {/* ── Logo ──────────────────────────────────────────────────── */}
      <div className="space-y-2.5">
        <Label className="text-xs text-muted-foreground">Foto de perfil (logo)</Label>
        <div className="flex flex-wrap items-center gap-3">
          <div
            className="shrink-0 overflow-hidden border bg-card"
            style={{ width: ancho, height: alto, borderRadius: geo.radio }}
          >
            {marca.logo_url ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={urlDeImagen(marca.logo_url)}
                alt="Logo"
                className="h-full w-full"
                style={{ objectFit: geo.ajuste }}
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
                sin logo
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <SubirImagen
              proposito="logo"
              size="sm"
              etiqueta={marca.logo_url ? "Cambiar" : "Subir logo"}
              // ACÁ está el arreglo: el recorte usa la forma elegida, no un
              // círculo cableado. Sin esto, alguien con «Cuadrado» encuadraba
              // adentro de un círculo y después le aparecían las esquinas.
              forma={{
                aspecto: geo.aspecto,
                redondo: geo.redondo,
                ayuda: geo.ayuda,
              }}
              onSubida={(url) => marca.onLogo(url)}
            />
            {marca.logo_url && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => marca.onLogo(null)}
              >
                Quitar
              </Button>
            )}
          </div>
        </div>

        <Elegir<LogoForma>
          etiqueta="Forma"
          ayuda={geo.ayuda}
          valor={tema.logo_forma}
          opciones={FORMAS}
          onElegir={(v) => onCambio({ ...tema, logo_forma: v })}
        />
        <Elegir
          etiqueta="Tamaño"
          valor={tema.logo_tamano}
          opciones={[
            { valor: "grande" as const, label: "Grande" },
            { valor: "chico" as const, label: "Chico" },
          ]}
          onElegir={(v) => onCambio({ ...tema, logo_tamano: v })}
        />
        {marca.logo_url && (
          <p className="text-xs text-muted-foreground">
            Si cambiás la forma, volvé a subir el logo para encuadrarlo de
            nuevo — el que está guardado se recortó con la forma anterior.
          </p>
        )}
      </div>

      {/* ── Portada ───────────────────────────────────────────────── */}
      <div className="space-y-2.5 border-t pt-4">
        <Label className="text-xs text-muted-foreground">Foto de portada</Label>
        <div className="flex flex-wrap items-center gap-3">
          {marca.portada_url ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={urlDeImagen(marca.portada_url)}
              alt="Portada"
              className="h-14 w-24 shrink-0 rounded-lg border object-cover"
            />
          ) : (
            <div className="flex h-14 w-24 shrink-0 items-center justify-center rounded-lg border bg-card text-[10px] text-muted-foreground">
              sin portada
            </div>
          )}
          <div className="flex flex-wrap gap-1.5">
            <SubirImagen
              proposito="portada"
              size="sm"
              etiqueta={marca.portada_url ? "Cambiar" : "Subir portada"}
              onSubida={(url) => marca.onPortada(url)}
            />
            {marca.portada_url && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => marca.onPortada(null)}
              >
                Quitar
              </Button>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Va de fondo en la cabecera, con el nombre y los botones encima. Una
          foto del local en horizontal, de 1600&nbsp;px de ancho o más. Si la
          dejás vacía, la cabecera queda lisa.
        </p>
      </div>

      {/* ── Color de marca ────────────────────────────────────────── */}
      <div className="border-t pt-4">
        <Color
          etiqueta="Color de marca"
          valor={marca.color_marca}
          porDefecto="#00d4aa"
          onCambio={marca.onColor}
        />
        <p className="mt-1.5 text-xs text-muted-foreground">
          Pinta los botones y los detalles de tu página. Es el único color que
          la plantilla NO te pisa: es tuyo.
        </p>
      </div>
    </div>
  );
}
