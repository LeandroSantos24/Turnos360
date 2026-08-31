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
import Link from "next/link";
import {
  Building2,
  MapPin,
  Pencil,
  Phone,
  Plus,
  RotateCcw,
  UserPlus,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  editarSucursal,
  listarSucursales,
  Sucursal,
  SucursalesRespuesta,
} from "@/lib/sucursales-api";
import { olvidarSucursales } from "@/lib/use-sucursales";
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
      // Que el selector de local de Recursos vea el cambio sin recargar la app.
      olvidarSucursales();
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
      toast.success(
        cerrando ? `«${s.nombre}» quedó cerrado` : `«${s.nombre}» está abierto`,
      );
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
    return <p className="p-8 text-sm text-muted-foreground">Cargando…</p>;
  }
  if (!datos) return null;

  const sinCupo = datos.usadas >= datos.tope;

  return (
    <div className="p-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Sucursales</h1>
          <p className="text-sm text-muted-foreground">
            Tus locales. Cada uno tiene su equipo, su agenda y su caja.
          </p>
        </div>
        <Button onClick={abrirAlta} disabled={sinCupo}>
          <Plus size={16} className="mr-2" />
          Nuevo local
        </Button>
      </div>

      {/* Cupo del plan. En barra y no en texto suelto: de un vistazo se ve
          cuánto margen queda antes de tener que cambiar de plan. */}
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="flex items-center gap-1" aria-hidden>
          {Array.from({ length: datos.tope }).map((_, i) => (
            <span
              key={i}
              className={`h-1.5 w-7 rounded-full ${
                i < datos.usadas ? "bg-primary" : "bg-muted"
              }`}
            />
          ))}
        </div>
        <p className="text-sm">
          <span className="font-medium tabular-nums">
            {datos.usadas} de {datos.tope}
          </span>{" "}
          <span className="text-muted-foreground">
            {datos.tope === 1 ? "local" : "locales"} · plan {datos.plan_etiqueta}
          </span>
        </p>
        {sinCupo && (
          <p className="text-sm text-muted-foreground">
            — para sumar otro,{" "}
            <Link href="/suscripcion" className="font-medium underline underline-offset-4">
              cambiá de plan
            </Link>
            .
          </p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {datos.sucursales.map((s) => (
          <div
            key={s.id}
            className={`flex flex-col rounded-2xl border bg-card p-5 transition-colors ${
              s.activa ? "hover:border-foreground/20" : "opacity-70"
            }`}
          >
            <div className="mb-3 flex items-start gap-3">
              <span
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                  s.activa ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                }`}
              >
                <Building2 size={18} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate font-semibold">{s.nombre}</h2>
                  {s.es_principal && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                      Principal
                    </span>
                  )}
                  {!s.activa && (
                    <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400">
                      Cerrado
                    </span>
                  )}
                </div>
                <div className="mt-1.5 space-y-1 text-sm text-muted-foreground">
                  <p className="flex items-start gap-2">
                    <MapPin size={13} className="mt-0.5 shrink-0 opacity-60" />
                    <span className={s.direccion ? "" : "italic opacity-70"}>
                      {s.direccion ?? "Sin dirección cargada"}
                    </span>
                  </p>
                  {s.telefono && (
                    <p className="flex items-center gap-2">
                      <Phone size={13} className="shrink-0 opacity-60" />
                      {s.telefono}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Cuánta gente trabaja acá. Es el dato que hay que mirar antes de
                cerrar un local, y el atajo para ir a asignar profesionales. */}
            <Link
              href="/recursos"
              className="mb-4 flex items-center justify-between rounded-xl border border-dashed px-3 py-2.5 text-sm transition-colors hover:border-solid hover:bg-muted/50"
            >
              <span className="flex items-center gap-2">
                {s.profesionales === 0 ? (
                  <>
                    <UserPlus size={14} className="opacity-60" />
                    <span className="text-muted-foreground">
                      Sin profesionales — asigná los primeros
                    </span>
                  </>
                ) : (
                  <>
                    <Users size={14} className="opacity-60" />
                    <span>
                      <span className="font-medium tabular-nums">
                        {s.profesionales}
                      </span>{" "}
                      <span className="text-muted-foreground">
                        {s.profesionales === 1 ? "profesional" : "profesionales"}
                      </span>
                    </span>
                  </>
                )}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                Ver en Recursos →
              </span>
            </Link>

            <div className="mt-auto flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => abrirEdicion(s)}
              >
                <Pencil size={14} className="mr-2" />
                Editar
              </Button>
              <Button
                variant={s.activa ? "ghost" : "default"}
                size="sm"
                className="flex-1"
                onClick={() => void cambiarEstado(s)}
              >
                {s.activa ? (
                  "Cerrar local"
                ) : (
                  <>
                    <RotateCcw size={14} className="mr-2" />
                    Reabrir
                  </>
                )}
              </Button>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        Los locales no se borran: se cierran. Los turnos, la caja y los arqueos
        que ya tienen se conservan, y podés reabrirlos cuando quieras.
      </p>

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
