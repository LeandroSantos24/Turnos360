"use client";

/**
 * Proveedor de temas (claro/oscuro) usando next-themes.
 * Envuelve la app y gestiona el cambio de tema, recordando la preferencia.
 */

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { type ComponentProps } from "react";

export function ThemeProvider({
  children,
  ...props
}: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}