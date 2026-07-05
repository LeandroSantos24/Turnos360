"use client";

/**
 * Panel de empresas (/admin).
 * Lista las empresas, permite crear una nueva (con su usuario dueño) y
 * pausar/reactivar el servicio. Cada empresa enlaza a su gestión de usuarios.
 */

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Plus, Users, ExternalLink, Copy, Check } from "lucide-react";
import { toast } from "sonner";

import {
  listarEmpresas,
  listarRubros,
  crearEmpresa,
  pausarEmpresa,
  EmpresaAdmin,
  RubroAdmin,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const SYNE = { fontFamily: "Syne, sans-serif" } as const;

function slugify(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function AdminEmpresasPage() {
  const [empresas, setEmpresas] = useState<EmpresaAdmin[]>([]);
  const [rubros, setRubros] = useState<RubroAdmin[]>([]);
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

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [e, r] = await Promise.all([listarEmpresas(), listarRubros()]);
      setEmpresas(e);
      setRubros(r);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
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
  }

  async function guardar() {
    if (
      !nombre.trim() ||
      !slug.trim() ||
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
        slug: slug.trim(),
        rubro_id: Number(rubroId),
        dueno: { nombre: dNombre.trim(), email: dEmail.trim(), clave: dClave },
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
    try {
      await pausarEmpresa(emp.id, !emp.activa);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar");
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
                <label className="mb-1 block text-sm font-medium">Rubro</label>
                <Select value={rubroId} onValueChange={setRubroId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Elegí un rubro">
                      {(v) =>
                        rubros.find((r) => String(r.id) === String(v))?.nombre ??
                        "Elegí un rubro"
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {rubros.map((r) => (
                      <SelectItem key={r.id} value={String(r.id)}>
                        {r.nombre}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                </p>
                <p className="text-sm text-muted-foreground">
                  {e.rubro_nombre ?? "—"} · /{e.slug} · {e.cantidad_usuarios}{" "}
                  {e.cantidad_usuarios === 1 ? "usuario" : "usuarios"}
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