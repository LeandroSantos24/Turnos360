"use client";

/**
 * Home del panel (/). El layout ya valida la sesión, así que acá
 * solo mostramos una bienvenida. Más adelante: un resumen del día.
 */

export default function HomePage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold">Inicio</h1>
      <p className="mt-2 text-muted-foreground">
        Bienvenido a tu panel. Elegí una sección en el menú de la izquierda.
      </p>
    </div>
  );
}