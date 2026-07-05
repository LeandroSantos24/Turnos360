"use client";

/**
 * Gestión de usuarios de una empresa (/admin/empresas/[id]).
 * Lista los usuarios, permite crear uno nuevo con su rol y activar/desactivar.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Plus, ExternalLink } from "lucide-react";
import { toast } from "sonner";

import {
  listarUsuarios,
  crearUsuario,
  actualizarUsuario,
  listarEmpresas,
  UsuarioAdmin,
  RolUsuario,
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
        href="/admin"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Volver a empresas
      </Link>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={SYNE}>
            Usuarios
          </h1>
          <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
            {nombreEmpresa || "Empresa"}
            {slugEmpresa && (
              <button
                type="button"
                onClick={() => window.open(`/${slugEmpresa}`, "_blank", "noopener,noreferrer")}
                className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
              >
                /{slugEmpresa} <ExternalLink className="h-3.5 w-3.5" />
              </button>
            )}
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
              <Plus className="mr-1.5 h-4 w-4" /> Nuevo usuario
            </Button>
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
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Switch
                  checked={u.activo}
                  onCheckedChange={() => toggleActivo(u)}
                />
                Activo
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}