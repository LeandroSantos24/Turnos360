import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Política de privacidad · Turnos360",
  description:
    "Cómo Turnos360 recopila, usa y protege los datos de los negocios y de sus clientes.",
};

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

export default function PrivacidadPage() {
  return (
    <main className="min-h-screen bg-white">
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
          Política de privacidad
        </h1>
        <p className="mt-2 text-sm" style={{ color: TINTA_SUAVE }}>
          Última actualización: julio de 2026
        </p>

        <P>
          Proteger los datos de los negocios que usan Turnos360 — y los de sus
          clientes — es una prioridad. Esta política explica qué información se
          recopila, para qué se usa y cuáles son tus derechos según la Ley
          25.326 de Protección de Datos Personales.
        </P>

        {/* ───────────────────────── Clientes que reservan ───────────────── */}
        <div
          className="mt-8 rounded-2xl border p-5"
          style={{ borderColor: "#17a08a55", background: "#17a08a0d" }}
        >
          <h2
            id="reservas"
            className="scroll-mt-24 text-lg font-bold"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            ¿Reservaste un turno en un negocio que usa Turnos360?
          </h2>
          <P>
            <b>Quién recibe tus datos.</b> Los datos que cargás al reservar
            (nombre, teléfono y email) los recibe <b>el negocio</b> en el que
            reservaste, que es el responsable de tratarlos. Turnos360 es la
            plataforma tecnológica que ese negocio usa para administrar su
            agenda.
          </P>
          <P>
            <b>Para qué se usan.</b> Para gestionar tu turno: confirmártelo,
            recordártelo por email antes de la cita y avisarte si cambia o se
            cancela. Esos mensajes son parte del servicio que pediste.
          </P>
          <P>
            <b>Promociones, solo si vos querés.</b> El negocio únicamente puede
            mandarte emails promocionales (descuentos, saludos de cumpleaños) si
            marcaste la casilla de aceptación al reservar. Podés pedir la baja
            de esas comunicaciones cuando quieras.
          </P>
          <P>
            <b>Tus derechos.</b> Podés pedir el acceso, la corrección o la
            eliminación de tus datos contactando directamente al negocio, o
            escribiéndonos a nosotros, que le trasladaremos el pedido.
          </P>
          <P>
            <b>Pagos.</b> Si pagaste una seña o el total al reservar, el cobro
            lo procesó Mercado Pago y el dinero fue directo a la cuenta del
            negocio. Turnos360 no ve ni guarda los datos de tu tarjeta.
          </P>
        </div>

        {/* ───────────────────────── Negocios ────────────────────────────── */}
        <H2 id="negocios">Para los negocios que usan Turnos360</H2>

        <H2 id="recopilamos">1. Qué datos recopilamos</H2>
        <P>
          <b>Datos de tu cuenta:</b> el nombre de tu negocio, tu email de acceso
          y la configuración que cargás (servicios, precios, horarios, equipo,
          tu página pública).
        </P>
        <P>
          <b>Datos de tus clientes:</b> la información que cargás o que tus
          clientes dejan al reservar (nombre, teléfono, email, historial de
          turnos, pagos, notas). <b>Vos sos el responsable de esos datos</b>;
          Turnos360 actúa como encargado del tratamiento por tu cuenta y solo
          los usa para prestarte el servicio.
        </P>
        <P>
          <b>Datos técnicos:</b> lo mínimo necesario para el funcionamiento y la
          seguridad (por ejemplo, la sesión de inicio). No usamos tus datos ni
          los de tus clientes para publicidad, y no los vendemos ni cedemos a
          terceros.
        </P>

        <H2 id="uso">2. Cómo los usamos</H2>
        <P>
          Exclusivamente para prestar el servicio: mostrar tu agenda, gestionar
          turnos y cobros, enviar los emails de tu negocio (confirmaciones,
          recordatorios y las campañas que actives) y generar tus reportes.
          Los emails promocionales solo salen a los clientes que dieron su
          consentimiento — la plataforma lo controla automáticamente.
        </P>

        <H2 id="almacenamiento">3. Dónde se almacenan</H2>
        <P>
          En servidores profesionales en la nube contratados por Turnos360, con
          conexión cifrada (HTTPS), contraseñas encriptadas y credenciales
          sensibles encriptadas en reposo. Cada negocio accede únicamente a su
          propia información: el aislamiento entre empresas está aplicado en
          cada consulta del sistema. Se realizan copias de seguridad periódicas.
        </P>

        <H2 id="terceros">4. Servicios de terceros</H2>
        <P>
          Para funciones específicas intervienen proveedores que procesan datos
          por nuestra cuenta: <b>Mercado Pago</b> para los cobros anticipados
          (el dinero va directo a tu cuenta; nunca vemos los datos de la tarjeta
          del cliente) y el proveedor de correo con el que salen los emails de
          tu negocio. Cada uno cumple sus propios estándares de seguridad.
        </P>

        <H2 id="derechos">5. Tus derechos</H2>
        <P>
          Podés acceder, corregir o eliminar la información de tu cuenta desde
          la propia aplicación. Si querés eliminar tu cuenta por completo, junto
          con todos sus datos, escribinos y lo gestionamos. Los titulares de
          datos personales tienen además los derechos de acceso, rectificación
          y supresión previstos por la Ley 25.326, ante el responsable del
          tratamiento y la Agencia de Acceso a la Información Pública.
        </P>

        <H2 id="conservacion">6. Conservación</H2>
        <P>
          Conservamos tus datos mientras tu cuenta esté activa. Si dejás de usar
          el servicio, podés solicitar su eliminación definitiva.
        </P>

        <H2 id="cambios">7. Cambios</H2>
        <P>
          Podemos actualizar esta política; los cambios importantes se comunican
          y la versión vigente está siempre en esta página.
        </P>

        <H2 id="contacto">8. Contacto</H2>
        <P>
          Por cualquier consulta sobre privacidad, escribinos por WhatsApp desde{" "}
          <Link href="/" className="font-medium underline" style={{ color: TEAL }}>
            turnos360.com.ar
          </Link>
          .
        </P>
      </article>
    </main>
  );
}
