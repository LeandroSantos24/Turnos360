"use client";

/**
 * Panel de empresas (/admin).
 * Lista las empresas, permite crear una nueva (con su usuario dueño) y
 * pausar/reactivar el servicio. Cada empresa enlaza a su gestión de usuarios.
 */

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Plus, Users, ExternalLink, Copy, Check, Crown } from "lucide-react";
import { toast } from "sonner";
import { useConfirmar } from "@/components/confirmar";

import {
  listarEmpresas,
  listarRubros,
  crearEmpresa,
  pausarEmpresa,
  setearSuscripcion,
  EmpresaAdmin,
  RubroAdmin,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";

const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

/**
 * Texto libre -> slug de URL.
 *
 * El parámetro `final` es el arreglo de un bug feo: recortar el guión del
 * FINAL en cada tecleo borraba el guión recién creado por el espacio, y la
 * letra siguiente quedaba pegada. Tipeando "barberia el faro" a mano salía
 * "barberiaelfaro"; pegando el mismo texto salía "barberia-el-faro". Dos
 * resultados distintos para el mismo nombre, según cómo lo hubieras escrito.
 *
 *   final = false -> mientras se tipea: conserva el guión del final.
 *   final = true  -> al guardar: recorta los guiones de las puntas.
 */
function slugify(s: string, final = false): string {
  const base = s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+/, "");
  return final ? base.replace(/-+$/, "") : base;
}

