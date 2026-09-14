"use client";

/**
 * PASO 4 — Transferencia bancaria.
 *
 * Los datos para ir al homebanking y el monto EXACTO, arriba de todo.
 *
 * El monto va primero y en grande por un motivo concreto: cuando estaba abajo,
 * había que deducirlo de la grilla de planes de otra sección, y ahí es donde se
 * transfiere de menos. El número que la persona necesita para tipear en el
 * banco tiene que estar antes que el CBU, no después.
 */

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Cargando,
  FilaCopiable,
  PasoLayout,
  SYNE,
  pesos,
  planDeLaUrl,
  useSuscripcion,
} from "../../_suscripcion";

function Transferencia() {
  const router = useRouter();
  const params = useSearchParams();
  const codigo = params.get("plan");
  const { datos, avisoPendiente, cargando } = useSuscripcion();

  if (cargando || !datos) return <Cargando />;

  const destino = planDeLaUrl(datos, codigo);
  const monto = destino?.precio ?? datos.cuota;
  const c = datos.cobro;
  const hayTransferencia = Boolean(c.cbu || c.alias);

  if (!hayTransferencia) {
    return (
      <PasoLayout paso={3} titulo="Todavía no hay datos de transferencia">
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <p className="text-sm text-muted-foreground">
            No tenemos cargado el CBU ni el alias. Escribinos y te los pasamos.
          </p>
        </section>
      </PasoLayout>
    );
  }

  return (
    <PasoLayout
      paso={3}
      titulo="Transferí desde tu banco"
      bajada={
        destino
          ? `Estás pagando ${destino.etiqueta}. Tu plan cambia cuando confirmemos la transferencia.`
          : "Cuando la confirmemos contra el banco, tu vencimiento se corre 30 días."
      }
    >
      {/* EL MONTO, antes que nada. */}
      <section className="rounded-2xl border border-primary/40 bg-primary/5 p-4 md:p-5">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Transferí exactamente
        </p>
        <p className="text-3xl font-bold tabular-nums" style={SYNE}>
          {pesos(monto)}
        </p>
        {destino && (
          <p className="mt-1 text-sm text-muted-foreground">{destino.resumen}</p>
        )}
      </section>

      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <h2 className="text-base font-bold" style={SYNE}>
          A esta cuenta
        </h2>
        <div className="mt-3 divide-y rounded-xl border px-3.5">
          {c.alias && <FilaCopiable etiqueta="Alias" valor={c.alias} />}
          {c.cbu && <FilaCopiable etiqueta="CBU" valor={c.cbu} />}
          {c.titular && (
            <div className="py-2.5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Titular
              </p>
              <p className="text-sm font-medium">{c.titular}</p>
            </div>
          )}
          {c.cuit && (
            <div className="py-2.5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                CUIT / CUIL
              </p>
              <p className="text-sm font-medium tabular-nums">{c.cuit}</p>
            </div>
          )}
          {c.banco && (
            <div className="py-2.5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Banco
              </p>
              <p className="text-sm font-medium">{c.banco}</p>
            </div>
          )}
        </div>

        <div className="mt-4 rounded-xl border bg-muted/40 p-3.5">
          <p className="text-sm font-medium">Cómo sigue</p>
          <ol className="mt-1.5 space-y-1 pl-4 text-sm text-muted-foreground">
            <li className="list-decimal">
              Transferís {monto ? <b>{pesos(monto)}</b> : "el importe"} a los
              datos de arriba.
            </li>
            <li className="list-decimal">
              Volvés acá y nos avisás en el paso siguiente.
            </li>
            <li className="list-decimal">
              Lo confirmamos contra el banco: tu vencimiento se corre 30 días.
            </li>
          </ol>
          <p className="mt-2 text-xs text-muted-foreground">
            La verificación es manual, así que puede demorar unas horas. Mientras
            tanto tu cuenta sigue funcionando: para eso están los{" "}
            {datos.dias_prorroga} días de gracia.
          </p>
        </div>

        {c.whatsapp && (
          <a
            href={`https://wa.me/${c.whatsapp}?text=${encodeURIComponent(
              "Hola! Te paso el comprobante de la transferencia de Turnos360.",
            )}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center gap-2 rounded-lg border bg-background px-3.5 py-2 text-sm font-medium"
          >
            Mandar el comprobante por WhatsApp
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}

        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
          {avisoPendiente ? (
            <Button onClick={() => router.push("/suscripcion")}>
              Volver a mi suscripción
            </Button>
          ) : (
            <Button
              onClick={() =>
                router.push(
                  `/suscripcion/cambiar/comprobante${codigo ? `?plan=${codigo}` : ""}`,
                )
              }
            >
              Ya transferí
            </Button>
          )}
        </div>
      </section>
    </PasoLayout>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Cargando />}>
      <Transferencia />
    </Suspense>
  );
}
