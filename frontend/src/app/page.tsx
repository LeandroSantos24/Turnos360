"use client";

/**
 * Raíz del panel (/).
 *
 * No tiene contenido propio todavía: solo decide a dónde mandar al usuario.
 * Si hay sesión → al panel (por ahora, un saludo). Si no → al login.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn, clearToken } from "@/lib/auth";
import { getMe, UsuarioMe } from "@/lib/auth-api";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  const router = useRouter();
  const [usuario, setUsuario] = useState<UsuarioMe | null>(null);

  useEffect(() => {
    // Al cargar: si no hay sesión, al login. Si hay, traemos los datos.
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    getMe()
      .then(setUsuario)
      .catch(() => router.push("/login")); // token inválido
  }, [router]);

  function salir() {
    clearToken();
    router.push("/login");
  }

  if (!usuario) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Cargando…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold">¡Hola, {usuario.nombre}!</h1>
      <p className="text-muted-foreground">
        Empresa #{usuario.empresa_id} · rol: {usuario.rol}
      </p>
      <Button variant="outline" onClick={salir}>
        Cerrar sesión
      </Button>
    </div>
  );
}