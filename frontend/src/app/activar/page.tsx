"use client";

/**
 * /activar?token=… — la persona invitada desde el super-admin elige su
 * contraseña. El link sirve una sola vez y vence (lo valida el backend).
 * Si el link no sirve, la respuesta es la misma pase lo que pase: no se
 * dice si venció, si se usó o si nunca existió.
 */

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { UserCheck } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Invitacion = { nombre: string; negocio: string | null; email: string };

function FormActivar() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [inv, setInv] = useState<Invitacion | null>(null);
  const [invalida, setInvalida] = useState<string | null>(null);
  const [clave, setClave] = useState("");
  const [clave2, setClave2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [listo, setListo] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setInvalida("El link no es válido (le falta el código).");
      return;
    }
    api
      .post<Invitacion>("/auth/invitacion", { token })
      .then(setInv)
      .catch((e) => setInvalida(e instanceof ApiError ? e.message : "No se pudo conectar con el servidor."));
  }, [token]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (clave.length < 8) {
      setError("La contraseña tiene que tener al menos 8 caracteres.");
      return;
    }
    if (clave !== clave2) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setCargando(true);
    try {
      const r = await api.post<{ detalle: string }>("/auth/activar", { token, clave });
      setListo(r.detalle);
      setTimeout(() => router.push("/login"), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
      setCargando(false);
    }
  }

  if (invalida) {
    return (
      <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800">
        {invalida}
      </p>
    );
  }
  if (!inv) return <p className="text-sm text-gray-600">Revisando el link…</p>;
  if (listo) {
    return (
      <p role="status" className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">
        ✔ {listo} Te llevamos al login…
      </p>
    );
  }

  return (
    <form onSubmit={enviar} className="space-y-4" noValidate>
      <p className="text-sm text-gray-700">
        Hola {inv.nombre}: elegí la contraseña para entrar
        {inv.negocio ? <> a <b>{inv.negocio}</b></> : null} con <b>{inv.email}</b>.
      </p>
      <div className="space-y-1.5">
        <Label htmlFor="ac-clave">Contraseña</Label>
        <Input
          id="ac-clave"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          aria-describedby="ac-ayuda"
          aria-invalid={!!error}
        />
        <p id="ac-ayuda" className="text-xs text-gray-600">Mínimo 8 caracteres.</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="ac-clave2">Repetila</Label>
        <Input
          id="ac-clave2"
          type="password"
          autoComplete="new-password"
          required
          value={clave2}
          onChange={(e) => setClave2(e.target.value)}
          aria-invalid={!!error}
        />
      </div>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <Button type="submit" className="w-full" disabled={cargando}>
        {cargando ? "Activando…" : "Activar mi cuenta"}
      </Button>
    </form>
  );
}

export default function ActivarPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f6f7f9] p-6">
      <div className="w-full max-w-sm rounded-2xl border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold tracking-tight text-[#0a0f1e]" style={{ fontFamily: "var(--fuente-marca)" }}>
          Turnos<span className="text-[#0b7262]">360</span>
        </h1>
        <div className="mt-5 flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#00b894]/10 text-[#0b7262]">
            <UserCheck className="h-4 w-4" aria-hidden />
          </span>
          <div>
            <p className="font-semibold text-[#0a0f1e]">Activá tu cuenta</p>
            <p className="mt-0.5 text-sm text-gray-600">El link sirve una sola vez.</p>
          </div>
        </div>
        <div className="mt-6">
          <Suspense fallback={<p className="text-sm text-gray-600">Cargando…</p>}>
            <FormActivar />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
