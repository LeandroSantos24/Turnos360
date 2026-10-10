"use client";

/**
 * Mi suscripción · Uso y límites. Los topes salen del servidor (topes del plan
 * vigente, o los pactados); acá solo se muestran.
 */

import Link from "next/link";

import { Cargando, SYNE, useSuscripcion } from "../_suscripcion";
import { BarraUso } from "../_componentes";

export default function SuscripcionUso() {
  const { datos, cargando } = useSuscripcion();
  if (cargando || !datos) return <Cargando />;

  const recursos = [
    {
      etiqueta: "Profesionales",
      usados: datos.uso.profesionales,
      tope: datos.topes.profesionales,
      que: "Las personas o boxes que atienden y tienen agenda.",
    },
    {
      etiqueta: "Usuarios con acceso",
      usados: datos.uso.usuarios,
      tope: datos.topes.usuarios,
      que: "Las cuentas que entran al panel (dueño, recepción, profesionales).",
    },
    {
      etiqueta: "Sucursales",
      usados: datos.uso.sucursales,
      tope: datos.topes.sucursales,
      que: "Los locales con agenda, caja y equipo propios.",
    },
  ];

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-bold" style={SYNE}>
            {datos.estado === "prueba" ? "Prueba gratis" : datos.plan_etiqueta}
          </h2>
          <span className="text-sm text-muted-foreground">{datos.plan_resumen}</span>
        </div>
        <div className="mt-5 grid gap-6 md:grid-cols-3">
          {recursos.map((r) => (
            <div key={r.etiqueta} className="space-y-1.5">
              <BarraUso etiqueta={r.etiqueta} usados={r.usados} tope={r.tope} />
              <p className="text-xs text-muted-foreground">
                {r.tope === null ? "Ilimitado en tu plan. " : ""}
                {r.que}
              </p>
            </div>
          ))}
        </div>
      </section>

      {datos.grilla.length > 0 && (
        <section className="rounded-2xl border bg-card p-5 md:p-6">
          <h2 className="text-base font-bold" style={SYNE}>
            Qué incluye cada plan
          </h2>
          <ul className="mt-3 divide-y text-sm">
            {datos.grilla.map((p) => (
              <li key={p.codigo} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                <span className="font-medium">
                  {p.etiqueta}
                  {p.codigo === datos.plan_codigo && datos.estado !== "prueba" && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">(tu plan)</span>
                  )}
                </span>
                <span className="text-muted-foreground">{p.resumen}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-muted-foreground">
            ¿Te quedás corto?{" "}
            <Link href="/suscripcion/planes" className="font-medium text-foreground underline underline-offset-4">
              Ver planes
            </Link>
          </p>
        </section>
      )}
    </div>
  );
}
