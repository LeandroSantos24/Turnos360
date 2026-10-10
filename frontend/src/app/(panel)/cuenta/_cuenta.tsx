"use client";

/**
 * Lo que comparten los apartados de «Mi cuenta»: el usuario (una sola
 * lectura de /auth/me para todas las pestañas) y piezas chicas de interfaz.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { getMe, type UsuarioMe } from "@/lib/auth-api";

export const ROL_LABEL: Record<string, string> = {
  dueno: "Dueño",
  admin: "Administrador",
  recepcion: "Recepción",
  profesional: "Profesional",
};

/** Iniciales para el avatar: «Leandro Santos» → «LS», «Leandro» → «L». */
export function iniciales(nombre: string | null | undefined): string {
  const partes = (nombre ?? "").trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  const dos = partes.length > 1 ? partes[0][0] + partes[partes.length - 1][0] : partes[0][0];
  return dos.toUpperCase();
}

interface Contexto {
  usuario: UsuarioMe | null;
  error: boolean;
  recargar: () => Promise<void>;
  setUsuario: (u: UsuarioMe) => void;
}

const Ctx = createContext<Contexto | null>(null);

export function ProveedorCuenta({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<UsuarioMe | null>(null);
  const [error, setError] = useState(false);

  const recargar = useCallback(async () => {
    try {
      setUsuario(await getMe());
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  return <Ctx.Provider value={{ usuario, error, recargar, setUsuario }}>{children}</Ctx.Provider>;
}

export function useCuenta(): Contexto {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCuenta fuera de ProveedorCuenta");
  return c;
}

export function Avatar({ nombre, tam = "md" }: { nombre: string; tam?: "md" | "lg" }) {
  const clases = tam === "lg" ? "h-16 w-16 text-xl" : "h-10 w-10 text-sm";
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-2xl bg-primary/15 font-bold text-[hsl(170_85%_26%)] dark:text-primary ${clases}`}
      style={{ fontFamily: "var(--fuente-titulos)" }}
    >
      {iniciales(nombre)}
    </span>
  );
}

/** Fila «etiqueta / valor» de solo lectura, con la explicación de por qué. */
export function FilaDato({
  etiqueta,
  valor,
  nota,
}: {
  etiqueta: string;
  valor: React.ReactNode;
  nota?: React.ReactNode;
}) {
  return (
    <div className="grid gap-1 py-3.5 sm:grid-cols-[180px_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{etiqueta}</dt>
      <dd className="min-w-0">
        <div className="break-words text-sm font-medium">{valor}</div>
        {nota && <div className="mt-0.5 text-xs text-muted-foreground">{nota}</div>}
      </dd>
    </div>
  );
}

export function CargandoCuenta() {
  return (
    <div className="space-y-4">
      <div className="tarjeta h-32 animate-pulse" />
      <div className="tarjeta h-48 animate-pulse" />
    </div>
  );
}

export function ErrorCuenta({ onReintentar }: { onReintentar: () => void }) {
  return (
    <div className="tarjeta p-6 text-sm">
      <p className="font-medium">No pudimos cargar tu cuenta.</p>
      <button type="button" onClick={onReintentar} className="enlace mt-2">
        Reintentar
      </button>
    </div>
  );
}
