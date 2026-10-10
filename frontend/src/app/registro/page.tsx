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
import { FotoRubro, SelectorRubro } from "@/components/selector-rubro";

/** Mismo normalizador que el backend, para que el preview no mienta. */
function aSlug(v: string, final = false): string {
  const sinTildes = v
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
  const limpio = sinTildes.replace(/[^a-z0-9]+/g, "-");
  return final ? limpio.replace(/^-+|-+$/g, "") : limpio.replace(/^-+/, "");
}

/** Plural simple en castellano (barbero → barberos, box → boxes, sesión → sesiones). */
function plural(p: string): string {
  if (/ón$/i.test(p)) return p.replace(/ón$/i, "ones");
  return /[aeiouáéíóú]$/i.test(p) ? `${p}s` : `${p}es`;
}

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
  // Paso 1: qué tipo de negocio es. Paso 2: los datos, con la vista previa.
  const [paso, setPaso] = useState<1 | 2>(1);

  useEffect(() => {
    listarRubrosPublicos()
      .then((r) => {
        setRubros(r);
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

  const elegido = rubros.find((r) => r.codigo === rubro);

  if (paso === 1) {
    return (
      <div className="min-h-screen bg-muted/30 px-4 py-10">
        <div className="mx-auto max-w-5xl">
          <Encabezado subtitulo="Creá tu cuenta y empezá a gestionar turnos. 14 días gratis, sin tarjeta." />
          <section className="rounded-2xl border bg-card p-5 shadow-sm sm:p-6">
            <h1 className="text-xl font-bold tracking-tight">¿Qué tipo de negocio tenés?</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Con esto armamos tu agenda con los nombres y los servicios de tu rubro. Después cambiás lo que quieras.
            </p>
            <div className="mt-5">
              {rubros.length === 0 ? (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="aspect-[4/3] animate-pulse rounded-2xl bg-muted" />
                  ))}
                </div>
              ) : (
                <SelectorRubro rubros={rubros} valor={rubro} onCambio={setRubro} etiqueta="Tipo de negocio" />
              )}
            </div>
            <div className="mt-6 flex flex-col-reverse items-center justify-between gap-3 sm:flex-row">
              <p className="text-sm text-muted-foreground">
                ¿Ya tenés cuenta?{" "}
                <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
                  Iniciá sesión
                </Link>
              </p>
              <Button size="lg" className="w-full sm:w-auto" disabled={!rubro} onClick={() => setPaso(2)}>
                {elegido ? `Continuar con ${elegido.nombre}` : "Elegí tu rubro para continuar"}
              </Button>
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30 px-4 py-10">
      <div className="mx-auto max-w-5xl">
        <Encabezado subtitulo="Último paso: tus datos y los de tu negocio." />
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <form
          onSubmit={enviar}
          className="space-y-5 rounded-2xl border bg-card p-6 shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-xl font-bold tracking-tight">Tus datos</h1>
            <button
              type="button"
              onClick={() => setPaso(1)}
              className="rounded-full border px-3 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              {elegido?.nombre ?? "Rubro"} · cambiar
            </button>
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

          {/* Sin esto la cuenta se creaba sin que el negocio viera nunca los
              términos (cobro, suspensión por falta de pago, baja) ni la
              política de privacidad que exige la Ley 25.326 al recolectar
              datos. */}
          <p className="text-center text-xs text-muted-foreground">
            Al crear tu cuenta aceptás los{" "}
            <Link href="/terminos" target="_blank" className="font-medium text-foreground underline underline-offset-2">
              Términos y condiciones
            </Link>{" "}
            y la{" "}
            <Link href="/privacidad" target="_blank" className="font-medium text-foreground underline underline-offset-2">
              Política de privacidad
            </Link>
            .
          </p>

          <p className="text-center text-sm text-muted-foreground">
            ¿Ya tenés cuenta?{" "}
            <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
              Iniciá sesión
            </Link>
          </p>
        </form>

        <VistaPrevia rubro={elegido} negocio={negocio} slug={slugFinal} />
        </div>
      </div>
    </div>
  );
}

function Encabezado({ subtitulo }: { subtitulo: string }) {
  return (
    <div className="mb-6 text-center">
      <Link href="/" className="text-2xl font-bold">
        Turnos<span className="text-primary">360</span>
      </Link>
      <p className="mt-1.5 text-sm text-muted-foreground">{subtitulo}</p>
    </div>
  );
}

/** Cómo va a quedar: lo que el dueño ve antes de crear la cuenta. */
function VistaPrevia({ rubro, negocio, slug }: { rubro?: RubroPublico; negocio: string; slug: string }) {
  if (!rubro) return null;
  const recurso = rubro.recurso ?? "profesional";
  const cliente = rubro.cliente ?? "cliente";
  return (
    <aside aria-label="Vista previa" className="overflow-hidden rounded-2xl border bg-card shadow-sm lg:sticky lg:top-6">
      <FotoRubro codigo={rubro.codigo} />
      <div className="space-y-4 p-5 text-sm">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Vista previa</p>
          <p className="mt-1 text-lg font-bold leading-tight">{negocio.trim() || "Tu negocio"}</p>
          <p className="truncate text-muted-foreground">turnos360.com.ar/{slug || "tu-negocio"}</p>
        </div>
        <p>
          Tu agenda va a hablar de <b>{plural(recurso)}</b>, <b>{plural(cliente)}</b> y{" "}
          <b>{plural(rubro.turno ?? "turno")}</b>.
        </p>
        {rubro.servicios && rubro.servicios.length > 0 && (
          <div>
            <p className="font-medium">Arrancás con estos servicios:</p>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {rubro.servicios.map((s) => (
                <li key={s} className="rounded-full bg-muted px-2.5 py-1 text-xs">
                  {s}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted-foreground">Precios y duraciones se cambian desde Servicios.</p>
          </div>
        )}
      </div>
    </aside>
  );
}

