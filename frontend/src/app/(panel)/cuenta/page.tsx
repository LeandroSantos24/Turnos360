"use client";

/**
 * Mi cuenta · Resumen (/cuenta).
 *
 * Quién sos, en qué negocio y con qué plan, y la entrada a cada apartado.
 * El estado del plan es el que manda el servidor (etiqueta y tono de
 * core/estados_suscripcion.py): acá no se calcula nada, se muestra y se
 * deriva a «Mi suscripción», que es donde vive el detalle.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Building2, KeyRound, MailWarning, Receipt, UserRound } from "lucide-react";

import { useConfigRubro } from "@/lib/config-rubro";
import { obtenerSuscripcion, type Suscripcion } from "@/lib/empresa-api";
import { etiquetaPlan } from "@/lib/precios";
import { BadgeEstado } from "../suscripcion/_suscripcion";
import { Avatar, CargandoCuenta, ErrorCuenta, ROL_LABEL, useCuenta } from "./_cuenta";

export default function CuentaResumen() {
  const { usuario, error, recargar } = useCuenta();
  const config = useConfigRubro();
  const dueno = usuario?.rol === "dueno";
  const [sus, setSus] = useState<Suscripcion | null>(null);

  useEffect(() => {
    if (!dueno) return;
    obtenerSuscripcion()
      .then(setSus)
      .catch(() => setSus(null));
  }, [dueno]);

  if (error) return <ErrorCuenta onReintentar={recargar} />;
  if (!usuario) return <CargandoCuenta />;

  const multisucursal = (config?.limite_sucursales ?? 1) > 1;
  const plan = sus ? etiquetaPlan(sus.plan) : config?.plan_etiqueta;

  const accesos = [
    {
      href: "/cuenta/perfil",
      Icono: UserRound,
      titulo: "Perfil",
      texto: "Tu nombre y cómo figurás en el panel.",
      aviso: usuario.email_verificado ? null : "Email sin confirmar",
    },
    {
      href: "/cuenta/seguridad",
      Icono: KeyRound,
      titulo: "Seguridad",
      texto: "Contraseña y sesiones en otros dispositivos.",
      aviso: null,
    },
    {
      href: "/cuenta/negocio",
      Icono: Building2,
      titulo: "Negocio y permisos",
      texto: "Tu rol, tu local y qué podés hacer.",
      aviso: null,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Quién sos + tarjeta de contexto del negocio */}
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="tarjeta flex items-center gap-4 p-5">
          <Avatar nombre={usuario.nombre} tam="lg" />
          <div className="min-w-0">
            <p className="truncate text-lg font-bold leading-tight">{usuario.nombre}</p>
            <p className="truncate text-sm text-muted-foreground">{usuario.email}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-[hsl(170_85%_26%)] dark:text-primary">
                {ROL_LABEL[usuario.rol] ?? usuario.rol}
              </span>
              {!usuario.email_verificado && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
                  <MailWarning className="h-3 w-3" aria-hidden /> Email sin confirmar
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="tarjeta p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tu negocio</p>
          <p className="mt-1 truncate text-lg font-bold leading-tight">
            {usuario.empresa_nombre ?? config?.nombre ?? "—"}
          </p>
          <p className="text-sm text-muted-foreground">
            {[config?.rubro_nombre, multisucursal ? usuario.sucursal_nombre : null].filter(Boolean).join(" · ")}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {plan && <span className="text-sm font-medium">Plan {plan}</span>}
            {dueno && sus?.etiqueta && <BadgeEstado etiqueta={sus.etiqueta} tono={sus.tono ?? "neutro"} />}
          </div>
          {dueno && sus?.mensaje && <p className="mt-1 text-xs text-muted-foreground">{sus.mensaje}</p>}
          {dueno && (
            <Link
              href="/suscripcion"
              className="enlace mt-3 inline-flex items-center gap-1.5 text-sm"
            >
              <Receipt className="h-4 w-4" aria-hidden />
              Ver vencimiento, pagos y planes
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          )}
        </div>
      </section>

      {/* Accesos a cada apartado */}
      <section aria-label="Apartados" className="grid gap-3 sm:grid-cols-3">
        {accesos.map(({ href, Icono, titulo, texto, aviso }) => (
          <Link
            key={href}
            href={href}
            className="tarjeta tarjeta-viva group flex flex-col gap-2 p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted">
              <Icono className="h-4 w-4" aria-hidden />
            </span>
            <span className="font-semibold">{titulo}</span>
            <span className="text-sm text-muted-foreground">{texto}</span>
            {aviso && <span className="text-xs font-semibold text-amber-700 dark:text-amber-300">{aviso}</span>}
          </Link>
        ))}
      </section>
    </div>
  );
}
