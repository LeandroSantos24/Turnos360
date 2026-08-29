"use client";

/**
 * El aviso de "confirmá tu email", arriba de todo el panel.
 *
 * Existe porque el candado anti-spam es invisible: hasta que el dueño no
 * verifica, su página pública responde 404. Sin este cartel, comparte el link
 * con sus clientes, no funciona, y no tiene forma de saber por qué.
 *
 * Solo aparece para quien se registró solo y todavía no confirmó. Los negocios
 * que dio de alta el super-admin nacen verificados y no lo ven nunca.
 */

import { useState } from "react";
import { MailWarning } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";

export function AvisoVerificacion({ email }: { email: string }) {
  const [enviando, setEnviando] = useState(false);
  const [mandado, setMandado] = useState(false);

  async function reenviar() {
    setEnviando(true);
    try {
      const r = await api.post<{ detalle: string }>(
        "/auth/reenviar-verificacion",
        {},
      );
      toast.success(r.detalle);
      setMandado(true);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo reenviar");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-amber-500/30 bg-amber-500/10 px-6 py-2.5 text-sm">
      <MailWarning className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <span className="min-w-0 flex-1">
        <b>Confirmá tu email</b> para publicar tu página de reservas. Te lo
        mandamos a {email}.
      </span>
      <button
        type="button"
        onClick={reenviar}
        disabled={enviando || mandado}
        className="shrink-0 font-medium underline-offset-4 hover:underline disabled:opacity-60"
      >
        {mandado ? "Enviado ✓" : enviando ? "Enviando…" : "Reenviar"}
      </button>
    </div>
  );
}