export default function AdminEmpresasPage() {
  const confirmar = useConfirmar();
  const [empresas, setEmpresas] = useState<EmpresaAdmin[]>([]);
  const [rubros, setRubros] = useState<RubroAdmin[]>([]);
  const [errorRubros, setErrorRubros] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState(false);
  const [copiadoId, setCopiadoId] = useState<number | null>(null);
  const [guardando, setGuardando] = useState(false);

  // formulario
  const [nombre, setNombre] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTocado, setSlugTocado] = useState(false);
  const [rubroId, setRubroId] = useState("");
  const [dNombre, setDNombre] = useState("");
  const [dEmail, setDEmail] = useState("");
  const [dClave, setDClave] = useState("");
  // 14 días es lo que ofrece la landing. 0 = el negocio ya arranca pagando.
  const [diasPrueba, setDiasPrueba] = useState(14);

  // Las dos cargas van por separado A PROPÓSITO. Con Promise.all, si UNA
  // fallaba se rechazaba todo y los rubros quedaban en [] — y un Select sin
  // items abre un panel vacío, que desde afuera se ve exactamente igual que
  // "el desplegable no anda". El síntoma no decía nada de la causa.
  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setEmpresas(await listarEmpresas());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar empresas");
    }
    try {
      setRubros(await listarRubros());
      setErrorRubros(null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Error al cargar los rubros";
      setErrorRubros(msg);
      toast.error(msg);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function resetForm() {
    setNombre("");
    setSlug("");
    setSlugTocado(false);
    setRubroId("");
    setDNombre("");
    setDEmail("");
    setDClave("");
    setDiasPrueba(14);
  }

  async function guardar() {
    if (
      !nombre.trim() ||
      !slugify(slug, true) ||
      !rubroId ||
      !dNombre.trim() ||
      !dEmail.trim() ||
      dClave.length < 6
    ) {
      toast.error("Completá todos los campos (la clave debe tener 6+ caracteres)");
      return;
    }
    setGuardando(true);
    try {
      await crearEmpresa({
        nombre: nombre.trim(),
        slug: slugify(slug, true),
        rubro_id: Number(rubroId),
        dueno: { nombre: dNombre.trim(), email: dEmail.trim(), clave: dClave },
        dias_prueba: diasPrueba,
      });
      toast.success("Empresa creada");
      setAbierto(false);
      resetForm();
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo crear");
    } finally {
      setGuardando(false);
    }
  }

  function linkPublico(emp: EmpresaAdmin) {
    return `${window.location.origin}/${emp.slug}`;
  }

  async function copiarLink(emp: EmpresaAdmin) {
    try {
      await navigator.clipboard.writeText(linkPublico(emp));
      setCopiadoId(emp.id);
      toast.success("Link público copiado");
      setTimeout(() => setCopiadoId(null), 2000);
    } catch {
      toast.error("No se pudo copiar");
    }
  }

  async function togglePausa(emp: EmpresaAdmin) {
    // Pausar deja al negocio entero afuera: no entra al panel y su página
    // pública de reservas deja de tomar turnos. Un switch es el control más
    // fácil de tocar sin querer.
    if (
      !(await confirmar({
        titulo: emp.activa ? `¿Pausar ${emp.nombre}?` : `¿Reactivar ${emp.nombre}?`,
        descripcion: emp.activa
          ? "Sus usuarios no van a poder entrar al panel y su página pública deja de tomar reservas."
          : "Vuelve a tener acceso al panel y su página pública vuelve a tomar reservas.",
        textoAccion: emp.activa ? "Sí, pausar" : "Sí, reactivar",
        destructivo: emp.activa,
      }))
    )
      return;
    try {
      await pausarEmpresa(emp.id, !emp.activa);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar");
    }
  }

  async function renovar30(emp: EmpresaAdmin) {
    // Esto REGALA un mes de suscripción paga desde un botón chico al lado de
    // "Ver página", sin registrar ningún pago y sin dejar rastro visible.
    if (
      !(await confirmar({
        titulo: `¿Renovar 30 días a ${emp.nombre}?`,
        descripcion:
          "Le mueve el vencimiento un mes hacia adelante SIN registrar un pago. " +
          "Si lo que querés es anotar una cuota cobrada, hacelo desde Cobranza.",
        textoAccion: "Sí, renovar 30 días",
      }))
    )
      return;
    try {
      await setearSuscripcion(emp.id, { renovar_30: true });
      toast.success(`Suscripción de ${emp.nombre} renovada por 30 días`);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo renovar");
    }
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={SYNE}>
            Empresas
          </h1>
          <p className="text-sm text-muted-foreground">
            Creá y gestioná los negocios de la plataforma.
          </p>
        </div>
        <Dialog
          open={abierto}
          onOpenChange={(o) => {
            setAbierto(o);
            if (!o) resetForm();
          }}
        >
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-1.5 h-4 w-4" /> Nueva empresa
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Nueva empresa</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Nombre del negocio
                  </label>
                  <Input
                    placeholder="Barbería La Cueva"
                    value={nombre}
                    onChange={(e) => {
                      setNombre(e.target.value);
                      if (!slugTocado) setSlug(slugify(e.target.value));
                    }}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Identificador (slug)
                  </label>
                  <Input
                    placeholder="la-cueva"
                    value={slug}
                    onChange={(e) => {
                      setSlugTocado(true);
                      setSlug(slugify(e.target.value));
                    }}
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium" htmlFor="rubro">
                  Rubro
                </label>
                {/* <select> nativo en vez del Select de la librería: este
                    campo vive adentro de un diálogo y el panel de la librería
                    se dibuja en un portal, que según el navegador puede quedar
                    detrás del overlay del modal. El nativo lo pinta el sistema
                    operativo y no puede taparlo nada. Es el único campo del
                    panel que bloquea por completo dar de alta un negocio, así
                    que acá conviene lo que no falla nunca. */}
                <select
                  id="rubro"
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm disabled:opacity-60"
                  value={rubroId}
                  disabled={rubros.length === 0}
                  onChange={(e) => setRubroId(e.target.value)}
                >
                  <option value="">
                    {rubros.length === 0 ? "Sin rubros disponibles" : "Elegí un rubro"}
                  </option>
                  {rubros.map((r) => (
                    <option key={r.id} value={String(r.id)}>
                      {r.nombre}
                    </option>
                  ))}
                </select>
                {/* Un desplegable vacío no explica nada. Estos dos mensajes
                    dicen qué pasó y qué hacer, en vez de dejar al operador
                    probando clics. */}
                {rubros.length === 0 && !cargando && (
                  <p className="mt-1.5 text-xs text-amber-600">
                    {errorRubros
                      ? `No se pudieron traer los rubros: ${errorRubros}`
                      : "No hay rubros cargados en la base. Corré el seed del catálogo: docker compose exec backend python -m app.seeds_minimo"}
                  </p>
                )}
              </div>

              <div className="rounded-xl border bg-muted/30 p-4">
                <p className="mb-3 text-sm font-semibold">Usuario dueño</p>
                <div className="space-y-3">
                  <Input
                    placeholder="Nombre del dueño"
                    value={dNombre}
                    onChange={(e) => setDNombre(e.target.value)}
                  />
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <Input
                      type="email"
                      placeholder="Email"
                      value={dEmail}
                      onChange={(e) => setDEmail(e.target.value)}
                    />
                    <Input
                      type="password"
                      placeholder="Contraseña (6+)"
                      value={dClave}
                      onChange={(e) => setDClave(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label>Período de prueba</Label>
                  <div className="flex flex-wrap gap-2">
                    {[0, 7, 14, 30].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setDiasPrueba(d)}
                        className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                          diasPrueba === d
                            ? "border-transparent bg-foreground text-background"
                            : "bg-background hover:bg-muted"
                        }`}
                      >
                        {d === 0 ? "Sin prueba" : `${d} días`}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Durante la prueba el negocio no cuenta en el MRR ni en la
                    deuda vencida, y en Cobranza aparece en azul.
                  </p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={guardar} disabled={guardando}>
                {guardando ? "Creando…" : "Crear empresa"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : empresas.length === 0 ? (
        <div className="rounded-2xl border bg-card p-10 text-center">
          <p className="text-sm text-muted-foreground">
            Todavía no hay empresas. Creá la primera con el botón de arriba.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {empresas.map((e) => (
            <div
              key={e.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card p-4"
            >
              <div className="min-w-0">
                <p className="flex items-center gap-2 font-medium">
                  {e.nombre}
                  {!e.activa && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      Pausada
                    </span>
                  )}
                  <ChipSuscripcion estado={e.estado_suscripcion} plan={e.plan} />
                </p>
                <p className="text-sm text-muted-foreground">
                  {e.rubro_nombre ?? "—"} · /{e.slug} · {e.cantidad_usuarios}{" "}
                  {e.cantidad_usuarios === 1 ? "usuario" : "usuarios"}
                  {e.suscripcion_vence && (
                    <> · vence {new Date(`${e.suscripcion_vence}T12:00:00`).toLocaleDateString("es-AR")}</>
                  )}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                <label className="mr-1 flex items-center gap-2 text-sm text-muted-foreground">
                  <Switch
                    checked={e.activa}
                    onCheckedChange={() => togglePausa(e)}
                  />
                  Activa
                </label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copiarLink(e)}
                  title="Copiar link público"
                >
                  {copiadoId === e.id ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(`/${e.slug}`, "_blank", "noopener,noreferrer")}
                >
                  <ExternalLink className="mr-1.5 h-4 w-4" /> Ver página
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => renovar30(e)}
                  title="Renovar la suscripción por 30 días desde hoy"
                >
                  <Crown className="mr-1.5 h-4 w-4" /> Renovar 30d
                </Button>
                <Link href={`/admin/empresas/${e.id}`}>
                  <Button variant="outline" size="sm">
                    <Users className="mr-1.5 h-4 w-4" /> Usuarios
                  </Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
/* ── Chip de estado de suscripción en la lista de empresas ── */
function ChipSuscripcion({ estado, plan }: { estado: string; plan: string }) {
  if (estado === "sin_vencimiento") {
    return (
      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
        {plan === "gratuito" ? "Gratuito" : "Sin vencimiento"}
      </span>
    );
  }
  const map: Record<string, { txt: string; color: string }> = {
    // "prueba" tiene que estar: sin ella el fallback de abajo pinta de
    // verde "Activa" a una empresa que está en prueba y no pagó nada.
    prueba: { txt: "En prueba", color: "#0ea5e9" },
    activa: { txt: "Activa", color: "#10b981" },
    prorroga: { txt: "En prórroga", color: "#f59e0b" },
    vencida: { txt: "Vencida", color: "#ef4444" },
  };
  const s = map[estado] ?? map.activa;
  return (
    <span
      className="rounded-full px-2 py-0.5 text-xs font-semibold"
      style={{ background: `${s.color}22`, color: s.color }}
    >
      {s.txt}
    </span>
  );
}
