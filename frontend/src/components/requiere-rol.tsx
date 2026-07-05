"use client";

/**
 * Guardas de PÁGINA por rol: si el rol no está permitido, REDIRIGE (no solo
 * esconde). Sirve para tapar el acceso por URL directa a pantallas dueño-only
 * (Estadísticas, Métodos de pago), donde ocultar la entrada del menú no alcanza.
 *
 * Uso, envolviendo el contenido de una page "use client":
 *
 *   export default function EstadisticasPage() {
 *     return (
 *       <RequiereDueno>
 *         <ContenidoEstadisticas />
 *       </RequiereDueno>
 *     );
 *   }
 *
 * El candado de verdad sigue siendo el backend; esto es UX (que el usuario no
 * vea una pantalla que igual no podría usar).
 */

import { useEffect, useState, type ReactNode } from "react";

import { useRouter } from "next/navigation";

import { esDueno, esGestion, leerRol, type Rol } from "@/lib/roles";

type Estado = "cargando" | "ok" | "denegado";

function GuardaRol({
  permitido,
  destino,
  children,
}: {
  permitido: (rol: Rol | null) => boolean;
  destino: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [estado, setEstado] = useState<Estado>("cargando");

  useEffect(() => {
    if (permitido(leerRol())) {
      setEstado("ok");
    } else {
      setEstado("denegado");
      router.replace(destino);
    }
  }, [router, destino, permitido]);

  // Mientras resuelve (o si va a redirigir) no mostramos nada de la página.
  if (estado !== "ok") return null;
  return <>{children}</>;
}

/** Solo el dueño ve la página; si no, redirige a `destino` (default "/inicio"). */
export function RequiereDueno({
  children,
  destino = "/inicio",
}: {
  children: ReactNode;
  destino?: string;
}) {
  return (
    <GuardaRol permitido={esDueno} destino={destino}>
      {children}
    </GuardaRol>
  );
}

/** Dueño + recepción (gestión del día); excluye al profesional. */
export function RequiereGestion({
  children,
  destino = "/inicio",
}: {
  children: ReactNode;
  destino?: string;
}) {
  return (
    <GuardaRol permitido={esGestion} destino={destino}>
      {children}
    </GuardaRol>
  );
}
