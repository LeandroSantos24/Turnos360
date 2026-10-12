"use client";

/**
 * Botón + diálogo para restablecer la contraseña de un usuario.
 *
 * El admin nunca ve ni elige la clave: el backend le manda al usuario un link
 * de un solo uso que vence. Opcionalmente cierra las sesiones abiertas.
 * La respuesta trae el email enmascarado, nunca el link.
 */

import { useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { restablecerClaveUsuario } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function RestablecerClave({
  usuario,
  onListo,
}: {
  usuario: { id: number; nombre: string; email: string; activo: boolean };
  onListo?: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [cerrarSesiones, setCerrarSesiones] = useState(true);
  const [enviando, setEnviando] = useState(false);

  async function enviar() {
    setEnviando(true);
    try {
      const r = await restablecerClaveUsuario(usuario.id, cerrarSesiones);
      toast.success(r.detalle);
      setAbierto(false);
      onListo?.();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo iniciar el restablecimiento.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        disabled={!usuario.activo}
        title={usuario.activo ? undefined : "Activalo primero"}
        onClick={() => setAbierto(true)}
        aria-label={`Restablecer la contraseña de ${usuario.nombre}`}
      >
        <KeyRound className="h-4 w-4" /> <span className="hidden sm:inline">Restablecer clave</span>
      </Button>
      <Dialog open={abierto} onOpenChange={(o) => !enviando && setAbierto(o)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>¿Restablecer la contraseña de {usuario.nombre}?</DialogTitle>
            <DialogDescription>
              Le mandamos a {usuario.email} un link para elegir una contraseña nueva. Vence en poco tiempo y sirve una sola vez.
              Vos no ves ni elegís la contraseña. Queda registrado en la auditoría.
            </DialogDescription>
          </DialogHeader>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-[hsl(170_85%_30%)]"
              checked={cerrarSesiones}
              onChange={(e) => setCerrarSesiones(e.target.checked)}
            />
            <span>
              Cerrar todas sus sesiones abiertas
              <span className="block text-xs text-muted-foreground">Recomendado si sospechás que alguien más entró a la cuenta.</span>
            </span>
          </label>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAbierto(false)} disabled={enviando}>Cancelar</Button>
            <Button onClick={enviar} disabled={enviando}>
              {enviando && <Loader2 className="h-4 w-4 animate-spin" />} Mandar link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
