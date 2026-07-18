"use client";

/**
 * /olvide-password — el usuario pone su email y le mandamos el link.
 * La respuesta es SIEMPRE la misma (exista o no la cuenta): no revelamos
 * qué emails están registrados.
 */

import { useState } from "react";
import Link from "next/link";
import { KeyRound, MailCheck } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function OlvidePasswordPage() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  async function manejarSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCargando(true);
    try {
      await api.post("/auth/olvide-password", { email });
      setEnviado(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.",
      );
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f6f7f9] p-6">
      <div className="w-full max-w-sm rounded-2xl border bg-white p-8 shadow-sm">
        <h1
          className="text-2xl font-bold tracking-tight text-[#0a0f1e]"
          style={{ fontFamily: "Syne, sans-serif" }}
        >
          Turnos<span className="text-[#00b894]">360</span>
        </h1>

        {enviado ? (
          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-3 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">
              <MailCheck className="h-5 w-5 shrink-0" />
              Si el email está registrado, te enviamos un link para elegir una
              contraseña nueva. Revisá tu casilla (y el spam).
            </div>
            <p className="text-xs text-gray-500">
              El link vence en 60 minutos. ¿No llegó? Verificá que el email sea
              el de tu cuenta y probá de nuevo.
            </p>
            <Link href="/login" className="block text-sm font-medium text-[#00b894]">
              ← Volver al login
            </Link>
          </div>
        ) : (
          <>
            <div className="mt-5 flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#00b894]/10 text-[#00b894]">
                <KeyRound className="h-4 w-4" />
              </span>
              <div>
                <p className="font-semibold text-[#0a0f1e]">¿Olvidaste tu contraseña?</p>
                <p className="mt-0.5 text-sm text-gray-500">
                  Poné el email de tu cuenta y te mandamos un link para elegir
                  una nueva.
                </p>
              </div>
            </div>

            <form onSubmit={manejarSubmit} className="mt-6 space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="op-email">Email</Label>
                <Input
                  id="op-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <Button type="submit" className="w-full" disabled={cargando}>
                {cargando ? "Enviando…" : "Enviarme el link"}
              </Button>
              <Link
                href="/login"
                className="block text-center text-sm text-gray-500 hover:text-gray-700"
              >
                ← Volver al login
              </Link>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
