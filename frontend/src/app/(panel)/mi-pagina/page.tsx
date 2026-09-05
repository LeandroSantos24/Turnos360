"use client";

/**
 * Mi página (/mi-pagina). El dueño edita el contenido de su landing pública:
 * sobre nosotros, dirección, contacto, logo, color, horarios (display), redes,
 * galería de fotos y las fotos del equipo. Arriba de todo, el link público
 * para compartir. Solo dueño (RequiereDueno + gate_dueno en el backend).
 *
 * Nota de estilo: NO usamos components/ui/card.tsx (está escrito con sintaxis
 * de Tailwind 4 y este proyecto usa Tailwind 3, así que sus paddings no
 * generan CSS). Seguimos el patrón del resto del panel: divs con
 * rounded-2xl + border + bg-card.
 */

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Save,
  Copy,
  Check,
  ExternalLink,
  X,
  Globe,
  Palette,
  Store,
  Share2,
  Images,
  Users,
  Clock,
  Wallet,
  Link as LinkIcon,
} from "lucide-react";

import {
  obtenerLanding,
  guardarLanding,
  obtenerConfigEmpresa,
  obtenerSenas,
  guardarSenas,
  probarSenas,
  type SenasConfig,
  LandingConfig,
  HorariosAtencion,
  Franja,
  Redes,
} from "@/lib/empresa-api";
import { listarRecursos, editarRecurso, Recurso } from "@/lib/recursos-api";
import { listarServicios } from "@/lib/servicios-api";
import { ApiError } from "@/lib/api";
import { SubirImagen } from "@/components/subir-imagen";
import { RequiereDueno } from "@/components/requiere-rol";
import { normalizarTema } from "@/lib/tema-vidriera";
import { PanelLook } from "./panel-look";
import { VistaPrevia } from "./vista-previa";
import {
  IconoInstagram,
  IconoFacebook,
  IconoLinkedin,
  IconoTiktok,
  type IconoRed,
} from "@/components/iconos-redes";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;
const MAX_FOTOS = 12;

type SeccionId =
  | "look"
  | "info"
  | "redes"
  | "galeria"
  | "equipo"
  | "horarios"
  | "senas"
  | "link";

/**
 * Las secciones del editor, agrupadas por lo que resuelven.
 *
 * El orden es el del impacto: primero EL LOOK —un toque y la página cambia
 * entera— y recién después los datos. Al revés, el que entra por primera vez
 * se topa con seis campos de texto antes de ver que la página puede quedar
 * linda, y se va pensando que esto es un formulario más.
 */
const GRUPOS_EDITOR: {
  titulo: string;
  items: { id: SeccionId; label: string; icono: typeof Palette }[];
}[] = [
  {
    titulo: "El look",
    items: [{ id: "look", label: "Look y colores", icono: Palette }],
  },
  {
    titulo: "Tu información",
    items: [
      { id: "info", label: "El negocio", icono: Store },
      { id: "redes", label: "Redes y links", icono: Share2 },
      { id: "galeria", label: "Galería", icono: Images },
      { id: "equipo", label: "Quiénes atienden", icono: Users },
      { id: "horarios", label: "Horarios", icono: Clock },
    ],
  },
  {
    titulo: "Cómo cobrás",
    items: [{ id: "senas", label: "Señas", icono: Wallet }],
  },
  {
    titulo: "Compartir",
    items: [{ id: "link", label: "Tu link y tu QR", icono: LinkIcon }],
  },
];

const DIAS: { clave: string; label: string }[] = [
  { clave: "lun", label: "Lunes" },
  { clave: "mar", label: "Martes" },
  { clave: "mie", label: "Miércoles" },
  { clave: "jue", label: "Jueves" },
  { clave: "vie", label: "Viernes" },
  { clave: "sab", label: "Sábado" },
  { clave: "dom", label: "Domingo" },
];

const REDES: {
  clave: keyof Redes;
  label: string;
  placeholder: string;
  Icono: IconoRed;
}[] = [
  { clave: "instagram", label: "Instagram", placeholder: "usuario o link", Icono: IconoInstagram },
  { clave: "facebook", label: "Facebook", placeholder: "link a tu página", Icono: IconoFacebook },
  { clave: "tiktok", label: "TikTok", placeholder: "@usuario", Icono: IconoTiktok },
  { clave: "linkedin", label: "LinkedIn", placeholder: "link a tu perfil", Icono: IconoLinkedin },
  { clave: "sitio_web", label: "Sitio web", placeholder: "https://…", Icono: Globe },
];

