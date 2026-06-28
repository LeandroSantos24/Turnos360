"use client";

/** Login del panel de super-administración (/admin/login). */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { loginAdmin, setAdminToken } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [cargando, setCargando] = useState(false);

  async function entrar() {
    if (!email.trim() || !clave) return;
    setCargando(true);
    try {
      const r = await loginAdmin(email.trim(), clave);
      setAdminToken(r.access_token);
      router.replace("/admin");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo iniciar sesión",
      );
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
      <div className="w-full max-w-sm rounded-2xl border bg-card p-8">
        <h1 className="text-xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
          Turnos360 · Administración
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Panel de super-administrador
        </p>
        <div className="mt-6 space-y-3">
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            type="password"
            placeholder="Contraseña"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && entrar()}
          />
          <Button className="w-full" onClick={entrar} disabled={cargando}>
            {cargando ? "Entrando…" : "Entrar"}
          </Button>
        </div>
      </div>
    </div>
  );
}