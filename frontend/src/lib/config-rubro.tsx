"use client";

/**
 * Provee la config del rubro (preset) a todo el panel.
 *
 * - useModulo("ficha_clinica") -> ¿está activo ese módulo en este rubro?
 * - useTermino()("cliente", "Cliente") -> traduce según la terminología del rubro.
 */

import { createContext, useContext } from "react";
import { ConfigEmpresa } from "./empresa-api";

const ConfigRubroContext = createContext<ConfigEmpresa | null>(null);

export function ConfigRubroProvider({
  value,
  children,
}: {
  value: ConfigEmpresa;
  children: React.ReactNode;
}) {
  return (
    <ConfigRubroContext.Provider value={value}>
      {children}
    </ConfigRubroContext.Provider>
  );
}

export function useConfigRubro(): ConfigEmpresa | null {
  return useContext(ConfigRubroContext);
}

/** Devuelve true si el módulo está activo en el preset del rubro. */
export function useModulo(clave: string): boolean {
  const config = useConfigRubro();
  return Boolean(config?.preset?.modulos?.[clave]);
}

/** Traduce un término según la terminología del rubro (cae al fallback). */
export function useTermino(): (clave: string, fallback: string) => string {
  const config = useConfigRubro();
  const term = config?.preset?.terminologia ?? {};
  return (clave, fallback) => term[clave] ?? fallback;
}