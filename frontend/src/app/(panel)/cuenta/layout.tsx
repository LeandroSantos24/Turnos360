"use client";

/**
 * «Mi cuenta» en apartados: resumen, perfil, seguridad, negocio y permisos.
 *
 * Antes era una sola tarjeta con el plan y el formulario de contraseña. Cada
 * apartado es ahora una ruta con su pestaña, como «Mi suscripción», y todos
 * leen el mismo usuario (ProveedorCuenta).
 */

import { Building2, KeyRound, LayoutGrid, UserRound } from "lucide-react";

import { SubNav } from "@/components/sub-nav";
import { ProveedorCuenta } from "./_cuenta";

const PESTANAS = [
  { href: "/cuenta", label: "Resumen", icon: LayoutGrid, exacto: true },
  { href: "/cuenta/perfil", label: "Perfil", icon: UserRound },
  { href: "/cuenta/seguridad", label: "Seguridad", icon: KeyRound },
  { href: "/cuenta/negocio", label: "Negocio y permisos", icon: Building2 },
];

export default function LayoutCuenta({ children }: { children: React.ReactNode }) {
  return (
    <ProveedorCuenta>
      <div className="w-full space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="space-y-4">
          <div>
            <h1 className="titulo-pantalla">
              Mi <b>cuenta</b>.
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Tus datos, tu contraseña y lo que podés hacer en el negocio.
            </p>
          </div>
          <SubNav items={PESTANAS} etiqueta="Apartados de mi cuenta" />
        </header>
        {children}
      </div>
    </ProveedorCuenta>
  );
}
