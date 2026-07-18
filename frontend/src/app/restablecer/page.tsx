"use client";

/**
 * /restablecer?token=… — la pantalla a la que llega el link del email.
 * Valida que las claves coincidan y tengan al menos 8 caracteres; el backend
 * valida el token (un solo uso, 60 min de vida).
 */

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LockKeyhole } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function FormRestablecer() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";

  const [clave, setClave] = useState("");
  const [clave2, setClave2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [listo, setListo] = useState(false);

  async function manejarSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (clave.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (clave !== clave2) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setCargando(true);
    try {
      await api.post("/auth/restablecer-password", {
        token,
        clave_nueva: clave,
      });
      setListo(true);
      setTimeout(() => router.push("/login"), 2500);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.",
      );
      setCargando(false);
    }
  }

  if (!token) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-red-600">
          El link no es válido (falta el código). Pedí uno nuevo desde el login.
        </p>
        <Link href="/olvide-password" className="block text-sm font-medium text-[#00b894]">
          Pedir un link nuevo →
        </Link>
      </div>
    );
  }

  if (listo) {
    return (
      <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">
        ✔ Contraseña actualizada. Te llevamos al login…
      </div>
    );
  }

  return (
    <form onSubmit={manejarSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="rp-clave">Contraseña nueva</Label>
        <Input
          id="rp-clave"
          type="password"
          required
          minLength={8}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          placeholder="Mínimo 8 caracteres"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="rp-clave2">Repetila</Label>
        <Input
          id="rp-clave2"
          type="password"
          required
          value={clave2}
          onChange={(e) => setClave2(e.target.value)}
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <Button type="submit" className="w-full" disabled={cargando}>
        {cargando ? "Guardando…" : "Guardar contraseña nueva"}
      </Button>
    </form>
  );
}

export default function RestablecerPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f6f7f9] p-6">
      <div className="w-full max-w-sm rounded-2xl border bg-white p-8 shadow-sm">
        <h1
          className="text-2xl font-bold tracking-tight text-[#0a0f1e]"
          style={{ fontFamily: "Syne, sans-serif" }}
        >
          Turnos<span className="text-[#00b894]">360</span>
        </h1>
        <div className="mt-5 flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#00b894]/10 text-[#00b894]">
            <LockKeyhole className="h-4 w-4" />
          </span>
          <div>
            <p className="font-semibold text-[#0a0f1e]">Elegí tu contraseña nueva</p>
            <p className="mt-0.5 text-sm text-gray-500">
              El link sirve una sola vez y vence en 60 minutos.
            </p>
          </div>
        </div>
        <div className="mt-6">
          <Suspense fallback={<p className="text-sm text-gray-500">Cargando…</p>}>
            <FormRestablecer />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
