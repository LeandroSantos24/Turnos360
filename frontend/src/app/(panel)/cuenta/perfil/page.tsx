"use client";

/**
 * Mi cuenta · Perfil (/cuenta/perfil).
 *
 * Se edita solo el nombre. El email es el usuario para entrar y el rol y el
 * local los decide el dueño: se muestran, con la explicación de dónde se
 * cambian, pero no hay campo para tocarlos (el servidor tampoco los acepta).
 */

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Lock, MailWarning } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { actualizarPerfil, reenviarVerificacion } from "@/lib/auth-api";
import { useConfigRubro } from "@/lib/config-rubro";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, CargandoCuenta, ErrorCuenta, FilaDato, ROL_LABEL, useCuenta } from "../_cuenta";

export default function CuentaPerfil() {
  const { usuario, error, recargar, setUsuario } = useCuenta();
  const config = useConfigRubro();
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [reenviando, setReenviando] = useState(false);

  useEffect(() => {
    if (usuario) setNombre(usuario.nombre);
  }, [usuario]);

  if (error) return <ErrorCuenta onReintentar={recargar} />;
  if (!usuario) return <CargandoCuenta />;

  const dueno = usuario.rol === "dueno";
  const limpio = nombre.trim().replace(/\s+/g, " ");
  const cambio = limpio !== usuario.nombre;
  const valido = limpio.length >= 2 && limpio.length <= 120;

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!valido || !cambio) return;
    setGuardando(true);
    try {
      const u = await actualizarPerfil(limpio);
      setUsuario({ ...usuario!, ...u });
      toast.success("Nombre actualizado");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  async function reenviar() {
    setReenviando(true);
    try {
      await reenviarVerificacion();
      toast.success(`Te mandamos el email a ${usuario!.email}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo mandar el email");
    } finally {
      setReenviando(false);
    }
  }

  const multisucursal = (config?.limite_sucursales ?? 1) > 1;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="tarjeta p-5 sm:p-6" aria-labelledby="t-editable">
        <div className="flex items-center gap-3">
          <Avatar nombre={limpio || usuario.nombre} />
          <div>
            <h2 id="t-editable" className="font-semibold">Lo que podés cambiar</h2>
            <p className="text-sm text-muted-foreground">Así te ven en el panel y en la agenda.</p>
          </div>
        </div>
        <form onSubmit={guardar} className="mt-5 max-w-md space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="p-nombre">Nombre y apellido</Label>
            <Input
              id="p-nombre"
              value={nombre}
              maxLength={120}
              autoComplete="name"
              aria-invalid={!valido}
              aria-describedby="p-nombre-ayuda"
              onChange={(e) => setNombre(e.target.value)}
            />
            <p id="p-nombre-ayuda" className={`text-xs ${valido ? "text-muted-foreground" : "text-destructive"}`}>
              {valido ? "Entre 2 y 120 caracteres." : "Escribí tu nombre (al menos 2 letras)."}
            </p>
          </div>
          <div className="flex gap-2">
            <Button type="submit" disabled={!cambio || !valido || guardando}>
              {guardando && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              {guardando ? "Guardando…" : "Guardar"}
            </Button>
            {cambio && (
              <Button type="button" variant="ghost" onClick={() => setNombre(usuario.nombre)} disabled={guardando}>
                Descartar
              </Button>
            )}
          </div>
        </form>
      </section>

      <section className="tarjeta p-5 sm:p-6" aria-labelledby="t-fijo">
        <h2 id="t-fijo" className="flex items-center gap-2 font-semibold">
          <Lock className="h-4 w-4 text-muted-foreground" aria-hidden /> Lo que no se cambia desde acá
        </h2>
        <dl className="mt-2 divide-y">
          <FilaDato
            etiqueta="Email"
            valor={
              <span className="inline-flex flex-wrap items-center gap-2">
                {usuario.email}
                {usuario.email_verificado ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> Confirmado
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
                    <MailWarning className="h-3.5 w-3.5" aria-hidden /> Sin confirmar
                  </span>
                )}
              </span>
            }
            nota={
              <>
                {dueno
                  ? "Es tu usuario para entrar y donde te llegan los avisos de la suscripción. Para cambiarlo, escribinos a soporte."
                  : "Es tu usuario para entrar. Si hay que cambiarlo, pedíselo al dueño del negocio."}
                {!usuario.email_verificado && (
                  <span className="mt-2 block">
                    <Button type="button" variant="outline" size="sm" onClick={reenviar} disabled={reenviando}>
                      {reenviando && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                      Reenviar email de confirmación
                    </Button>
                  </span>
                )}
              </>
            }
          />
          <FilaDato
            etiqueta="Rol"
            valor={ROL_LABEL[usuario.rol] ?? usuario.rol}
            nota={dueno ? "Sos quien administra el negocio." : "Lo asigna el dueño desde Equipo."}
          />
          {multisucursal && usuario.sucursal_nombre && (
            <FilaDato
              etiqueta="Local"
              valor={usuario.sucursal_nombre}
              nota={dueno ? "Ves todos los locales; este es en el que abre tu agenda." : "Lo asigna el dueño desde Equipo."}
            />
          )}
        </dl>
      </section>
    </div>
  );
}
