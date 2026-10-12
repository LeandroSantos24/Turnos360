"use client";

/**
 * Ficha de una empresa (/admin/empresas/[id]).
 *
 * Cuatro pestañas: Resumen (la suscripción con sus acciones críticas y la
 * ficha comercial), Usuarios (accesos y restablecer contraseña), Pagos (las
 * operaciones de cobro de este negocio) y Uso e historial (movimientos de la
 * suscripción y auditoría). La pestaña va en el #hash para poder linkearla.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus, ExternalLink, History, LayoutDashboard, Receipt, Users } from "lucide-react";
import { toast } from "sonner";
import { useConfirmar } from "@/components/confirmar";

import {
  listarUsuarios,
  crearUsuario,
  actualizarUsuario,
  listarEmpresas,
  UsuarioAdmin,
  RolUsuario,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { Button, buttonVariants } from "@/components/ui/button";
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
import { MovimientosSuscripcion } from "./movimientos-suscripcion";
import { AuditoriaEmpresa, GestionSuscripcion } from "./gestion-suscripcion";
import { Ficha } from "../../ficha-empresa";
import { RestablecerClave } from "../../usuarios/restablecer-clave";
import { PagosEmpresa } from "./pagos-empresa";

const PESTANAS = [
  { id: "resumen", label: "Resumen", icon: LayoutDashboard },
  { id: "usuarios", label: "Usuarios", icon: Users },
  { id: "pagos", label: "Pagos", icon: Receipt },
  { id: "historial", label: "Uso e historial", icon: History },
] as const;
type Pestana = (typeof PESTANAS)[number]["id"];

const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

const ROLES: { value: RolUsuario; label: string }[] = [
  { value: "dueno", label: "Dueño (acceso total)" },
  { value: "admin", label: "Administrador" },
  { value: "recepcion", label: "Recepción" },
  { value: "profesional", label: "Profesional" },
];

function labelRol(rol: string): string {
  return ROLES.find((r) => r.value === rol)?.label ?? rol;
}

export default function AdminUsuariosPage() {
  const confirmar = useConfirmar();
  const params = useParams();
  const empresaId = Number(params.id);

  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [nombreEmpresa, setNombreEmpresa] = useState("");
  const [slugEmpresa, setSlugEmpresa] = useState("");
  const [cargando, setCargando] = useState(true);
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [rol, setRol] = useState<RolUsuario | "">("");
  // Sube cuando una acción cambia la suscripción: las secciones se recargan.
  const [version, setVersion] = useState(0);
  const [pestana, setPestana] = useState<Pestana>("resumen");

  useEffect(() => {
    const h = window.location.hash.slice(1);
    if (PESTANAS.some((p) => p.id === h)) setPestana(h as Pestana);
  }, []);

  function irA(p: Pestana) {
    setPestana(p);
    window.history.replaceState(null, "", `#${p}`);
  }

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [us, empresas] = await Promise.all([
        listarUsuarios(empresaId),
        listarEmpresas(),
      ]);
      setUsuarios(us);
      const emp = empresas.find((e) => e.id === empresaId);
      setNombreEmpresa(emp?.nombre ?? "");
      setSlugEmpresa(emp?.slug ?? "");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [empresaId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function resetForm() {
    setNombre("");
    setEmail("");
    setClave("");
    setRol("");
  }

  async function guardar() {
    if (!nombre.trim() || !email.trim() || clave.length < 6 || !rol) {
      toast.error("Completá todos los campos (la clave debe tener 6+ caracteres)");
      return;
    }
    setGuardando(true);
    try {
      await crearUsuario(empresaId, {
        nombre: nombre.trim(),
        email: email.trim(),
        clave,
        rol: rol as RolUsuario,
      });
      toast.success("Usuario creado");
      setAbierto(false);
      resetForm();
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo crear");
    } finally {
      setGuardando(false);
    }
  }

  async function toggleActivo(u: UsuarioAdmin) {
    if (
      !(await confirmar({
        titulo: u.activo ? `¿Desactivar a ${u.nombre}?` : `¿Reactivar a ${u.nombre}?`,
        descripcion: u.activo
          ? `${u.email} deja de poder entrar al sistema.`
          : `${u.email} vuelve a poder entrar al sistema.`,
        textoAccion: u.activo ? "Sí, desactivar" : "Sí, reactivar",
        destructivo: u.activo,
      }))
    )
      return;
    try {
      await actualizarUsuario(u.id, !u.activo);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar");
    }
  }

  return (
    <div>
      <Link
        href="/admin/empresas"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Volver a empresas
      </Link>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={SYNE}>
            {nombreEmpresa || "Empresa"}
          </h1>
          <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
            {slugEmpresa && (
              <button
                type="button"
                onClick={() => window.open(`/${slugEmpresa}`, "_blank", "noopener,noreferrer")}
                className="inline-flex items-center gap-1 font-medium text-[hsl(170_85%_26%)] hover:underline dark:text-primary"
              >
                /{slugEmpresa} <ExternalLink className="h-3.5 w-3.5" />
              </button>
            )}
          </p>
        </div>
      </div>

      <div role="tablist" aria-label="Secciones de la empresa" className="-mx-1 mb-6 overflow-x-auto px-1">
        <div className="flex min-w-max gap-1 border-b">
          {PESTANAS.map(({ id, label, icon: Icono }) => (
            <button
              key={id}
              role="tab"
              id={`tab-${id}`}
              aria-selected={pestana === id}
              aria-controls={`panel-${id}`}
              onClick={() => irA(id)}
              className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
                pestana === id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icono className="h-4 w-4" aria-hidden /> {label}
            </button>
          ))}
        </div>
      </div>

      {pestana === "resumen" && (
        <div role="tabpanel" id="panel-resumen" aria-labelledby="tab-resumen" className="mb-6 space-y-4">
          <GestionSuscripcion
            empresaId={empresaId}
            version={version}
            onCambio={() => setVersion((v) => v + 1)}
          />
          <div className="overflow-hidden rounded-2xl border">
            <Ficha key={version} empresaId={empresaId} />
          </div>
        </div>
      )}

      {pestana === "usuarios" && (
      <div role="tabpanel" id="panel-usuarios" aria-labelledby="tab-usuarios">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Usuarios</h2>
        <Dialog
          open={abierto}
          onOpenChange={(o) => {
            setAbierto(o);
            if (!o) resetForm();
          }}
        >
          <DialogTrigger className={buttonVariants()}>
              <Plus className="mr-1.5 h-4 w-4" /> Nuevo usuario
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Nuevo usuario</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <Input
                placeholder="Nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
              />
              <Input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Input
                type="password"
                placeholder="Contraseña (6+)"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
              />
              <Select value={rol} onValueChange={(v) => setRol(v as RolUsuario)}>
                <SelectTrigger>
                  <SelectValue placeholder="Elegí un rol">
                    {(v) => labelRol(String(v))}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button onClick={guardar} disabled={guardando}>
                {guardando ? "Creando…" : "Crear usuario"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : usuarios.length === 0 ? (
        <div className="rounded-2xl border bg-card p-10 text-center">
          <p className="text-sm text-muted-foreground">
            Esta empresa todavía no tiene usuarios.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {usuarios.map((u) => (
            <div
              key={u.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card p-4"
            >
              <div className="min-w-0">
                <p className="flex items-center gap-2 font-medium">
                  {u.nombre}
                  {!u.activo && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      Inactivo
                    </span>
                  )}
                </p>
                <p className="text-sm text-muted-foreground">
                  {u.email} · {labelRol(u.rol)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <RestablecerClave usuario={u} />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Switch
                    checked={u.activo}
                    onCheckedChange={() => toggleActivo(u)}
                    aria-label={`Acceso de ${u.nombre}`}
                  />
                  Activo
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
      )}

      {pestana === "pagos" && (
        <div role="tabpanel" id="panel-pagos" aria-labelledby="tab-pagos">
          <PagosEmpresa empresaId={empresaId} onCambio={() => setVersion((v) => v + 1)} />
        </div>
      )}

      {pestana === "historial" && (
      <div role="tabpanel" id="panel-historial" aria-labelledby="tab-historial">
      <div>
        <MovimientosSuscripcion
          key={`m${version}`}
          empresaId={empresaId}
          nombre={nombreEmpresa}
          onCambio={() => setVersion((v) => v + 1)}
        />
      </div>

      <div className="pt-6">
        <AuditoriaEmpresa empresaId={empresaId} version={version} />
      </div>
      </div>
      )}
    </div>
  );
}
