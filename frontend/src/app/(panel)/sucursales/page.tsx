"use client";

/**
 * Sucursales (/sucursales) — solo el dueño, y solo con el plan Multi.
 *
 * Por qué esta pantalla puede no existir
 * --------------------------------------
 * Toda empresa tiene un local: se crea con el alta y se llama como el negocio.
 * Un barbero de una silla no tiene nada que hacer acá, y por eso el ítem del
 * menú no le aparece (el layout lo esconde cuando `limite_sucursales` es 1).
 *
 * Ese es el criterio de toda la fase: por debajo el sistema ya es
 * multisucursal, pero la palabra "sucursal" solo aparece cuando el negocio
 * realmente tiene más de un local.
 *
 * Qué NO hay acá
 * --------------
 * No hay botón de borrar. Un local tiene turnos, caja y arqueos colgando: se
 * cierra y su historia queda, igual que con las gift cards. Y cerrarlo pide
 * confirmación, como toda acción que cambia lo que otro ve.
 */

import { useCallback, useEffect, useState } from "react";
import { Building2, MapPin, Pencil, Phone, Plus, Users } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  editarSucursal,
  listarSucursales,
  Sucursal,
  SucursalesRespuesta,
} from "@/lib/sucursales-api";
import { RequiereDueno } from "@/components/requiere-rol";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { SucursalDialog } from "./sucursal-dialog";

function ContenidoSucursales() {
  const confirmar = useConfirmar();
  const [datos, setDatos] = useState<SucursalesRespuesta | null>(null);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState<Sucursal | null>(null);
  const [dialogo, setDialogo] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setDatos(await listarSucursales());
    } catch {
      toast.error("No se pudieron cargar los locales");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function cambiarEstado(s: Sucursal) {
    const cerrando = s.activa;
    if (cerrando) {
      const ok = await confirmar({
        titulo: `¿Cerrar «${s.nombre}»?`,
        descripcion:
          "Deja de aparecer en la reserva pública y no se le pueden asignar " +
          "profesionales. Los turnos y la caja que ya tiene se conservan, y " +
          "podés volver a abrirlo cuando quieras.",
        textoAccion: "Cerrar local",
        destructivo: true,
      });
      if (!ok) return;
    }
    try {
      await editarSucursal(s.id, { activa: !s.activa });
      toast.success(cerrando ? `«${s.nombre}» quedó cerrado` : `«${s.nombre}» está abierto`);
      void cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar");
    }
  }

  function abrirAlta() {
    setEditando(null);
    setDialogo(true);
  }

  function abrirEdicion(s: Sucursal) {
    setEditando(s);
    setDialogo(true);
  }

  if (cargando) {
    return <p className="text-muted-foreground">Cargando…</p>;
  }
  if (!datos) return null;

  const sinCupo = datos.usadas >= datos.tope;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Sucursales</h1>
          <p className="text-sm text-muted-foreground">
            Tus locales. Cada uno tiene su equipo, su agenda y su caja.
          </p>
        </div>
        <Button onClick={abrirAlta} disabled={sinCupo}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo local
        </Button>
      </header>

      <p className="text-sm text-muted-foreground">
        {datos.usadas} de {datos.tope} {datos.tope === 1 ? "local" : "locales"} en uso
        {sinCupo && (
          <>
            {" "}
            — tu plan {datos.plan_etiqueta} no incluye más. Para sumar otro,
            cambiá de plan desde <b>Mi suscripción</b>.
          </>
        )}
      </p>

      <ul className="space-y-3">
        {datos.sucursales.map((s) => (
          <li
            key={s.id}
            className={`rounded-xl border p-4 ${s.activa ? "" : "opacity-60"}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{s.nombre}</span>
                  {!s.activa && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs">
                      Cerrado
                    </span>
                  )}
                </div>
                {s.direccion && (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" />
                    {s.direccion}
                  </p>
                )}
                {s.telefono && (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Phone className="h-3.5 w-3.5" />
                    {s.telefono}
                  </p>
                )}
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Users className="h-3.5 w-3.5" />
                  {s.profesionales === 0
                    ? "Sin profesionales asignados"
                    : `${s.profesionales} ${s.profesionales === 1 ? "profesional" : "profesionales"}`}
                </p>
              </div>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => abrirEdicion(s)}>
                  <Pencil className="mr-2 h-3.5 w-3.5" />
                  Editar
                </Button>
                <Button
                  variant={s.activa ? "outline" : "default"}
                  size="sm"
                  onClick={() => void cambiarEstado(s)}
                >
                  {s.activa ? "Cerrar" : "Reabrir"}
                </Button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <SucursalDialog
        abierto={dialogo}
        sucursal={editando}
        onCerrar={() => setDialogo(false)}
        onListo={() => void cargar()}
      />
    </div>
  );
}

export default function SucursalesPage() {
  return (
    <RequiereDueno>
      <ContenidoSucursales />
    </RequiereDueno>
  );
}
