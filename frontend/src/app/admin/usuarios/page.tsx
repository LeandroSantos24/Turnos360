"use client";

/**
 * Usuarios y accesos (/admin/usuarios).
 *
 * Todos los usuarios de todos los negocios. Desde acá se corta o devuelve
 * el acceso (cortarlo cierra las sesiones) y se manda un link para
 * restablecer la contraseña. Nunca se ve ni se escribe una contraseña.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { cambiarAccesoUsuario, listarUsuariosGlobal, type UsuarioGlobal } from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Encabezado, Vacio } from "../_ui";
import { RestablecerClave } from "./restablecer-clave";

const ROLES: Record<string, string> = {
  dueno: "Dueño",
  admin: "Administrador",
  recepcion: "Recepción",
  profesional: "Profesional",
};

type Datos = { total: number; pagina: number; limite: number; filas: UsuarioGlobal[] };

export default function UsuariosAdmin() {
  const [buscar, setBuscar] = useState("");
  const [consulta, setConsulta] = useState("");
  const [rol, setRol] = useState("");
  const [activo, setActivo] = useState("");
  const [pagina, setPagina] = useState(1);
  const [d, setD] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const confirmar = useConfirmar();

  const cargar = useCallback(() => {
    setError(null);
    listarUsuariosGlobal({
      buscar: consulta || undefined,
      rol: rol || undefined,
      activo: activo === "" ? undefined : activo === "si",
      pagina,
    })
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los usuarios."));
  }, [consulta, rol, activo, pagina]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function cambiar(u: UsuarioGlobal) {
    const ok = await confirmar({
      titulo: u.activo ? `¿Cortar el acceso de ${u.nombre}?` : `¿Devolverle el acceso a ${u.nombre}?`,
      descripcion: u.activo
        ? `${u.email} (${u.empresa}) no va a poder entrar y se cierran sus sesiones abiertas.`
        : `${u.email} (${u.empresa}) vuelve a poder entrar con su contraseña.`,
      textoAccion: u.activo ? "Sí, cortar acceso" : "Sí, devolver acceso",
      destructivo: u.activo,
    });
    if (!ok) return;
    try {
      await cambiarAccesoUsuario(u.id, !u.activo);
      toast.success(u.activo ? "Acceso cortado" : "Acceso devuelto");
      cargar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo cambiar el acceso.");
    }
  }

  const paginas = d ? Math.max(1, Math.ceil(d.total / d.limite)) : 1;

  return (
    <div>
      <Encabezado
        titulo="Usuarios y accesos"
        bajada="Todos los usuarios de todos los negocios. Cortar un acceso cierra sus sesiones; la contraseña se restablece con un link al email del usuario."
      />
      <form
        className="mb-4 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setPagina(1);
          setConsulta(buscar.trim());
        }}
      >
        <label className="min-w-[200px] flex-1 text-xs text-muted-foreground">
          Buscar
          <span className="relative mt-1 block">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden />
            <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre, email o negocio"
              className="w-full rounded-lg border bg-background py-1.5 pl-8 pr-2 text-sm text-foreground" />
          </span>
        </label>
        <label className="text-xs text-muted-foreground">
          Rol
          <select value={rol} onChange={(e) => { setRol(e.target.value); setPagina(1); }}
            className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground">
            <option value="">Todos</option>
            {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Acceso
          <select value={activo} onChange={(e) => { setActivo(e.target.value); setPagina(1); }}
            className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground">
            <option value="">Todos</option>
            <option value="si">Con acceso</option>
            <option value="no">Sin acceso</option>
          </select>
        </label>
        <Button type="submit" size="sm" variant="outline">Buscar</Button>
      </form>

      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
      ) : d.filas.length === 0 ? (
        <Vacio>No hay usuarios con esos filtros.</Vacio>
      ) : (
        <>
          <p className="mb-2 text-xs text-muted-foreground">{d.total} usuario(s)</p>
          <ul className="divide-y rounded-2xl border bg-card">
            {d.filas.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {u.nombre}
                    {!u.activo && <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Sin acceso</span>}
                    {!u.email_verificado && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">Email sin verificar</span>}
                    {u.restablecimiento_pendiente && <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-900 dark:bg-sky-950 dark:text-sky-200">Link de clave enviado</span>}
                  </p>
                  <p className="truncate text-sm text-muted-foreground">
                    {u.email} · {ROLES[u.rol] ?? u.rol} ·{" "}
                    <Link href={`/admin/empresas/${u.empresa_id}`} className="underline-offset-4 hover:underline">{u.empresa}</Link>
                    {u.sucursal ? ` · ${u.sucursal}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <RestablecerClave usuario={u} onListo={cargar} />
                  <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Switch checked={u.activo} onCheckedChange={() => cambiar(u)} aria-label={`Acceso de ${u.nombre}`} />
                    <span className="hidden sm:inline">Acceso</span>
                  </label>
                </div>
              </li>
            ))}
          </ul>
          {paginas > 1 && (
            <div className="mt-4 flex items-center justify-center gap-3 text-sm">
              <Button size="sm" variant="outline" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>Anterior</Button>
              <span className="tabular-nums">{pagina} de {paginas}</span>
              <Button size="sm" variant="outline" disabled={pagina >= paginas} onClick={() => setPagina((p) => p + 1)}>Siguiente</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
