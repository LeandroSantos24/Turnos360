"use client";

/**
 * Alta y edición de un empleado, por el propio dueño.
 *
 * Hasta acá el panel solo dejaba VER el equipo y generar un link de
 * contraseña. Sumar una recepcionista, o corregirle una letra al nombre a
 * alguien, era un pedido por WhatsApp al super-admin.
 *
 * El mismo diálogo sirve para crear y para editar: cambia si hay `miembro`.
 * En edición no se pide contraseña — para eso está el link de un solo uso, que
 * es más seguro que tipearle una clave nueva a alguien.
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  crearMiembro,
  editarMiembro,
  MiembroEquipo,
  ROLES_ASIGNABLES,
} from "@/lib/equipo-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Rol = "recepcion" | "profesional";

export function MiembroDialog({
  abierto,
  miembro,
  onCerrar,
  onListo,
}: {
  abierto: boolean;
  /** null = alta. Con miembro = edición. */
  miembro: MiembroEquipo | null;
  onCerrar: () => void;
  onListo: () => void;
}) {
  const editando = miembro !== null;
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [rol, setRol] = useState<Rol>("profesional");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    setNombre(miembro?.nombre ?? "");
    setEmail(miembro?.email ?? "");
    setRol(
      miembro?.rol === "recepcion" || miembro?.rol === "profesional"
        ? miembro.rol
        : "profesional",
    );
    setClave("");
  }, [abierto, miembro]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    try {
      if (editando) {
        await editarMiembro(miembro.id, { nombre, email, rol });
        toast.success("Cambios guardados");
      } else {
        await crearMiembro({ nombre, email, clave, rol });
        toast.success(`${nombre} ya puede entrar al panel`);
      }
      onListo();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editando ? "Editar persona" : "Sumar a alguien"}</DialogTitle>
          <DialogDescription>
            {editando
              ? "Para cambiarle la contraseña, usá el link de un solo uso de la lista."
              : "Le creás la cuenta y le pasás los datos. Después puede cambiar la clave."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={guardar} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="m-nombre">Nombre *</Label>
            <Input
              id="m-nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Sofía Pérez"
              required
              minLength={2}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="m-email">Email *</Label>
            <Input
              id="m-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="sofia@gmail.com"
              required
            />
            <p className="text-xs text-muted-foreground">
              Tiene que ser un email de verdad: es por donde va a poder
              recuperar su contraseña sin depender de vos.
            </p>
          </div>

          {!editando && (
            <div className="space-y-2">
              <Label htmlFor="m-clave">Contraseña inicial *</Label>
              <Input
                id="m-clave"
                type="text"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
                placeholder="Mínimo 8 caracteres"
                required
                minLength={8}
              />
              <p className="text-xs text-muted-foreground">
                Se la pasás y ella la cambia cuando quiera. Va en texto visible
                para que la puedas copiar sin equivocarte.
              </p>
            </div>
          )}

          <div className="space-y-2">
            <Label>Rol *</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {ROLES_ASIGNABLES.map((r) => (
                <button
                  key={r.valor}
                  type="button"
                  onClick={() => setRol(r.valor)}
                  className={`rounded-xl border p-3 text-left transition-colors ${
                    rol === r.valor
                      ? "border-primary bg-primary/5"
                      : "hover:bg-muted/50"
                  }`}
                >
                  <p className="text-sm font-medium">{r.label}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{r.ayuda}</p>
                </button>
              ))}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : editando ? "Guardar" : "Crear cuenta"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
