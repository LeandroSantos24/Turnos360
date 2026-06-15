"use client";

/**
 * Botón para alternar entre modo claro y oscuro.
 * Muestra un sol o una luna según el tema actual.
 */

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [montado, setMontado] = useState(false);

  // next-themes necesita que esperemos al montaje para evitar desajustes
  // entre lo que renderiza el servidor y el cliente.
  useEffect(() => setMontado(true), []);

  if (!montado) {
    return (
      <Button variant="ghost" size="icon" aria-label="Cambiar tema">
        <Sun size={18} />
      </Button>
    );
  }

  const esOscuro = theme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(esOscuro ? "light" : "dark")}
      aria-label="Cambiar tema"
      title={esOscuro ? "Modo claro" : "Modo oscuro"}
    >
      {esOscuro ? <Sun size={18} /> : <Moon size={18} />}
    </Button>
  );
}