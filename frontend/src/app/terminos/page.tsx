import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Términos y condiciones · Turnos360",
  description:
    "Términos y condiciones de uso de Turnos360, la plataforma de gestión de turnos para negocios de servicios.",
};

/* Página legal: sobria y legible. La marca aparece en la navbar y el acento;
   el resto es tipografía tranquila para leer de corrido. */

const TINTA = "#0c1015";
const TINTA_SUAVE = "#4b5566";
const TEAL = "#17a08a";
const BORDE = "#e9ecf1";

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="mt-10 scroll-mt-24 text-xl font-bold tracking-tight"
      style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
    >
      {children}
    </h2>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-3 text-[15px] leading-relaxed" style={{ color: TINTA_SUAVE }}>
      {children}
    </p>
  );
}

export default function TerminosPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Navbar mínima */}
      <header
        className="sticky top-0 z-10 border-b bg-white/90 backdrop-blur"
        style={{ borderColor: BORDE }}
      >
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-3.5">
          <Link href="/" className="flex items-center gap-2">
            <span
              className="text-lg font-bold"
              style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
            >
              Turnos<span style={{ color: TEAL }}>360</span>
            </span>
          </Link>
          <Link href="/" className="text-sm font-medium hover:underline" style={{ color: TINTA_SUAVE }}>
            ← Volver al inicio
          </Link>
        </div>
      </header>

      <article className="mx-auto max-w-3xl px-5 pb-24 pt-12">
        <h1
          className="text-3xl font-bold tracking-tight md:text-4xl"
          style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
        >
          Términos y condiciones
        </h1>
        <p className="mt-2 text-sm" style={{ color: TINTA_SUAVE }}>
          Última actualización: julio de 2026
        </p>

        <P>
          Estos términos regulan el uso de <b>Turnos360</b>, una plataforma de
          gestión de turnos, clientes y finanzas para negocios de servicios
          (&quot;la Plataforma&quot;). Al crear una cuenta o reservar un turno a
          través de la Plataforma, aceptás estos términos.
        </P>

        <H2 id="definiciones">1. Definiciones</H2>
        <P>
          <b>El Negocio</b>: la empresa o profesional que contrata Turnos360
          para gestionar su agenda y ofrecer reservas online (una barbería, una
          peluquería, un consultorio).
        </P>
        <P>
          <b>El Cliente</b>: la persona que reserva un turno con un Negocio a
          través de su página en la Plataforma.
        </P>

        <H2 id="servicio">2. Qué es (y qué no es) Turnos360</H2>
        <P>
          Turnos360 es el software con el que cada Negocio administra su agenda,
          sus clientes y su caja, y ofrece reservas online las 24 horas. Los
          servicios que se reservan (un corte, una sesión, una consulta){" "}
          <b>los presta el Negocio, no Turnos360</b>. La calidad, el
          cumplimiento, los precios, las promociones y las políticas de
          cancelación o reembolso de cada servicio son responsabilidad exclusiva
          del Negocio que lo ofrece.
        </P>

        <H2 id="cuenta">3. La cuenta del Negocio</H2>
        <P>
          El Negocio es responsable de mantener la confidencialidad de sus
          credenciales de acceso y de toda la actividad que ocurra en su cuenta,
          incluida la de los usuarios que cree para su equipo. La información
          que el Negocio publica en su página (servicios, precios, horarios,
          fotos) debe ser veraz y estar actualizada.
        </P>

        <H2 id="suscripcion">4. Suscripción y pagos del servicio</H2>
        <P>
          El uso de la Plataforma por parte del Negocio se abona mediante una
          suscripción mensual, más un cargo inicial de configuración si
          corresponde. La falta de pago puede suspender el acceso al servicio.
          Los precios pueden actualizarse; los cambios se informan con
          anticipación. El Negocio puede dar de baja su suscripción cuando
          quiera: el acceso se mantiene hasta el final del período ya abonado,
          sin reembolsos proporcionales.
        </P>

        <H2 id="reservas">5. Reservas, señas y cobros online</H2>
        <P>
          La reserva de un turno crea un compromiso <b>entre el Cliente y el
          Negocio</b>. Si el Negocio activa el cobro anticipado (una seña o el
          total del servicio), ese cobro se procesa a través de Mercado Pago y{" "}
          <b>el dinero va directo a la cuenta de Mercado Pago del Negocio</b>:
          Turnos360 no procesa, retiene ni administra fondos de terceros, ni
          cobra comisión por reserva.
        </P>
        <P>
          Las políticas de reprogramación, cancelación y devolución de señas o
          pagos anticipados <b>las define cada Negocio</b>. Ante cualquier
          reclamo sobre un cobro, el Cliente debe dirigirse al Negocio, sin
          perjuicio de los derechos que le correspondan como consumidor frente a
          Mercado Pago o el Negocio.
        </P>

        <H2 id="datos">6. Datos de los Clientes</H2>
        <P>
          El Negocio es el responsable del tratamiento de los datos personales
          de sus Clientes que cargue o reciba a través de la Plataforma, en los
          términos de la Ley 25.326 de Protección de Datos Personales. El
          Negocio se compromete a usarlos únicamente para gestionar sus turnos y
          su relación comercial, a no enviar comunicaciones promocionales a
          quienes no lo hayan consentido, y a contar con el consentimiento
          necesario para cualquier dato sensible. El detalle está en nuestra{" "}
          <Link href="/privacidad" className="font-medium underline" style={{ color: TEAL }}>
            Política de privacidad
          </Link>
          .
        </P>

        <H2 id="uso">7. Uso correcto</H2>
        <P>
          No está permitido usar la Plataforma para fines ilegales, cargar datos
          de terceros sin su consentimiento, enviar spam, intentar vulnerar la
          seguridad del sistema ni acceder a información de otros negocios. El
          software, la marca y el contenido de Turnos360 son propiedad de sus
          titulares y no pueden copiarse ni revenderse.
        </P>

        <H2 id="disponibilidad">8. Disponibilidad</H2>
        <P>
          Trabajamos para que el servicio esté disponible de forma continua y
          realizamos copias de seguridad periódicas. Aun así, pueden existir
          interrupciones por mantenimiento o causas ajenas. En la medida
          permitida por la ley, la responsabilidad total de Turnos360 frente al
          Negocio se limita al monto abonado por el servicio en los últimos tres
          meses, y no incluye daños indirectos ni lucro cesante.
        </P>

        <H2 id="baja">9. Baja y suspensión</H2>
        <P>
          El Negocio puede solicitar la baja y la eliminación de su cuenta
          cuando quiera. Turnos360 se reserva el derecho de suspender cuentas
          que incumplan estos términos, con aviso previo salvo casos graves.
        </P>

        <H2 id="ley">10. Ley aplicable</H2>
        <P>
          Estos términos se rigen por las leyes de la República Argentina. Ante
          cualquier conflicto, las partes se someten a los tribunales ordinarios
          de la Provincia de Mendoza.
        </P>

        <H2 id="contacto">11. Contacto</H2>
        <P>
          Por consultas sobre estos términos, escribinos por WhatsApp desde{" "}
          <Link href="/" className="font-medium underline" style={{ color: TEAL }}>
            turnos360.com.ar
          </Link>
          .
        </P>
      </article>
    </main>
  );
}
