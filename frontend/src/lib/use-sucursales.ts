"use client";

/**
 * Los locales del negocio, para las pantallas que necesitan ofrecerlos.
 *
 * `multi` es el dato que decide todo: con un solo local, la palabra
 * "sucursal" no aparece en ningún lado. Los selectores, las columnas y los
 * filtros se esconden solos, y el negocio de una silla sigue viendo la
 * aplicación exactamente igual que antes de que existiera multisucursal.
 *
 * La lista se cachea a nivel de módulo porque la piden varias pantallas y
 * casi nunca cambia: sin eso, abrir el diálogo de un profesional dispara un
 * GET cada vez.
 */

import { useCallback, useEffect, useState } from "react";

import { listarSucursales, Sucursal } from "./sucursales-api";

let cache: Sucursal[] | null = null;
let enVuelo: Promise<Sucursal[]> | null = null;

async function traer(): Promise<Sucursal[]> {
  if (cache) return cache;
  if (!enVuelo) {
    enVuelo = listarSucursales()
      .then((r) => {
        cache = r.sucursales;
        return cache;
      })
      .finally(() => {
        enVuelo = null;
      });
  }
  return enVuelo;
}

/** Invalida el cache. Llamalo después de crear, editar o cerrar un local. */
export function olvidarSucursales(): void {
  cache = null;
}

// El prefijo `use` no es capricho: sin él, el linter de React no puede
// verificar las reglas de hooks acá adentro (misma convención que
// useConfirmar).
export function useSucursales() {
  const [sucursales, setSucursales] = useState<Sucursal[]>(cache ?? []);
  const [cargando, setCargando] = useState(cache === null);

  const recargar = useCallback(async () => {
    olvidarSucursales();
    setCargando(true);
    try {
      setSucursales(await traer());
    } catch {
      // Recepción y profesional no pueden listar locales (el endpoint es del
      // dueño). No es un error que haya que mostrar: sin locales, la pantalla
      // simplemente no ofrece nada de multisucursal.
      setSucursales([]);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    let vivo = true;
    traer()
      .then((s) => vivo && setSucursales(s))
      .catch(() => vivo && setSucursales([]))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, []);

  const abiertas = sucursales.filter((s) => s.activa);
  return {
    sucursales,
    /** Solo las que están abiertas: son las únicas asignables. */
    abiertas,
    cargando,
    /** true = hay más de un local. Es lo que enciende toda la interfaz. */
    multi: abiertas.length > 1,
    nombreDe: (id: number | null | undefined) =>
      sucursales.find((s) => s.id === id)?.nombre ?? null,
    recargar,
  };
}
