"use client";

/**
 * Alta de un negocio, sin que intervenga nadie.
 *
 * Hasta acá el alta la hacía el super-admin a mano y la landing lo vendía como
 * propuesta de valor. Funciona con diez clientes; no escala a cien.
 *
 * Dos decisiones del formulario que importan:
 *
 * · La URL se propone sola a partir del nombre del negocio, pero se puede
 *   editar. Es el único dato que NO se puede cambiar después (no hay endpoint
 *   para editar el slug), así que se muestra bien grande cómo va a quedar.
 *
 * · Al terminar entra derecho al panel, sin volver a loguearse ni esperar el
 *   email. Lo que espera al email es la página pública — ese es el candado
 *   anti-spam, y está explicado en la pantalla para que no sea una sorpresa.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { saveTokens } from "@/lib/auth";
import {
  listarRubrosPublicos,
  registrarNegocio,
  RubroPublico,
} from "@/lib/publico-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Mismo normalizador que el backend, para que el preview no mienta. */
function aSlug(v: string, final = false): string {
  const sinTildes = v
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
  const limpio = sinTildes.replace(/[^a-z0-9]+/g, "-");
  return final ? limpio.replace(/^-+|-+$/g, "") : limpio.replace(/^-+/, "");
}

/** Un emoji por rubro, para que la grilla se lea de un vistazo. */
const EMOJI: Record<string, string> = {
  barberia: "💈",
  peluqueria: "✂️",
  unas: "💅",
  estetica: "✨",
  spa: "🧖",
  medico: "🩺",
  odontologia: "🦷",
  nutricion: "🥗",
  psicologia: "🧠",
  kinesiologia: "🤸",
  veterinaria: "🐶",
};

export default function RegistroPage() {
  const router = useRouter();
  const [rubros, setRubros] = useState<RubroPublico[]>([]);
  const [rubro, setRubro] = useState("");
  const [negocio, setNegocio] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTocado, setSlugTocado] = useState(false);
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    listarRubrosPublicos()
      .then((r) => {
        setRubros(r);
        if (r.length) setRubro((actual) => actual || r[0].codigo);
      })
      .catch(() => toast.error("No pudimos cargar los rubros. Recargá la página."));
  }, []);

  // La URL sigue al nombre del negocio hasta que la tocás a mano.
  const slugFinal = useMemo(
    () => aSlug(slugTocado ? slug : negocio, true),
    [slug, slugTocado, negocio],
  );

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!rubro) {
      toast.error("Elegí tu rubro");
      return;
    }
    setEnviando(true);
    try {
      const r = await registrarNegocio({
        nombre_negocio: negocio.trim(),
        slug: slugFinal,
        rubro_codigo: rubro,
        nombre: nombre.trim(),
        email: email.trim(),
        clave,
      });
      saveTokens(r.access_token, r.refresh_token);
      toast.success(`¡Listo, ${r.empresa_nombre} ya está creado!`);
      router.push("/inicio");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "No se pudo crear la cuenta",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen bg-muted/30 px-4 py-10">
      <div className="mx-auto max-w-xl">
        <div className="mb-6 text-center">
          <Link href="/" className="text-2xl font-bold">
            Turnos<span className="text-primary">360</span>
          </Link>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Creá tu cuenta y empezá a gestionar turnos. 14 días gratis, sin tarjeta.
          </p>
        </div>

        <form
          onSubmit={enviar}
          className="space-y-5 rounded-2xl border bg-card p-6 shadow-sm"
        >
          <div className="space-y-2">
            <Label>¿Cuál es tu rubro? *</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {rubros.map((r) => (
                <button
                  key={r.codigo}
                  type="button"
                  onClick={() => setRubro(r.codigo)}
                  className={`rounded-xl border p-3 text-center transition-colors ${
                    rubro === r.codigo
                      ? "border-primary bg-primary/5"
                      : "hover:bg-muted/50"
                  }`}
                >
                  <div className="text-xl">{EMOJI[r.codigo] ?? "📅"}</div>
                  <div className="mt-1 text-xs font-medium leading-tight">
                    {r.nombre}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="negocio">Nombre del negocio *</Label>
            <Input
              id="negocio"
              value={negocio}
              onChange={(e) => setNegocio(e.target.value)}
              placeholder="Barbería El Faro"
              required
              minLength={2}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="slug">La dirección de tu página *</Label>
            <Input
              id="slug"
              value={slugTocado ? slug : aSlug(negocio)}
              onChange={(e) => {
                setSlugTocado(true);
                setSlug(aSlug(e.target.value));
              }}
              placeholder="barberia-el-faro"
              required
            />
            <p className="text-xs text-muted-foreground">
              Tus clientes van a reservar en{" "}
              <span className="font-medium text-foreground">
                turnos360.com.ar/{slugFinal || "tu-negocio"}
              </span>
              . Elegila bien: es lo único que después no se puede cambiar.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="nombre">Tu nombre *</Label>
              <Input
                id="nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Leandro"
                required
                minLength={2}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Tu email *</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="leandro@gmail.com"
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="clave">Contraseña *</Label>
            <Input
              id="clave"
              type="password"
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              placeholder="Mínimo 8 caracteres"
              required
              minLength={8}
            />
          </div>

          <div className="rounded-xl bg-muted/60 p-3.5 text-xs text-muted-foreground">
            Vas a entrar al panel enseguida. Te mandamos un email para
            confirmar tu dirección: <b>hasta que lo confirmes, tu página de
            reservas no se publica</b>. Es para que nadie use Turnos360 para
            publicar cualquier cosa.
          </div>

          <Button type="submit" className="w-full" size="lg" disabled={enviando}>
            {enviando ? "Creando tu cuenta…" : "Crear mi cuenta gratis"}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            ¿Ya tenés cuenta?{" "}
            <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
              Iniciá sesión
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