const VACIO: LandingConfig = {
  descripcion: null,
  direccion: null,
  telefono_publico: null,
  email_publico: null,
  logo_url: null,
  portada_url: null,
  color_marca: null,
  horarios_atencion: null,
  redes: {},
  galeria: [],
};

/** Tarjeta de sección con el estilo del panel (rounded-2xl + bg-card). */
function Seccion({
  titulo,
  descripcion,
  className = "",
  children,
}: {
  titulo: string;
  descripcion?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`rounded-2xl border bg-card p-5 ${className}`}>
      <h2 className="text-base font-bold" style={SYNE}>
        {titulo}
      </h2>
      {descripcion && (
        <p className="mt-1 text-sm text-muted-foreground">{descripcion}</p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** Editor de horarios visibles (display). Por día: abierto/cerrado + 1-2 franjas. */
function HorariosEditor({
  value,
  onChange,
}: {
  value: HorariosAtencion;
  onChange: (h: HorariosAtencion) => void;
}) {
  const franjasDe = (clave: string): Franja[] => value[clave] ?? [];
  const abierto = (clave: string) => franjasDe(clave).length > 0;

  function toggle(clave: string, on: boolean) {
    onChange({ ...value, [clave]: on ? [["09:00", "19:00"]] : [] });
  }
  function setHora(clave: string, i: number, extremo: 0 | 1, hora: string) {
    const franjas = franjasDe(clave).map((f, j) => {
      if (j !== i) return f;
      const copia: Franja = [f[0], f[1]];
      copia[extremo] = hora;
      return copia;
    });
    onChange({ ...value, [clave]: franjas });
  }
  function agregarFranja(clave: string) {
    const franjas = franjasDe(clave);
    // La franja nueva arranca donde termina la última, para no pisarse.
    const ultimaFin = franjas.length ? franjas[franjas.length - 1][1] : "16:00";
    const desde = ultimaFin < "20:00" ? ultimaFin : "20:00";
    onChange({ ...value, [clave]: [...franjas, [desde, "22:00"]] });
  }
  function quitarFranja(clave: string, i: number) {
    onChange({ ...value, [clave]: franjasDe(clave).filter((_, j) => j !== i) });
  }

  /** Horas 00 a 23, en punto y y media. */
  const HORAS: string[] = [];
  for (let h = 0; h < 24; h++) {
    HORAS.push(`${String(h).padStart(2, "0")}:00`);
    HORAS.push(`${String(h).padStart(2, "0")}:30`);
  }

  /** ¿La franja i se solapa o repite con otra del mismo día? */
  function franjaInvalida(franjas: Franja[], i: number): string | null {
    const [ini, fin] = franjas[i];
    if (ini >= fin) return "El horario de fin debe ser mayor al de inicio";
    for (let j = 0; j < franjas.length; j++) {
      if (j === i) continue;
      const [ini2, fin2] = franjas[j];
      // Se pisan si una empieza antes de que la otra termine (y viceversa).
      if (ini < fin2 && ini2 < fin) return "Esta franja se pisa con otra del mismo día";
    }
    return null;
  }

  return (
    <div className="grid items-start gap-2 lg:grid-cols-2">
      {DIAS.map((d) => {
        const franjas = franjasDe(d.clave);
        return (
          <div key={d.clave} className="rounded-xl border p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{d.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {abierto(d.clave) ? "Abierto" : "Cerrado"}
                </span>
                <Switch
                  checked={abierto(d.clave)}
                  onCheckedChange={(on) => toggle(d.clave, on)}
                />
              </div>
            </div>

            {abierto(d.clave) && (
              <div className="mt-3 space-y-2">
                {franjas.map((f, i) => {
                  const error = franjaInvalida(franjas, i);
                  return (
                    <div key={i}>
                      <div className="flex items-center gap-2">
                        <select
                          value={f[0]}
                          onChange={(e) => setHora(d.clave, i, 0, e.target.value)}
                          className={`h-9 w-24 rounded-md border bg-background px-2 text-sm ${
                            error ? "border-red-500" : ""
                          }`}
                        >
                          {HORAS.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                        <span className="text-sm text-muted-foreground">a</span>
                        <select
                          value={f[1]}
                          onChange={(e) => setHora(d.clave, i, 1, e.target.value)}
                          className={`h-9 w-24 rounded-md border bg-background px-2 text-sm ${
                            error ? "border-red-500" : ""
                          }`}
                        >
                          {HORAS.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                        {franjas.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => quitarFranja(d.clave, i)}
                          >
                            Quitar
                          </Button>
                        )}
                      </div>
                      {error && (
                        <p className="mt-1 text-xs text-red-500">{error}</p>
                      )}
                    </div>
                  );
                })}
                {franjas.length < 2 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => agregarFranja(d.clave)}
                  >
                    + Agregar franja (ej. tarde/siesta)
                  </Button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Card con el link público del negocio, para copiar y compartir. */
function LinkPublico({ slug }: { slug: string | null }) {
  const [copiado, setCopiado] = useState(false);
  const url = useMemo(() => {
    if (!slug) return null;
    const origen =
      typeof window !== "undefined" ? window.location.origin : "https://turnos360.com.ar";
    return `${origen}/${slug}`;
  }, [slug]);

  async function copiar() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      toast.success("Link copiado");
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      toast.error("No se pudo copiar. Seleccionalo y copialo a mano.");
    }
  }

  return (
    <Seccion
      titulo="Tu link público"
      descripcion="Compartilo en Instagram, WhatsApp o donde quieras: tus clientes ven tu página y reservan solos."
      className="lg:col-span-2"
    >
      {url ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <code className="flex-1 truncate rounded-lg border bg-muted/50 px-3 py-2 font-mono text-sm">
            {url}
          </code>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={copiar}>
              {copiado ? (
                <Check className="mr-1.5 h-4 w-4" />
              ) : (
                <Copy className="mr-1.5 h-4 w-4" />
              )}
              {copiado ? "Copiado" : "Copiar"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
            >
              <ExternalLink className="mr-1.5 h-4 w-4" />
              Abrir
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Cargando tu link…</p>
      )}
    </Seccion>
  );
}

/** Galería: URLs de fotos con vista previa. Se guarda con el botón global. */
function GaleriaEditor({
  fotos,
  onChange,
}: {
  fotos: string[];
  onChange: (fotos: string[]) => void;
}) {
  function agregar(url: string) {
    if (!url) return;
    if (fotos.length >= MAX_FOTOS) {
      toast.error(`Máximo ${MAX_FOTOS} fotos`);
      return;
    }
    if (fotos.includes(url)) {
      toast.error("Esa foto ya está en la galería");
      return;
    }
    onChange([...fotos, url]);
  }
  function quitar(i: number) {
    onChange(fotos.filter((_, j) => j !== i));
  }

  return (
    <Seccion
      titulo="Galería de fotos"
      descripcion={`Fotos de tus trabajos o del local (hasta ${MAX_FOTOS}). Estas van completas, sin recortar: se ven grandes en tu página.`}
      className="lg:col-span-2"
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <SubirImagen
            proposito="galeria"
            etiqueta="Agregar foto"
            onSubida={agregar}
          />
          <span className="text-xs text-muted-foreground">
            {fotos.length} de {MAX_FOTOS}
          </span>
        </div>

        {fotos.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Todavía no agregaste fotos. La sección Galería no se muestra en tu página hasta
            que haya al menos una.
          </p>
        ) : (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {fotos.map((url, i) => (
              <div
                key={`${url}-${i}`}
                className="group relative aspect-square overflow-hidden rounded-xl border bg-muted"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt={`Foto ${i + 1}`}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
                <button
                  type="button"
                  onClick={() => quitar(i)}
                  className="absolute right-1.5 top-1.5 rounded-full bg-black/60 p-1 text-white opacity-0 transition-opacity hover:bg-black/80 group-hover:opacity-100"
                  aria-label="Quitar foto"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Seccion>
  );
}

/**
 * Fotos del equipo: una fila por profesional.
 *
 * ANTES ERA UN CAMPO PARA PEGAR UNA URL
 * ─────────────────────────────────────
 * Y eso no es una función incompleta: es una que no existe. Leandro lo dijo
 * probando el alta —«no me deja cargar la foto de los peluqueros»— y tenía
 * razón. Un dueño de barbería no tiene las fotos de su equipo publicadas en
 * ningún lado con una URL a mano; las tiene en el celular. Pedirle una URL es
 * pedirle que primero resuelva un problema que no sabe que tiene.
 *
 * Además la fila se rompía: con el nombre a la izquierda, el campo al medio y
 * el botón a la derecha, dentro de una grilla de dos columnas no entraba nada
 * y «Guardar» terminaba encima del nombre.
 */
function EquipoEditor({
  recursos,
  onGuardado,
}: {
  recursos: Recurso[];
  onGuardado: (r: Recurso) => void;
}) {
  const [guardandoId, setGuardandoId] = useState<number | null>(null);

  async function fijarFoto(r: Recurso, url: string | null) {
    setGuardandoId(r.id);
    try {
      onGuardado(await editarRecurso(r.id, { foto_url: url }));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardandoId(null);
    }
  }

  return (
    <Seccion
      titulo="Fotos del equipo"
      descripcion="La foto de cada profesional aparece en la sección Equipo de tu página. Sin foto, se muestra la inicial del nombre."
      className="lg:col-span-2"
    >
      {recursos.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No hay profesionales activos. Crealos en la pantalla Recursos y van a aparecer acá.
        </p>
      ) : (
        <div className="grid items-start gap-3 lg:grid-cols-2">
          {recursos.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 rounded-xl border p-3"
            >
              <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full border bg-muted">
                {r.foto_url ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={r.foto_url}
                    alt={r.nombre}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-sm font-semibold text-muted-foreground">
                    {r.nombre.charAt(0).toUpperCase()}
                  </div>
                )}
              </div>

              <span className="min-w-0 flex-1 truncate text-sm font-medium">
                {r.nombre}
              </span>

              {/* Los botones no crecen: son lo último que puede robar espacio
                  al nombre, que es lo que identifica la fila. */}
              <div className="flex shrink-0 items-center gap-1.5">
                <SubirImagen
                  proposito="avatar"
                  size="sm"
                  etiqueta={r.foto_url ? "Cambiar" : "Subir foto"}
                  onSubida={(url) => fijarFoto(r, url)}
                />
                {r.foto_url && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={guardandoId === r.id}
                    onClick={() => fijarFoto(r, null)}
                  >
                    Quitar
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Seccion>
  );
}

function ContenidoMiPagina() {
  const [form, setForm] = useState<LandingConfig | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [seccion, setSeccion] = useState<SeccionId>("look");
  const [nombreNegocio, setNombreNegocio] = useState("");
  const [servicioEjemplo, setServicioEjemplo] = useState<
    { nombre: string; precio: number | null; duracion_min: number } | null
  >(null);

  useEffect(() => {
    Promise.all([
      obtenerLanding(),
      obtenerConfigEmpresa().catch(() => null),
      listarRecursos().catch(() => null),
      // Un servicio REAL para la previa. Con uno inventado, lo que el dueño
      // juzga no es su página: es una maqueta con datos de otro negocio.
      listarServicios().catch(() => null),
    ])
      .then(([data, config, pagina, servicios]) => {
        setForm({ ...VACIO, ...data, redes: data.redes ?? {}, galeria: data.galeria ?? [] });
        if (config) {
          setSlug(config.slug);
          setNombreNegocio(config.nombre);
        }
        if (pagina)
          setRecursos(pagina.items.filter((r) => r.tipo === "persona" && r.activo));
        const primero = servicios?.items?.find((s) => s.activo && s.agendable);
        if (primero) {
          setServicioEjemplo({
            nombre: primero.nombre,
            precio: primero.precio ?? null,
            duracion_min: primero.duracion_min,
          });
        }
      })
      .catch((err) =>
        toast.error(err instanceof ApiError ? err.message : "Error al cargar"),
      )
      .finally(() => setCargando(false));
  }, []);

  // Solo previsualizamos URLs http(s) completas: mientras el dueño está
  // pegando el link, el valor intermedio no es una imagen y el recuadro
  // quedaría roto.
  const portadaPrevia =
    form?.portada_url && /^https?:\/\/[^\s"'()<>]+$/i.test(form.portada_url.trim())
      ? form.portada_url.trim()
      : null;

  function set<K extends keyof LandingConfig>(clave: K, valor: LandingConfig[K]) {
    setForm((f) => (f ? { ...f, [clave]: valor } : f));
  }
  function setRed(clave: keyof Redes, valor: string) {
    setForm((f) => (f ? { ...f, redes: { ...f.redes, [clave]: valor } } : f));
  }

  async function guardar() {
    if (!form) return;

    // El backend ahora rechaza URLs de imagen que no sean http(s). Validamos
    // acá primero para dar un mensaje entendible en vez del 422 de Pydantic.
    const urlImagenOk = (u: string | null) => {
      const t = (u ?? "").trim();
      return t === "" || /^https?:\/\/[^\s"'()<>]+$/i.test(t);
    };
    if (!urlImagenOk(form.logo_url)) {
      toast.error("El link del logo tiene que empezar con https://");
      return;
    }
    if (!urlImagenOk(form.portada_url)) {
      toast.error("El link de la portada tiene que empezar con https://");
      return;
    }

    setGuardando(true);
    const limpio = (s: string | null) => {
      const t = (s ?? "").trim();
      return t === "" ? null : t;
    };
    const redesLimpias: Redes = {};
    for (const [k, v] of Object.entries(form.redes)) {
      if ((v ?? "").trim() !== "") redesLimpias[k] = (v as string).trim();
    }
    const tieneHorarios =
      !!form.horarios_atencion &&
      Object.values(form.horarios_atencion).some((f) => f.length > 0);

    // No dejar guardar franjas de atención pisadas o mal cargadas.
    if (form.horarios_atencion) {
      for (const franjas of Object.values(form.horarios_atencion)) {
        for (let i = 0; i < franjas.length; i++) {
          const [ini, fin] = franjas[i];
          if (ini >= fin) {
            toast.error("Revisá los horarios de atención: hay una franja con fin anterior al inicio.");
            return;
          }
          for (let j = i + 1; j < franjas.length; j++) {
            const [ini2, fin2] = franjas[j];
            if (ini < fin2 && ini2 < fin) {
              toast.error("Revisá los horarios de atención: hay franjas del mismo día que se pisan.");
              return;
            }
          }
        }
      }
    }

    const payload: LandingConfig = {
      descripcion: limpio(form.descripcion),
      direccion: limpio(form.direccion),
      telefono_publico: limpio(form.telefono_publico),
      email_publico: limpio(form.email_publico),
      logo_url: limpio(form.logo_url),
      portada_url: limpio(form.portada_url),
      color_marca: limpio(form.color_marca),
      horarios_atencion: tieneHorarios ? form.horarios_atencion : null,
      redes: redesLimpias,
      galeria: form.galeria.map((u) => u.trim()).filter(Boolean).slice(0, MAX_FOTOS),
      tema: normalizarTema(form.tema),
    };

    try {
      const guardado = await guardarLanding(payload);
      setForm({
        ...VACIO,
        ...guardado,
        redes: guardado.redes ?? {},
        galeria: guardado.galeria ?? [],
      });
      toast.success("Página actualizada");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando || !form) {
    return <div className="p-8 text-sm text-muted-foreground">Cargando…</div>;
  }

  return (
    <div className="superficie min-h-full">
      {/* ── Cabecera ───────────────────────────────────────────────── */}
      <div className="border-b bg-card/60 px-6 py-5 backdrop-blur sm:px-8">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="titulo-pantalla">
              Tu <b>página</b>.
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Lo que ven tus clientes cuando abren tu link. Elegí el look, cargá
              tus datos y mirá cómo va quedando a la derecha.
            </p>
          </div>
          <Button onClick={guardar} disabled={guardando} className="shrink-0">
            <Save className="mr-1.5 h-4 w-4" />
            {guardando ? "Guardando…" : "Publicar cambios"}
          </Button>
        </div>
      </div>

      {/*
        TRES COLUMNAS: qué editar · el editor · cómo queda.

        Antes era un formulario largo en dos columnas, con un link «Abrir»
        arriba: para ver el efecto de un cambio había que guardar, cambiar de
        pestaña, recargar y volver. Con ese costo por ajuste, nadie prueba
        nada — se elige el primer color que suena bien y no se toca nunca más.

        La previa está a la derecha y se actualiza mientras se escribe.
      */}
      <div className="mx-auto grid max-w-[1200px] gap-6 p-6 sm:p-8 lg:grid-cols-[210px_minmax(0,1fr)_340px]">
        {/* Rail de secciones */}
        <nav className="lg:sticky lg:top-6 lg:self-start">
          <div className="flex gap-1.5 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
            {GRUPOS_EDITOR.map((grupo) => (
              <div key={grupo.titulo} className="contents lg:block">
                <p className="mb-1.5 mt-4 hidden text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground lg:block">
                  {grupo.titulo}
                </p>
                {grupo.items.map((s) => {
                  const activa = seccion === s.id;
                  const Icono = s.icono;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setSeccion(s.id)}
                      className={`flex w-full shrink-0 items-center gap-2.5 whitespace-nowrap rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${
                        activa
                          ? "bg-primary/10 font-semibold text-primary"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      <Icono className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{s.label}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </nav>

        {/* Panel de la sección elegida */}
        <div className="min-w-0 space-y-5">
          {seccion === "link" && <LinkPublico slug={slug} />}

          {seccion === "look" && (
            <div className="tarjeta p-5">
              <PanelLook
                tema={normalizarTema(form.tema)}
                acentoNegocio={form.color_marca ?? null}
                onCambio={(nuevo) => set("tema", nuevo)}
              />
            </div>
          )}

          {seccion === "info" && (
  <Seccion
    titulo="Información del negocio"
    descripcion="Lo básico que ve el cliente al entrar."
  >
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="descripcion">Sobre nosotros</Label>
        <Textarea
          id="descripcion"
          rows={4}
          placeholder="Contá qué hace especial a tu negocio…"
          value={form.descripcion ?? ""}
          onChange={(e) => set("descripcion", e.target.value)}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="direccion">Dirección</Label>
        <Input
          id="direccion"
          placeholder="San Martín 1234, Mendoza"
          value={form.direccion ?? ""}
          onChange={(e) => set("direccion", e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          De acá salen el mapa y el botón &ldquo;Cómo llegar&rdquo;.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="tel">Teléfono / WhatsApp</Label>
          <Input
            id="tel"
            placeholder="+54 9 261 123 4567"
            value={form.telefono_publico ?? ""}
            onChange={(e) => set("telefono_publico", e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="hola@tunegocio.com"
            value={form.email_publico ?? ""}
            onChange={(e) => set("email_publico", e.target.value)}
          />
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Logo</Label>
          <div className="flex items-center gap-3">
            <div className="h-14 w-14 shrink-0 overflow-hidden rounded-full border bg-muted">
              {form.logo_url ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={form.logo_url} alt="Logo" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                  sin logo
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              <SubirImagen
                proposito="logo"
                size="sm"
                etiqueta={form.logo_url ? "Cambiar" : "Subir logo"}
                onSubida={(url) => set("logo_url", url)}
              />
              {form.logo_url && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => set("logo_url", "")}
                >
                  Quitar
                </Button>
              )}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Se ve en un círculo arriba de tu página. Al subirlo elegís qué parte
            se ve.
          </p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="color">Color de marca</Label>
          <div className="flex items-center gap-2">
            <input
              id="color"
              type="color"
              className="h-9 w-12 cursor-pointer rounded-md border bg-transparent"
              value={form.color_marca ?? "#00d4aa"}
              onChange={(e) => set("color_marca", e.target.value)}
            />
            <Input
              value={form.color_marca ?? ""}
              placeholder="#00d4aa"
              onChange={(e) => set("color_marca", e.target.value)}
              className="w-32"
            />
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>Foto de portada</Label>
        <div className="flex flex-wrap items-center gap-3">
          {form.portada_url && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={form.portada_url}
              alt="Portada"
              className="h-16 w-28 shrink-0 rounded-lg border object-cover"
            />
          )}
          <div className="flex flex-wrap gap-1.5">
            <SubirImagen
              proposito="portada"
              size="sm"
              etiqueta={form.portada_url ? "Cambiar portada" : "Subir portada"}
              onSubida={(url) => set("portada_url", url)}
            />
            {form.portada_url && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => set("portada_url", "")}
              >
                Quitar
              </Button>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Se muestra de fondo en la cabecera de tu página, con el nombre y
          los botones encima. Va bien una foto del local en horizontal
          (mínimo 1600&nbsp;px de ancho). Si la dejás vacía, la cabecera
          queda blanca.
        </p>
        {portadaPrevia && (
          <div
            className="mt-2 h-32 w-full overflow-hidden rounded-xl border bg-cover bg-center"
            style={{ backgroundImage: `url(${portadaPrevia})` }}
          >
            <div className="flex h-full w-full items-end bg-gradient-to-b from-black/45 via-black/25 to-black/80 p-3">
              <span
                className="text-lg font-bold text-white"
                style={SYNE}
              >
                Así se va a ver
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  </Seccion>
          )}

          {seccion === "redes" && (
  <Seccion titulo="Redes y links" descripcion="Dejá vacío lo que no uses.">
    <div className="space-y-4">
      {REDES.map(({ clave, label, placeholder, Icono }) => (
        <div key={String(clave)} className="space-y-1.5">
          <Label htmlFor={String(clave)} className="flex items-center gap-2">
            <Icono className="h-4 w-4 text-muted-foreground" />
            {label}
          </Label>
          <Input
            id={String(clave)}
            placeholder={placeholder}
            value={form.redes[clave] ?? ""}
            onChange={(e) => setRed(clave, e.target.value)}
          />
        </div>
      ))}
    </div>
  </Seccion>
          )}

          {seccion === "galeria" && (
  <GaleriaEditor fotos={form.galeria} onChange={(g) => set("galeria", g)} />
          )}

          {seccion === "equipo" && (
  <EquipoEditor
    recursos={recursos}
    onGuardado={(actualizado) =>
      setRecursos((lista) =>
        lista.map((r) => (r.id === actualizado.id ? actualizado : r)),
      )
    }
  />
          )}

          {seccion === "horarios" && (
  <Seccion
    titulo="Horarios de atención"
    descripcion="Solo para mostrar en tu página. Los turnos reservables salen de la agenda de cada profesional."
    className="lg:col-span-2"
  >
    <HorariosEditor
      value={form.horarios_atencion ?? {}}
      onChange={(h) => set("horarios_atencion", h)}
    />
  </Seccion>
          )}

          {seccion === "senas" && <SeccionSenas />}
        </div>

        {/* Vista previa */}
        <div className="hidden lg:block">
          <VistaPrevia
            tema={normalizarTema(form.tema)}
            datos={{
              nombre: nombreNegocio,
              descripcion: form.descripcion,
              direccion: form.direccion,
              logo_url: form.logo_url,
              portada_url: portadaPrevia,
              color_marca: form.color_marca,
              servicio: servicioEjemplo,
            }}
          />
        </div>
      </div>

      <div className="px-6 pb-10 sm:px-8 lg:hidden">
        {/* En pantallas chicas la previa no entra al costado: va abajo, donde
            igual se ve al scrollear. Esconderla del todo dejaría al que edita
            desde el celular sin la mitad de la pantalla. */}
        <VistaPrevia
          tema={normalizarTema(form.tema)}
          datos={{
            nombre: nombreNegocio,
            descripcion: form.descripcion,
            direccion: form.direccion,
            logo_url: form.logo_url,
            portada_url: portadaPrevia,
            color_marca: form.color_marca,
            servicio: servicioEjemplo,
          }}
        />
      </div>
    </div>
  );
}

function SeccionSenas() {
  const [config, setConfig] = useState<SenasConfig | null>(null);
  const [modo, setModo] = useState<"ninguno" | "sena" | "total">("ninguno");
  const [monto, setMonto] = useState("");
  const [token, setToken] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [probando, setProbando] = useState(false);

  useEffect(() => {
    obtenerSenas()
      .then((c) => {
        setConfig(c);
        setModo(c.cobro_modo ?? (c.sena_activa ? "sena" : "ninguno"));
        setMonto(c.sena_monto != null ? String(c.sena_monto) : "");
      })
      .catch(() => toast.error("No se pudo cargar la config de señas"));
  }, []);

  async function probar() {
    setProbando(true);
    try {
      const r = await probarSenas();
      setConfig((c) => (c ? { ...c, mp_cuenta: r.cuenta } : c));
      toast.success(`Mercado Pago responde bien · cuenta: ${r.cuenta.nombre}`);
    } catch (e) {
      // El backend manda el motivo escrito para mostrárselo tal cual.
      toast.error(e instanceof ApiError ? e.message : "No pude probar la conexión");
    } finally {
      setProbando(false);
    }
  }

  async function guardar() {
    const montoNum = monto.trim() === "" ? null : Number(monto);
    if (modo === "sena" && (!montoNum || montoNum <= 0)) {
      toast.error("Definí el monto de la seña");
      return;
    }
    if (modo !== "ninguno" && !config?.mp_conectado && !token.trim()) {
      toast.error("Pegá el Access Token de tu cuenta de Mercado Pago");
      return;
    }
    setGuardando(true);
    try {
      const nuevo = await guardarSenas({
        cobro_modo: modo,
        sena_activa: modo !== "ninguno",
        sena_monto: montoNum,
        ...(token.trim() ? { mp_access_token: token.trim() } : {}),
      });
      setConfig(nuevo);
      setToken("");
      toast.success("Señas guardadas");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Seccion
      titulo="Señas con Mercado Pago"
      descripcion="Cobrá una seña al reservar online: el que paga, aparece. La plata va directo a TU cuenta de Mercado Pago (la comisión de MP la absorbe el negocio)."
      className="lg:col-span-2"
    >
      <div className="space-y-4">
        {/* Qué cuenta quedó conectada, y un botón para confirmar que
            sigue andando. Antes acá decía "conectada ✓" sin haber verificado
            nada: si el dueño pegaba la Public Key en vez del Access Token,
            el tilde verde aparecía igual y el problema salía a la luz recién
            cuando un cliente no podía pagar. */}
        <div className="flex flex-wrap items-center gap-2">
          {config?.mp_conectado ? (
            <div className="flex-1 rounded-xl border bg-muted/40 p-3 text-xs">
              <p className="font-medium text-foreground">
                Conectado a Mercado Pago ✓
              </p>
              {config.mp_cuenta ? (
                <p className="mt-0.5 text-muted-foreground">
                  Cuenta: <strong>{config.mp_cuenta.nombre}</strong>
                  {config.mp_cuenta.email ? ` · ${config.mp_cuenta.email}` : ""}
                </p>
              ) : (
                <p className="mt-0.5 text-muted-foreground">
                  Se conectó antes de que verificáramos la cuenta. Tocá
                  &ldquo;Probar conexión&rdquo; para confirmar que anda.
                </p>
              )}
            </div>
          ) : (
            <p className="flex-1 text-xs text-muted-foreground">
              Todavía sin conectar Mercado Pago
            </p>
          )}
          {config?.mp_conectado && (
            <Button
              variant="outline"
              size="sm"
              onClick={probar}
              disabled={probando}
            >
              {probando ? "Probando…" : "Probar conexión"}
            </Button>
          )}
        </div>

        {/* Qué se cobra al reservar: lo elige el negocio. */}
        <div className="grid gap-2 sm:grid-cols-3">
          {(
            [
              { id: "ninguno", t: "No cobrar nada", d: "Reservan sin pagar" },
              { id: "sena", t: "Cobrar una seña", d: "Un monto fijo" },
              { id: "total", t: "Cobrar el total", d: "El precio del servicio" },
            ] as const
          ).map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => setModo(o.id)}
              className={`rounded-xl border p-3 text-left transition-colors ${
                modo === o.id
                  ? "border-primary bg-primary/5"
                  : "hover:border-muted-foreground/40"
              }`}
            >
              <p className="text-sm font-medium">{o.t}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{o.d}</p>
            </button>
          ))}
        </div>

        {modo !== "ninguno" && (
          <div className="grid gap-4 sm:grid-cols-2">
            {modo === "sena" ? (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Monto de la seña (ARS)</Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  placeholder="5000"
                  value={monto}
                  onChange={(e) => setMonto(e.target.value)}
                />
              </div>
            ) : (
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Monto a cobrar</Label>
                <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                  El precio de cada servicio
                </div>
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Access Token de Mercado Pago{config?.mp_conectado ? " (solo si querés cambiarlo)" : ""}
              </Label>
              <Input
                type="password"
                placeholder="APP_USR-…"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                autoComplete="off"
              />
              <p className="text-xs text-muted-foreground">
                Se guarda encriptado. Lo sacás de Mercado Pago → Tus integraciones →
                Credenciales de producción.
              </p>
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={guardar} disabled={guardando}>
            {guardando ? "Guardando…" : "Guardar señas"}
          </Button>
        </div>
      </div>
    </Seccion>
  );
}

export default function MiPaginaPage() {
  return (
    <RequiereDueno>
      <ContenidoMiPagina />
    </RequiereDueno>
  );
}
