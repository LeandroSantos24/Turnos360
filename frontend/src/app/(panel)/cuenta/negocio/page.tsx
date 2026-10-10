"use client";

/**
 * Mi cuenta · Negocio y permisos (/cuenta/negocio).
 *
 * En qué negocio estás, con qué rol y qué te deja hacer ese rol. La lista de
 * permisos es la misma regla que aplican el menú (layout del panel) y el
 * backend (gate_dueno / gate_gestion en api/deps.py): si se cambia allá, se
 * cambia acá.
 *
 * Avisos por email: hoy no hay preferencias por persona. Los de reservas van
 * al email público del negocio y los de la suscripción al del dueño. Se
 * muestra a dónde llegan, sin interruptores que no harían nada.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Check, Mail, Minus } from "lucide-react";

import { useConfigRubro } from "@/lib/config-rubro";
import { obtenerLanding } from "@/lib/empresa-api";
import { CargandoCuenta, ErrorCuenta, FilaDato, ROL_LABEL, useCuenta } from "../_cuenta";

type Permisos = { puede: string[]; noPuede: string[] };

function permisosDe(rol: string, termCliente: string): Permisos {
  const clientes = `${termCliente.charAt(0).toUpperCase()}${termCliente.slice(1)}s`;
  if (rol === "dueno") {
    return {
      puede: [
        "Todo el panel: agenda, clientes, servicios y equipo",
        "Caja, estadísticas y métodos de pago",
        "Campañas, cupones, membresías y gift cards (según el plan)",
        "Tu página de reservas y sus reglas",
        "Mi suscripción: plan, pagos y vencimientos",
      ],
      noPuede: [],
    };
  }
  if (rol === "profesional") {
    return {
      puede: ["Mi día: tus turnos", `${clientes}: la ficha de los que atendés`, "Tu cuenta"],
      noPuede: ["Agenda del resto del equipo", "Caja y finanzas", "Configuración del negocio"],
    };
  }
  // recepción y administrador
  return {
    puede: [
      "Agenda y turnos de tu local",
      `${clientes}`,
      "Cobros en la caja del día",
      "Vender gift cards y asignar membresías (según el plan)",
      "Ver servicios y profesionales",
    ],
    noPuede: [
      "Crear o cambiar servicios, precios y planes de abono",
      "Estadísticas y métodos de pago",
      "Equipo, campañas y cupones",
      "Tu página de reservas",
      "La suscripción del negocio",
    ],
  };
}

export default function CuentaNegocio() {
  const { usuario, error, recargar } = useCuenta();
  const config = useConfigRubro();
  const [emailNegocio, setEmailNegocio] = useState<string | null | undefined>(undefined);
  const dueno = usuario?.rol === "dueno";

  useEffect(() => {
    if (!dueno) return;
    obtenerLanding()
      .then((l) => setEmailNegocio(l.email_publico))
      .catch(() => setEmailNegocio(undefined));
  }, [dueno]);

  if (error) return <ErrorCuenta onReintentar={recargar} />;
  if (!usuario) return <CargandoCuenta />;

  const multisucursal = (config?.limite_sucursales ?? 1) > 1;
  const termCliente = config?.preset?.terminologia?.cliente ?? "cliente";
  const { puede, noPuede } = permisosDe(usuario.rol, termCliente);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="tarjeta p-5 sm:p-6" aria-labelledby="t-negocio">
        <h2 id="t-negocio" className="font-semibold">Dónde estás</h2>
        <dl className="mt-2 divide-y">
          <FilaDato etiqueta="Negocio" valor={usuario.empresa_nombre ?? config?.nombre ?? "—"} nota={config?.rubro_nombre} />
          <FilaDato
            etiqueta="Tu rol"
            valor={ROL_LABEL[usuario.rol] ?? usuario.rol}
            nota={dueno ? "Cuenta principal del negocio." : "Lo asigna el dueño desde Equipo."}
          />
          {multisucursal && usuario.sucursal_nombre && (
            <FilaDato
              etiqueta="Tu local"
              valor={usuario.sucursal_nombre}
              nota={
                dueno
                  ? "Ves y comparás todos los locales; este es en el que abre tu agenda."
                  : "Ves la agenda y la caja de este local. Lo cambia el dueño desde Equipo."
              }
            />
          )}
          {config?.plan_etiqueta && <FilaDato etiqueta="Plan" valor={config.plan_etiqueta} />}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          Cada cuenta pertenece a un solo negocio. Para trabajar en otro, ese negocio te tiene que dar de alta con otro email.
        </p>
      </section>

      <section className="tarjeta p-5 sm:p-6" aria-labelledby="t-permisos">
        <h2 id="t-permisos" className="font-semibold">Qué podés hacer</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {puede.map((p) => (
            <li key={p} className="flex gap-2">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
              <span>{p}</span>
            </li>
          ))}
        </ul>
        {noPuede.length > 0 && (
          <>
            <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Solo el dueño</p>
            <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
              {noPuede.map((p) => (
                <li key={p} className="flex gap-2">
                  <Minus className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="tarjeta p-5 sm:p-6 lg:col-span-2" aria-labelledby="t-avisos">
        <h2 id="t-avisos" className="flex items-center gap-2 font-semibold">
          <Mail className="h-4 w-4 text-muted-foreground" aria-hidden /> A dónde llegan los avisos
        </h2>
        {dueno ? (
          <dl className="mt-2 divide-y">
            <FilaDato
              etiqueta="Reservas online"
              valor={emailNegocio === undefined ? "…" : emailNegocio || "Sin email del negocio cargado"}
              nota={
                <>
                  Cada reserva nueva le llega al email del negocio. Se cambia en{" "}
                  <Link href="/mi-pagina" className="enlace">
                    Mi página
                  </Link>{" "}
                  › El negocio.
                </>
              }
            />
            <FilaDato
              etiqueta="Suscripción"
              valor={usuario.email}
              nota="Vencimientos y pagos de Turnos360 le llegan al dueño."
            />
            <FilaDato
              etiqueta="Tus clientes"
              valor="Confirmación, recordatorios y campañas"
              nota={
                <>
                  Se prenden y se ajustan en{" "}
                  <Link href="/campanas" className="enlace">
                    Campañas
                  </Link>
                  .
                </>
              }
            />
          </dl>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            Los avisos del negocio (reservas nuevas, suscripción) le llegan al dueño. A tu email solo te llega lo de tu cuenta, como recuperar la contraseña.
          </p>
        )}
      </section>
    </div>
  );
}
