"use client";

/**
 * Mi suscripción · Cancelar. Tres pasos: qué va a pasar (y por qué se va),
 * la confirmación con la fecha concreta, y el estado final. Nada se corta en
 * el momento ni se borra: el servidor programa la baja al fin del período.
 */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AlertTriangle, ArrowLeft, CalendarClock, CheckCircle2 } from "lucide-react";

import { cancelarSuscripcion } from "@/lib/empresa-api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Cargando, fechaLarga, useSuscripcion } from "../_suscripcion";

const MOTIVOS = [
  "Es muy caro para mí",
  "No lo estoy usando",
  "Me falta una función",
  "Me cambio a otro sistema",
  "Cierro o pauso el negocio",
];

export default function SuscripcionCancelar() {
  const router = useRouter();
  const { datos, cargando, cargar } = useSuscripcion();
  const [paso, setPaso] = useState<1 | 2 | 3>(1);
  const [motivo, setMotivo] = useState<string | null>(null);
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  if (cargando || !datos) return <Cargando />;

  const hasta = datos.vence;
  const enPrueba = datos.estado === "prueba";
  const yaCancelada = ["cancelada", "cancelacion_programada", "suspendida"].includes(datos.estado);

  if (yaCancelada && paso !== 3) {
    return (
      <section className="mx-auto max-w-xl rounded-2xl border bg-card p-6 text-sm">
        <p className="font-semibold">
          {datos.estado === "suspendida" ? "Tu cuenta está suspendida." : "Tu suscripción ya está cancelada o con la baja programada."}
        </p>
        <p className="mt-1 text-muted-foreground">Desde el resumen podés ver hasta cuándo sigue activa o reactivarla.</p>
        <Button className="mt-4" variant="outline" onClick={() => router.push("/suscripcion")}>
          Ir al resumen
        </Button>
      </section>
    );
  }

  async function confirmar() {
    setEnviando(true);
    try {
      const texto = [motivo, comentario.trim()].filter(Boolean).join(" · ") || null;
      const r = await cancelarSuscripcion(texto);
      setResultado(r.detalle);
      setPaso(3);
      await cargar();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo cancelar");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="mx-auto max-w-xl space-y-5">
      <Link href="/suscripcion" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Volver al resumen
      </Link>

      <ol className="flex gap-2 text-xs font-medium text-muted-foreground" aria-label="Pasos">
        {["Qué pasa", "Confirmar", "Listo"].map((t, i) => (
          <li
            key={t}
            aria-current={paso === i + 1 ? "step" : undefined}
            className={`flex-1 rounded-full border px-3 py-1 text-center ${paso === i + 1 ? "border-primary text-foreground" : ""}`}
          >
            {i + 1}. {t}
          </li>
        ))}
      </ol>

      <div className="rounded-2xl border bg-card p-5 md:p-6">
        {paso === 1 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-bold">Cancelar tu suscripción</h2>
              <p className="text-sm text-muted-foreground">Antes de confirmar, esto es lo que pasa:</p>
            </div>
            <ul className="space-y-2 text-sm">
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                {hasta
                  ? `Seguís usando ${enPrueba ? "la prueba" : `el plan ${datos.plan_etiqueta}`} hasta el ${fechaLarga(hasta)}.`
                  : "La cancelación se aplica en el momento."}
              </li>
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                Tus clientes, turnos e historial NO se borran.
              </li>
              <li className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
                Después de esa fecha no se renueva y tu página deja de tomar reservas.
              </li>
              {datos.debito && (
                <li className="flex gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
                  Se corta el débito automático: no se te cobra nada más.
                </li>
              )}
            </ul>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">¿Por qué te vas? (opcional)</legend>
              <div className="flex flex-wrap gap-2">
                {MOTIVOS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    aria-pressed={motivo === m}
                    onClick={() => setMotivo(motivo === m ? null : m)}
                    className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                      motivo === m ? "border-primary bg-primary/10 text-foreground" : "hover:bg-muted"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <Textarea
                aria-label="Comentario"
                placeholder="Contanos más si querés"
                value={comentario}
                maxLength={200}
                onChange={(e) => setComentario(e.target.value)}
              />
            </fieldset>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={() => router.push("/suscripcion")}>
                Mantener mi suscripción
              </Button>
              <Button variant="destructive" onClick={() => setPaso(2)}>
                Continuar
              </Button>
            </div>
          </div>
        )}

        {paso === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-bold">¿Confirmás la cancelación?</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {hasta
                  ? `Tu ${enPrueba ? "prueba" : `plan ${datos.plan_etiqueta}`} queda activo hasta el ${fechaLarga(hasta)} y después no se renueva. Podés reactivarla cuando quieras.`
                  : "Tu suscripción se cancela ahora. Podés reactivarla cuando quieras."}
              </p>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={() => setPaso(1)} disabled={enviando}>
                Volver
              </Button>
              <Button variant="destructive" onClick={confirmar} disabled={enviando}>
                {enviando ? "Cancelando…" : "Sí, cancelar suscripción"}
              </Button>
            </div>
          </div>
        )}

        {paso === 3 && (
          <div className="space-y-4 text-center">
            <CalendarClock className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden />
            <div>
              <h2 className="text-lg font-bold">Listo, quedó registrada</h2>
              <p className="mt-1 text-sm text-muted-foreground">{resultado}</p>
            </div>
            <Button onClick={() => router.push("/suscripcion")}>Ver mi suscripción</Button>
          </div>
        )}
      </div>
    </section>
  );
}
