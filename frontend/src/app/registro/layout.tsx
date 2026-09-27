import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Creá tu cuenta gratis · Turnos360",
  description:
    "Probá Turnos360 gratis: agenda online, reservas 24/7, seña con Mercado Pago y recordatorios automáticos para tu negocio.",
  alternates: { canonical: "/registro" },
};

export default function LayoutRegistro({ children }: { children: React.ReactNode }) {
  return children;
}
