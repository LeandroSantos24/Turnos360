"use client";

/**
 * Confirmación del email, desde el link que llega por correo.
 *
 * Es lo que enciende la página pública del negocio. Hasta que alguien pase por
 * acá, la vidriera responde 404 — ver services/publico.py::resolver_empresa.
 */

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, XCircle } from "lucide-react";

import { verificarEmail } from "@/lib/publico-api";
import { ApiError } from "@/lib/api";

function Contenido() {
  const params = useSearchParams();
  const token = params.get("token");
  const [estado, setEstado] = useState<"cargando" | "ok" | "error">("cargando");
  const [mensaje, setMensaje] = useState("");

  useEffect(() => {
    if (!token) {
      setEstado("error");
      setMensaje("El link no tiene el código de verificación.");
      return;
    }
    verificarEmail(token)
      .then((r) => {
        setEstado("ok");
        setMensaje(r.detalle);
      })
      .catch((e) => {
        setEstado("error");
        setMensaje(
          e instanceof ApiError
            ? e.message
            : "No pudimos verificar tu email. Probá de nuevo.",
        );
      });
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-md rounded-2xl border bg-card p-8 text-center shadow-sm">
        <Link href="/" className="text-xl font-bold">
          Turnos<span className="text-primary">360</span>
        </Link>

        {estado === "cargando" && (
          <p className="mt-6 text-sm text-muted-foreground">Verificando…</p>
        )}

        {estado === "ok" && (
          <>
            <CheckCircle2 className="mx-auto mt-6 h-12 w-12 text-emerald-500" />
            <h1 className="mt-4 text-xl font-bold">¡Email confirmado!</h1>
            <p className="mt-2 text-sm text-muted-foreground">{mensaje}</p>
            <Link
              href="/inicio"
              className="mt-6 flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Ir a mi panel
            </Link>
          </>
        )}

        {estado === "error" && (
          <>
            <XCircle className="mx-auto mt-6 h-12 w-12 text-destructive" />
            <h1 className="mt-4 text-xl font-bold">No pudimos verificarlo</h1>
            <p className="mt-2 text-sm text-muted-foreground">{mensaje}</p>
            <p className="mt-3 text-xs text-muted-foreground">
              Entrá a tu panel y pedí un link nuevo desde el aviso de arriba.
            </p>
            <Link
              href="/login"
              className="mt-6 flex h-10 w-full items-center justify-center rounded-md border px-4 text-sm font-medium transition-colors hover:bg-muted"
            >
              Iniciar sesión
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerificarPage() {
  return (
    <Suspense fallback={null}>
      <Contenido />
    </Suspense>
  );
}
